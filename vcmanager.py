import asyncio
import time
from pyrogram import Client
from pyrogram.errors import FloodWait, UserDeactivated, AuthKeyUnregistered, UserNotParticipant
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import (
    GroupCallNotFound,
    NotInGroupCallError,
    NoActiveGroupCall,
)
from config import API_ID, API_HASH, SESSIONS_DIR

_clients: dict[str, Client] = {}
_tgcalls: dict[str, PyTgCalls] = {}
_joined: dict[str, set[int]] = {}
_dead: set[str] = set()
_login_in_progress: set[str] = set()

_auto_rejoin: bool = True
_rejoin_task: asyncio.Task | None = None
_REJOIN_INTERVAL = 15
_MAX_RETRIES = 3
_JOIN_STAGGER = 2.5  # seconds between accounts to avoid flood


def make_client(session_name: str) -> Client:
    if session_name in _clients:
        return _clients[session_name]
    app = Client(
        session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=SESSIONS_DIR,
        no_updates=True,
    )
    _clients[session_name] = app
    return app


async def _handle_flood(coro):
    """Run a coroutine, sleeping through any FloodWait."""
    while True:
        try:
            return await coro
        except FloodWait as e:
            wait = min(e.value, 60)
            print(f"[flood] sleeping {wait}s")
            await asyncio.sleep(wait + 1)
        except (UserDeactivated, AuthKeyUnregistered) as e:
            raise


async def start_client(session_name: str) -> bool:
    if session_name in _login_in_progress:
        return False
    if session_name in _dead:
        print(f"[start_client] {session_name} is marked dead, skipping")
        return False
    _login_in_progress.add(session_name)
    try:
        app = make_client(session_name)
        if not app.is_connected:
            try:
                await app.start()
            except (UserDeactivated, AuthKeyUnregistered) as e:
                print(f"[start_client] {session_name} session dead: {e}")
                _dead.add(session_name)
                return False
            except FloodWait as e:
                await asyncio.sleep(min(e.value, 60) + 1)
                await app.start()
        call = PyTgCalls(app)
        if not call._is_started:
            await call.start()
        _tgcalls[session_name] = call
        _dead.discard(session_name)
        return True
    except Exception as e:
        print(f"[start_client] {session_name}: {e}")
        return False
    finally:
        _login_in_progress.discard(session_name)


async def stop_client(session_name: str) -> bool:
    try:
        for cid in list(_joined.get(session_name, set())):
            await leave_vc(session_name, cid)
        call = _tgcalls.pop(session_name, None)
        if call:
            try:
                await call.stop()
            except Exception:
                pass
        app = _clients.pop(session_name, None)
        if app and app.is_connected:
            try:
                await app.stop()
            except Exception:
                pass
        _joined.pop(session_name, None)
        return True
    except Exception as e:
        print(f"[stop_client] {session_name}: {e}")
        return False


async def _resolve_chat_id(session_name: str, target) -> int | None:
    """Resolve a link/username/numeric to a real chat id."""
    app = _clients.get(session_name)
    if not app or not app.is_connected:
        return None
    try:
        chat = await app.get_chat(target)
        return chat.id
    except Exception:
        return None


async def join_chat(session_name: str, chat_id) -> bool:
    app = _clients.get(session_name)
    if not app or not app.is_connected:
        ok = await start_client(session_name)
        if not ok:
            return False
        app = _clients[session_name]
    # If target is a link, resolve it; if already a member, fine.
    try:
        await _handle_flood(app.get_chat(chat_id))
        return True
    except Exception:
        pass
    try:
        await _handle_flood(app.join_chat(str(chat_id)))
        return True
    except FloodWait:
        return False
    except UserNotParticipant:
        return True
    except Exception as e:
        # Already a member or banned
        if "already" in str(e).lower() or "ChannelPrivate" in str(e):
            return True
        print(f"[join_chat] {session_name}: {e}")
        return False


async def join_vc(session_name: str, chat_id: int, retry: int = 0) -> bool:
    call = _tgcalls.get(session_name)
    if not call:
        ok = await start_client(session_name)
        if not ok:
            return False
        call = _tgcalls[session_name]
    try:
        call.join_group_call(chat_id, None, mute=True)
        _joined.setdefault(session_name, set()).add(chat_id)
        return True
    except NoActiveGroupCall:
        # No active call right now — that's okay, auto-rejoin will catch it later
        return False
    except GroupCallNotFound:
        return False
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg:
            _joined.setdefault(session_name, set()).add(chat_id)
            return True
        if retry < _MAX_RETRIES and ("network" in msg or "timeout" in msg):
            await asyncio.sleep(2)
            return await join_vc(session_name, chat_id, retry + 1)
        print(f"[join_vc] {session_name} -> {chat_id}: {e}")
        return False


