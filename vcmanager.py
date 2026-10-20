import asyncio
from typing import Optional

from pyrogram import Client
from pyrogram.errors import (
    FloodWait,
    UserDeactivated,
    AuthKeyUnregistered,
    UserNotParticipant,
    ChannelPrivate,
)
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NotInCallError,
    PyTgCallsAlreadyRunning,
)
from config import API_ID, API_HASH, SESSIONS_DIR

_clients: dict = {}
_tgcalls: dict = {}
_joined: dict = {}
_dead: set = set()
_login_in_progress: set = set()
_started_tgcalls: set = set()

_auto_rejoin: bool = True
_rejoin_task: Optional[asyncio.Task] = None
_REJOIN_INTERVAL = 20
_MAX_RETRIES = 3
_JOIN_STAGGER = 3.0


def make_client(session_name: str, session_string: str = "") -> Client:
    if session_name in _clients:
        return _clients[session_name]
    if session_string:
        app = Client(
            session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string,
            no_updates=False,
        )
    else:
        app = Client(
            session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=SESSIONS_DIR,
            in_memory=False,
            no_updates=False,
        )
    _clients[session_name] = app
    return app


async def _with_flood_wait(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        wait = min(e.value, 120)
        print(f"[flood] sleeping {wait}s")
        await asyncio.sleep(wait + 1)
        return await func(*args, **kwargs)
    except (UserDeactivated, AuthKeyUnregistered):
        raise


async def start_client(session_name: str, session_string: str = "") -> bool:
    if session_name in _login_in_progress:
        return False
    if session_name in _dead:
        print(f"[start_client] {session_name} is marked dead, skipping")
        return False
    _login_in_progress.add(session_name)
    try:
        app = make_client(session_name, session_string)
        if not app.is_connected:
            try:
                await app.start()
            except (UserDeactivated, AuthKeyUnregistered) as e:
                print(f"[start_client] {session_name} session dead: {e}")
                _dead.add(session_name)
                return False
            except FloodWait as e:
                await asyncio.sleep(min(e.value, 120) + 1)
                try:
                    await app.start()
                except (UserDeactivated, AuthKeyUnregistered):
                    _dead.add(session_name)
                    return False

        call = _tgcalls.get(session_name)
        if call is None:
            call = PyTgCalls(app)
            if session_name not in _started_tgcalls:
                try:
                    await call.start()
                except PyTgCallsAlreadyRunning:
                    pass
                except Exception as e:
                    msg = str(e).lower()
                    if "already" not in msg and "started" not in msg:
                        print(f"[start_client] pytgcalls start {session_name}: {e}")
                _started_tgcalls.add(session_name)
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
        _started_tgcalls.discard(session_name)
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


async def _resolve_chat_id(session_name: str, target) -> Optional[int]:
    app = _clients.get(session_name)
    if not app or not app.is_connected:
        return None
    try:
        chat = await _with_flood_wait(app.get_chat, target)
        return chat.id
    except Exception:
        return None




def _is_invite_link(chat_id):
    """True agar chat_id private invite link hai (t.me/+... ya t.me/joinchat/...)."""
    if not isinstance(chat_id, str):
        return False
    t = chat_id.strip().lower()
    return ("t.me/+" in t or "t.me/joinchat/" in t or "telegram.me/+" in t or
            "telegram.dog/+" in t)


async def join_chat(session_name: str, chat_id) -> bool:
    if _is_invite_link(chat_id):
        try:
            await app.join_chat(chat_id.strip())
            print(f"[join_chat] {session_name}: joined invite link")
            return True
        except Exception as e:
            print(f"[join_chat] {session_name}: invite link failed: {e}")
            return False
    if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
        chat_id = int(chat_id)
    if isinstance(chat_id, int) and chat_id > 0:
        chat_id = int(f"-100{chat_id}")
    app = _clients.get(session_name)
    if not app or not app.is_connected:
        ok = await start_client(session_name)
        if not ok:
            return False
        app = _clients[session_name]
    try:
        await _with_flood_wait(app.get_chat, chat_id)
        return True
    except (UserDeactivated, AuthKeyUnregistered):
        _dead.add(session_name)
        return False
    except Exception:
        pass
    try:
        await _with_flood_wait(app.join_chat, str(chat_id))
        return True
    except UserNotParticipant:
        return True
    except ChannelPrivate:
        return True
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "channelprivate" in msg:
            return True
        print(f"[join_chat] {session_name}: {e}")
        return False


async def join_vc(session_name: str, chat_id: int, retry: int = 0) -> bool:
    if _is_invite_link(chat_id):
        # pehle join karo, phir VC join karo
        ok = await join_chat(session_name, chat_id)
        if not ok:
            return False
        # joined chat ka real ID nikaalo
        try:
            chat = await app.get_chat(chat_id.strip())
            chat_id = chat.id
        except Exception:
            return False
    if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
        chat_id = int(chat_id)
    if isinstance(chat_id, int) and chat_id > 0:
        chat_id = int(f"-100{chat_id}")
    call = _tgcalls.get(session_name)
    if call is None:
        ok = await start_client(session_name)
        if not ok:
            return False
        call = _tgcalls.get(session_name)
        if call is None:
            return False
    try:
        await call.play(chat_id, None)
        await call.mute(chat_id)
        _joined.setdefault(session_name, set()).add(chat_id)
        return True
    except NoActiveGroupCall:
        return False
    except NotInCallError:
        return False
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg:
            _joined.setdefault(session_name, set()).add(chat_id)
            try:
                await call.mute(chat_id)
            except Exception:
                pass
            return True
        if retry < _MAX_RETRIES and ("network" in msg or "timeout" in msg):
            await asyncio.sleep(2)
            return await join_vc(session_name, chat_id, retry + 1)
        print(f"[join_vc] {session_name} -> {chat_id}: {e}")
        return False


async def leave_vc(session_name: str, chat_id: int) -> bool:
    call = _tgcalls.get(session_name)
    if call:
        try:
            await call.leave_call(chat_id)
        except (NotInCallError, NoActiveGroupCall):
            pass
        except Exception:
            pass
    _joined.get(session_name, set()).discard(chat_id)
    return True


async def join_all_targets(session_name: str, targets: list) -> dict:
    results = {}
    for t in targets:
        chat_id = t.get("chat_id")
        joined_chat = await join_chat(session_name, chat_id)
        if not joined_chat:
            results[str(chat_id)] = False
            continue
        if not isinstance(chat_id, int):
            resolved = await _resolve_chat_id(session_name, chat_id)
            if resolved:
                chat_id = resolved
        joined_vc = await join_vc(session_name, chat_id)
        results[str(chat_id)] = joined_vc
    return results


async def join_all_accounts(targets: list) -> dict:
    results = {}
    for s in list(_clients.keys()):
        results[s] = await join_all_targets(s, targets)
        await asyncio.sleep(_JOIN_STAGGER)
    return results


async def is_in_call(session_name: str, chat_id: int) -> bool:
    call = _tgcalls.get(session_name)
    if call is None:
        return False
    try:
        calls = await call.calls
        return chat_id in calls
    except Exception:
        return chat_id in _joined.get(session_name, set())


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
                    cid = t.get("chat_id")
                    if not cid:
                        continue
                    try:
                        cid_int = int(cid)
                    except (TypeError, ValueError):
                        cid_int = await _resolve_chat_id(sname, cid)
                        if not cid_int:
                            continue
                    in_call = await is_in_call(sname, cid_int)
                    if not in_call:
                        try:
                            await join_chat(sname, cid_int)
                        except Exception:
                            pass
                        joined = await join_vc(sname, cid_int)
                        if joined:
                            print(f"[auto-rejoin] {sname} rejoined {cid_int}")
                    await asyncio.sleep(0.5)
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
        app = _clients[session_name]
    try:
        await app.get_me()
        return "alive"
    except (UserDeactivated, AuthKeyUnregistered):
        _dead.add(session_name)
        return "dead"
    except Exception:
        return "unknown"