async def leave_vc(session_name: str, chat_id: int) -> bool:
    call = _tgcalls.get(session_name)
    if not call:
        return False
    try:
        call.leave_group_call(chat_id)
    except (NotInGroupCallError, GroupCallNotFound):
        pass
    except Exception:
        pass
    _joined.get(session_name, set()).discard(chat_id)
    return True


async def join_all_targets(session_name: str, targets: list) -> dict:
    results = {}
    for t in targets:
        chat_id = t["chat_id"]
        joined_chat = await join_chat(session_name, chat_id)
        if not joined_chat:
            results[chat_id] = False
            continue
        # Resolve link to int id for pytgcalls
        if not isinstance(chat_id, int):
            resolved = await _resolve_chat_id(session_name, chat_id)
            if resolved:
                chat_id = resolved
        joined_vc = await join_vc(session_name, chat_id)
        results[chat_id] = joined_vc
    return results


async def join_all_accounts(targets: list) -> dict:
    """Join all accounts with staggered timing to avoid Telegram flood bans."""
    results = {}
    for s in list(_clients.keys()):
        results[s] = await join_all_targets(s, targets)
        await asyncio.sleep(_JOIN_STAGGER)
    return results


async def is_in_call(session_name: str, chat_id: int) -> bool:
    call = _tgcalls.get(session_name)
    if not call:
        return False
    try:
        call.get_call(chat_id)
        return True
    except (NoActiveGroupCall, GroupCallNotFound):
        # No call exists — account isn't "in" it, but also nothing to rejoin yet
        return chat_id in _joined.get(session_name, set())
    except Exception:
        return chat_id in _joined.get(session_name, set())


# ---------- Auto-rejoin background loop ----------

def auto_rejoin_enabled() -> bool:
    return _auto_rejoin


async def set_auto_rejoin(enabled: bool):
    global _auto_rejoin, _rejoin_task
    _auto_rejoin = enabled
    if enabled and (_rejoin_task is None or _rejoin_task.done()):
        _rejoin_task = asyncio.create_task(_rejoin_loop())
    elif not enabled and _rejoin_task and not _rejoin_task.done():
        _rejoin_task.cancel()
        _rejoin_task = None


async def _rejoin_loop():
    import database as db
    print("[auto-rejoin] loop started")
    while True:
        try:
            await asyncio.sleep(_REJOIN_INTERVAL)
            if not _auto_rejoin:
                break
            targets = await db.list_targets()
            if not targets:
                continue
            for sname in list(_clients.keys()):
                if sname in _dead:
                    continue
                for t in targets:
                    cid = t["chat_id"]
                    try:
                        cid_int = int(cid)
                    except (TypeError, ValueError):
                        # Resolve link to int
                        cid_int = await _resolve_chat_id(sname, cid)
                        if not cid_int:
                            continue
                    in_call = await is_in_call(sname, cid_int)
                    if not in_call:
                        # Check if a call actually exists before rejoining
                        try:
                            await join_chat(sname, cid_int)
                        except Exception:
                            pass
                        joined = await join_vc(sname, cid_int)
                        if joined:
                            print(f"[auto-rejoin] {sname} rejoined {cid_int}")
        except asyncio.CancelledError:
            print("[auto-rejoin] loop cancelled")
            break
        except Exception as e:
            print(f"[auto-rejoin] error: {e}")


async def start_rejoin_loop():
    global _rejoin_task
    if _auto_rejoin and (_rejoin_task is None or _rejoin_task.done()):
        _rejoin_task = asyncio.create_task(_rejoin_loop())


async def stop_all():
    await set_auto_rejoin(False)
    for s in list(_clients.keys()):
        await stop_client(s)


def active_accounts() -> list:
    return [s for s in _clients.keys() if s not in _dead]


def dead_accounts() -> list:
    return list(_dead)


def joined_targets(session_name: str) -> list:
    return list(_joined.get(session_name, set()))


async def validate_session(session_name: str) -> str:
    """Returns 'alive', 'dead', or 'unknown'."""
    app = _clients.get(session_name)
    if not app:
        ok = await start_client(session_name)
        if not ok:
            return "dead" if session_name in _dead else "unknown"
        app = _clients[session_name]
    if not app.is_connected:
        ok = await start_client(session_name)
        if not ok:
            return "dead" if session_name in _dead else "unknown"
    try:
        me = await app.get_me()
        return "alive"
    except (UserDeactivated, AuthKeyUnregistered):
        _dead.add(session_name)
        return "dead"
    except Exception:
        return "unknown"
