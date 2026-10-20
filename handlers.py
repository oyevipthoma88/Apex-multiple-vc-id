import hashlib

from pyrogram import Client, filters
try:
    from pyrogram.errors import (
        PhoneCodeInvalid, PhoneCodeExpired, PhoneCodeEmpty,
        SessionPasswordNeeded, PasswordHashInvalid,
    )
except ImportError:
    from pyrogram.errors import (
        PhoneCodeInvalid, PhoneCodeExpired,
        SessionPasswordNeeded, PasswordHashInvalid,
    )
    class PhoneCodeEmpty(Exception):
        pass
from pyrogram.types import (
    Message,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_IDS, SESSIONS_DIR, SUPPORT_GROUP
import database as db
import vcmanager

bot = Client(
    "vcjoiner_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=SESSIONS_DIR,
)

conv: dict = {}
phone_state: dict = {}
acct_select: dict = {}


def _is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


owner_filter = filters.create(
    lambda _, __, m: bool(m.from_user and m.from_user.id in OWNER_IDS)
)


async def is_allowed_user(user_id: int) -> bool:
    return True


def main_menu():
    return InlineKeyboardMarkup([
        [_btn("➕ Add String", callback_data="m:add_string", style="success"),
         _btn("➕ Add Login", callback_data="m:add_login", style="primary")],
        [_btn("👤 Accounts", callback_data="m:accounts"),
         _btn("🎯 Targets", callback_data="m:targets")],
        [_btn("➕ Add Target GC", callback_data="m:add_target", style="primary")],
        [_btn("▶️ Start All VC", callback_data="m:start_all", style="success"),
         _btn("⏹️ Stop All VC", callback_data="m:stop_all", style="danger")],
        [_btn("🤖 Auto Join: ON", callback_data="m:toggle_auto", style="success"),
         _btn("⚙️ Control Account", callback_data="m:control")],
        [_btn("📊 Status", callback_data="m:status"),
         _btn("📘 Tutorial", callback_data="m:tutorial"),
         _btn("👥 Users", callback_data="m:users")],
        [_btn("💬 Support", url=SUPPORT_GROUP, icon_custom_emoji_id=5443038326535759644, style="success")],
    ])

def main_menu_off():
    return InlineKeyboardMarkup([
        [_btn("➕ Add String", callback_data="m:add_string", style="success"),
         _btn("➕ Add Login", callback_data="m:add_login", style="primary")],
        [_btn("👤 Accounts", callback_data="m:accounts"),
         _btn("🎯 Targets", callback_data="m:targets")],
        [_btn("➕ Add Target GC", callback_data="m:add_target", style="primary")],
        [_btn("▶️ Start All VC", callback_data="m:start_all", style="success"),
         _btn("⏹️ Stop All VC", callback_data="m:stop_all", style="danger")],
        [_btn("🤖 Auto Join: OFF", callback_data="m:toggle_auto", style="danger"),
         _btn("⚙️ Control Account", callback_data="m:control")],
        [_btn("📊 Status", callback_data="m:status"),
         _btn("📘 Tutorial", callback_data="m:tutorial"),
         _btn("👥 Users", callback_data="m:users")],
        [_btn("💬 Support", url=SUPPORT_GROUP, icon_custom_emoji_id=5443038326535759644, style="success")],
    ])

def _normalize_chat_id(chat_id):
    """Auto-prepend -100 for positive group/channel IDs."""
    if isinstance(chat_id, int) and chat_id > 0:
        return int(f"-100{chat_id}")
    return chat_id

def _btn(text, **kwargs):
    """Safely create InlineKeyboardButton with ButtonStyle enum + emoji."""
    if "style" in kwargs and isinstance(kwargs["style"], str):
        try:
            from pyrogram.enums import ButtonStyle
            kwargs["style"] = getattr(ButtonStyle, kwargs["style"].upper())
        except (ImportError, AttributeError):
            kwargs.pop("style", None)
    if "icon_custom_emoji_id" in kwargs and kwargs["icon_custom_emoji_id"] is not None:
        try:
            kwargs["icon_custom_emoji_id"] = int(kwargs["icon_custom_emoji_id"])
        except (TypeError, ValueError):
            kwargs.pop("icon_custom_emoji_id", None)
    try:
        return InlineKeyboardButton(text, **kwargs)
    except (TypeError, ValueError):
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text, **kwargs)

def support_kb():
    return InlineKeyboardMarkup([[
        _btn(
            "Support",
            url=SUPPORT_GROUP,
            icon_custom_emoji_id=5443038326535759644,
            style="success",
        )
    ]])

def acct_kb(sessions: list):
    rows = []
    for s in sessions:
        name = s.get("session_name", str(s)) if isinstance(s, dict) else str(s)
        rows.append([InlineKeyboardButton(f"🆔 {name}", callback_data=f"acct:{name}")])
    rows.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")])
    return InlineKeyboardMarkup(rows)


def acct_action_kb(name: str):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🟢 Join VC", callback_data=f"ajoin:{name}"),
                InlineKeyboardButton("🔴 Leave VC", callback_data=f"aleave:{name}"),
            ],
            [
                InlineKeyboardButton("🟡 Restart", callback_data=f"arestart:{name}"),
                _btn("⚫ Delete", callback_data=f"adelete:{name}", style="danger"),
            ],
            [InlineKeyboardButton("🔵 Back", callback_data="back_acct")],
        ]
    )


def target_kb(targets: list):
    rows = []
    for t in targets:
        title = t.get("title", str(t.get("chat_id")))[:30]
        rows.append(
            [InlineKeyboardButton(f"🎯 {title}", callback_data=f"tdel:{t.get('chat_id')}")]
        )
    rows.append([InlineKeyboardButton("🔵 Back", callback_data="back_menu")])
    return InlineKeyboardMarkup(rows)


@bot.on_message(filters.command("start"))
async def start_cmd(_, m: Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    if uid in OWNER_IDS:
        role = "🛡️ **Owner**"
    else:
        role = "👤 **User**"
    await db.add_user(uid)
    await m.reply(
        f"**VC Joiner Bot**\n\n"
        f"Welcome! Role: {role}\n\n"
        f"• Add accounts via string or login\n"
        f"• Add target groups/channels\n"
        f"• Start VC join — accounts sit muted\n"
        f"• Auto-join re-enters calls if they end\n\n"
        f"Use the menu below 👇",
        reply_markup=main_menu(),
    )


@bot.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    if not m.from_user or not await is_allowed_user(m.from_user.id):
        return
    await _help_text(m)


async def _help_text(m: Message):
    await m.reply(
        "**VC Joiner — Commands**\n\n"
        "/start — Open menu\n"
        "/status — Bot health & stats\n"
        "/health — Same as status\n"
        "/help — This message\n\n"
        "**Owner commands:**\n"
        "/adduser <id> — Add authorized user\n"
        "/deluser <id> — Remove user\n"
        "/delacc <name> — Delete an account\n"
        "/deltarget <id> — Delete a target\n\n"
        "**Menu buttons** let you do everything without commands."
    )
    await m.reply("Need help? Join support 👇", reply_markup=support_kb())


@bot.on_message(filters.command("health"))
async def health_cmd(_, m: Message):
    if not m.from_user or not await is_allowed_user(m.from_user.id):
        return
    await _status_text(m)


@bot.on_message(filters.command("status"))
async def status_cmd(_, m: Message):
    if not m.from_user or not await is_allowed_user(m.from_user.id):
        return
    await _status_text(m)


async def _status_text(m: Message):
    sessions = await db.list_sessions()
    targets = await db.list_targets()
    active = vcmanager.active_accounts()
    users = await db.list_users()
    auto = "ON ✅" if vcmanager.auto_rejoin_enabled() else "OFF ❌"
    dead = vcmanager.dead_accounts()
    text = (
        f"**📊 Bot Health**\n\n"
        f"**Accounts saved:** {len(sessions)}\n"
        f"**Accounts active:** {len(active)}\n"
        f"**Dead sessions:** {len(dead)}\n"
        f"**Targets:** {len(targets)}\n"
        f"**Total users:** {len(users)}\n"
        f"**Auto-rejoin:** {auto}\n\n"
    )
    if active:
        text += "**Active:**\n" + "\n".join(f"• `{a}`" for a in active) + "\n"
    if dead:
        text += "\n**⚠️ Dead (need re-login):**\n" + "\n".join(f"• `{a}`" for a in dead)
    if not active and not dead:
        text += "No accounts."
    await m.reply(text)


async def _cleanup_login(uid=None, *args, **kwargs):
    if not isinstance(uid, int):
        for a in args:
            fu = getattr(a, "from_user", None)
            if fu and getattr(fu, "id", None):
                uid = fu.id
                break
        if not isinstance(uid, int) and hasattr(uid, "from_user") and uid.from_user:
            uid = uid.from_user.id
    if not isinstance(uid, int):
        return
    st = phone_state.get(uid)
    if st and st.get("app"):
        try:
            await st["app"].disconnect()
        except Exception:
            pass
    phone_state.pop(uid, None)
    conv.pop(uid, None)
    acct_select.pop(uid, None)

@bot.on_message(filters.private & filters.text, group=1)
async def menu_router(client: Client, m: Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    if not await is_allowed_user(uid):
        return
    text = m.text.strip()

    if text == "/cancel":
        conv.pop(uid, None)
        phone_state.pop(uid, None)
        acct_select.pop(uid, None)
        await m.reply("Cancelled.", reply_markup=main_menu())
        return

    if text == "➕ Add String":
        await m.reply(
            "Send the **String Session**.\n"
            "Generate one with @StringSessionGen_Bot or similar.\n\n"
            "Send /cancel to abort."
        )
        conv[uid] = "await_string"

    elif text == "➕ Add Login":
        await m.reply(
            "Send the **phone number** with country code.\nExample: `+919876543210`\n\nSend /cancel to abort."
        )
        conv[uid] = "await_phone"

    elif text == "📋 Accounts":
        sessions = await db.list_sessions()
        if not sessions:
            await m.reply("No accounts yet. Add one with the menu.")
            return
        lines = []
        for s in sessions:
            name = s["session_name"] if isinstance(s, dict) else s
            if name in vcmanager._dead:
                status = "❌"
            elif name in vcmanager._clients:
                status = "🟢"
            else:
                status = "⚪"
            lines.append(f"{status} `{name}`")
        await m.reply("**Your Accounts:**\n" + "\n".join(lines))

    elif text == "🎯 Targets":
        targets = await db.list_targets()
        if not targets:
            await m.reply("No targets yet. Use **Add Target GC** button.")
            return
        lines = []
        for t in targets:
            title = t.get("title", str(t.get("chat_id")))[:40]
            lines.append(f"• **{title}**\n  `{t.get('chat_id')}`")
        await m.reply("**Target Chats:**\n" + "\n".join(lines))

    elif text == "➕ Add Target GC":
        await m.reply(
            "Send the **target link or chat ID**.\n\n"
            "Examples:\n`https://t.me/xxxxx`\n`-1001234567890`\n\nSend /cancel to abort."
        )
        conv[uid] = "await_target"

    elif text == "▶️ Start All VC":
        sessions = await db.list_sessions()
        targets = await db.list_targets()
        if not sessions:
            await m.reply("Add at least one account first.")
            return
        if not targets:
            await m.reply("Add at least one target first.")
            return
        msg = await m.reply("⏳ Starting accounts and joining voice chats...")
        total = 0
        failed_accounts = []
        for i, s in enumerate(sessions, 1):
            sname = s["session_name"] if isinstance(s, dict) else s
            sstr = s.get("session_string", "") if isinstance(s, dict) else ""
            await msg.edit(f"⏳ Joining...\nAccount {i}/{len(sessions)}: `{sname}`")
            await vcmanager.start_client(sname, sstr)
            res = await vcmanager.join_all_targets(sname, targets)
            ok_count = sum(1 for v in res.values() if v)
            total += ok_count
            if ok_count == 0:
                failed_accounts.append(sname)
            import asyncio as _a
            await _a.sleep(2.5)
        await vcmanager.start_rejoin_loop()
        report = (
            f"✅ **VC Join complete**\n"
            f"Accounts: {len(sessions)}\n"
            f"Targets: {len(targets)}\n"
            f"Successful joins: {total}\n"
        )
        if failed_accounts:
            report += f"⚠️ Failed: {', '.join(f'`{a}`' for a in failed_accounts)}"
        await msg.edit(report)

    elif text == "⏹️ Stop All VC":
        await vcmanager.stop_all()
        await m.reply("⏹️ All accounts stopped and left voice chats.")

    elif text in ("🤖 Auto Join: ON", "🤖 Auto Join: OFF"):
        cur = vcmanager.auto_rejoin_enabled()
        await vcmanager.set_auto_rejoin(not cur)
        new_state = not cur
        await m.reply(
            f"🤖 Auto-rejoin is now **{'ON ✅' if new_state else 'OFF ❌'}**.\n"
            + ("If a voice chat ends, accounts will automatically rejoin when a new call starts."
               if new_state else "Accounts will no longer auto-rejoin."),
            reply_markup=main_menu() if new_state else main_menu_off(),
        )

    elif text == "🎯 Control Account":
        sessions = await db.list_sessions()
        if not sessions:
            await m.reply("No accounts to control.")
            return
        await m.reply("Pick an account to control:", reply_markup=acct_kb(sessions))

    elif text == "📊 Status":
        await _status_text(m)

    elif text == "📚 Tutorial":
        await _tutorial(m)

    elif text == "👤 Users":
        if not _is_owner(uid):
            await m.reply("Owner only.")
            return
        users = await db.list_users()
        await m.reply(
            "**Authorized Users (besides owner):**\n"
            + ("\n".join(f"• `{u}`" for u in users) if users else "None added.")
            + "\n\nCommands:\n`/adduser <id>`\n`/deluser <id>`"
        )

    else:
        await _conv_handler(client, m)


async def _conv_handler(client: Client, m: Message):
    uid = m.from_user.id
    state = conv.get(uid)
    if not state:
        return
    text = m.text.strip()
    if text == "/cancel":
        await _cleanup_login(uid)
        await m.reply("Cancelled.", reply_markup=main_menu())
        return

    if state == "await_string":
        name = "acc_" + hashlib.md5(text.encode()).hexdigest()[:8]
        await db.add_session(name, "string", text)
        ok = await vcmanager.start_client(name, text)
        await m.reply(
            f"{'✅' if ok else '⚠️'} String session saved as `{name}`.\n"
            + ("Account started." if ok else "Failed to start — check logs."),
            reply_markup=main_menu(),
        )
        conv.pop(uid, None)

    elif state == "await_phone":
        phone = text
        name = "acc_" + hashlib.md5(phone.encode()).hexdigest()[:8]
        app = Client(
            name,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=SESSIONS_DIR,
            in_memory=False,
        )
        await app.connect()
        try:
            sent_code = await app.send_code(phone)
        except Exception as e:
            try:
                await app.disconnect()
            except Exception:
                pass
            await m.reply(f"Failed to send code: {e}", reply_markup=main_menu())
            conv.pop(uid, None)
            return
        conv[uid] = "await_code"
        phone_state[uid] = {
            "app": app,
            "phone": phone,
            "code_hash": sent_code.phone_code_hash,
            "name": name,
        }
        await m.reply("Send the **login code** you just received.")

    elif state == "await_code":
        st = phone_state.get(uid)
        if not st:
            await m.reply("Session expired. Try again.")
            conv.pop(uid, None)
            return
        try:
            await st["app"].sign_in(st["phone"], st["code_hash"], text)
            session_string = await st["app"].export_session_string()
            await st["app"].disconnect()
            await db.add_session(st["name"], st["phone"], session_string)
            await vcmanager.start_client(st["name"], session_string)
            await m.reply(
                f"✅ Logged in and saved as `{st['name']}`.",
                reply_markup=main_menu(),
            )
        except Exception as e:
            if "PASSWORD" in str(e):
                conv[uid] = "await_2fa"
                await m.reply("2FA enabled. Send your **cloud password**.")
                return
            await m.reply(f"Login failed: {e}", reply_markup=main_menu())
        phone_state.pop(uid, None)
        conv.pop(uid, None)

    elif state == "await_2fa":
        st = phone_state.get(uid)
        if not st:
            await m.reply("Session expired.")
            conv.pop(uid, None)
            return
        try:
            await st["app"].check_password(text)
            session_string = await st["app"].export_session_string()
            await st["app"].disconnect()
            await db.add_session(st["name"], st["phone"], session_string)
            await vcmanager.start_client(st["name"], session_string)
            await m.reply(
                f"✅ Logged in (2FA) and saved as `{st['name']}`.",
                reply_markup=main_menu(),
            )
        except Exception as e:
            await m.reply(f"2FA failed: {e}", reply_markup=main_menu())
        finally:
            phone_state.pop(uid, None)
            conv.pop(uid, None)
            try:
                await st["app"].disconnect()
            except Exception:
                pass

    elif state == "await_target":
        target = text.strip()
        if target.isdigit():
            target = f"-100{target}"
        chat_id = None
        title = target
        try:
            app = None
            if vcmanager._clients:
                app = next(iter(vcmanager._clients.values()))
            if app and app.is_connected:
                chat = await app.get_chat(target)
                chat_id = chat.id
                title = chat.title or chat.first_name or str(chat.id)
        except Exception:
            try:
                chat_id = _normalize_chat_id(int(target))
            except Exception:
                await m.reply(
                    "Could not resolve that target.\nSend a valid link or numeric chat ID.",
                    reply_markup=main_menu(),
                )
                conv.pop(uid, None)
                return
        if chat_id is None:
            chat_id = target
        await db.add_target(chat_id, title, target)
        await m.reply(
            f"✅ Target added: **{title}**\n`{target}`",
            reply_markup=main_menu(),
        )
        conv.pop(uid, None)


@bot.on_callback_query()
async def callback_handler(client: Client, cq):
    if not cq.from_user:
        return
    uid = cq.from_user.id
    if not await is_allowed_user(uid):
        await cq.answer("Not authorized.", show_alert=True)
        return
    data = cq.data
    if data == "m:accounts":
        sessions = await db.list_sessions()
        await cq.answer()
        await cq.message.edit_text("👤 **Accounts:**", reply_markup=acct_kb(sessions) if sessions else main_menu())
        return
    if data == "m:targets":
        targets = await db.list_targets()
        await cq.answer()
        txt = "🎯 **Targets:**\n\n" + ("\n".join(f"• `{t}`" for t in targets) if targets else "None")
        await cq.message.edit_text(txt, reply_markup=main_menu())
        return

    # ── Inline menu callbacks ──
    if data == "m:add_string":
        conv[uid] = "await_string"
        await cq.message.edit_text("🔗 Send your **Pyrogram string session**.")
        await cq.answer()
        return
    if data == "m:add_login":
        conv[uid] = "await_phone"
        await cq.message.edit_text("📱 Send your **phone number** with country code (e.g. +91...).")
        await cq.answer()
        return
    if data == "m:add_target":
        conv[uid] = "await_target"
        await cq.message.edit_text(
            "🎯 Send the **target link or chat ID**.\n\n"
            "Examples:\n`https://t.me/xxxxx`\n`-1001234567890`\n\n"
            "⚠️ Account ko pehle us channel me join hona chahiye."
        )
        await cq.answer()
        return
    if data == "m:start_all":
        sessions = await db.list_sessions()
        targets = await db.list_targets()
        if not sessions or not targets:
            await cq.answer("Add account + target first.", show_alert=True)
            return
        await cq.answer("Starting...")
        await cq.message.edit_text("⏳ Joining all targets...")
        total = 0
        failed = []
        for i, sess in enumerate(sessions, 1):
            sname = sess["session_name"] if isinstance(sess, dict) else sess
            sstr = sess.get("session_string", "") if isinstance(sess, dict) else ""
            await vcmanager.start_client(sname, sstr)
            res = await vcmanager.join_all_targets(sname, targets)
            ok = sum(1 for v in res.values() if v)
            total += ok
            if ok < len(targets):
                failed.append(sname)
        await cq.message.edit_text(
            f"✅ Joined **{total}** VCs.\n"
            + (f"⚠️ Failed: {', '.join(failed)}" if failed else ""),
            reply_markup=main_menu(),
        )
        return
    if data == "m:stop_all":
        await vcmanager.stop_all()
        await cq.message.edit_text("⏹️ All accounts stopped.", reply_markup=main_menu())
        await cq.answer()
        return
    if data == "m:toggle_auto":
        cur = vcmanager.auto_rejoin_enabled()
        await vcmanager.set_auto_rejoin(not cur)
        new_state = not cur
        await cq.message.edit_text(
            f"🤖 Auto-rejoin: **{'ON ✅' if new_state else 'OFF ❌'}**",
            reply_markup=main_menu() if new_state else main_menu_off(),
        )
        await cq.answer()
        return
    if data == "m:control":
        sessions = await db.list_sessions()
        if not sessions:
            await cq.answer("No accounts.", show_alert=True)
            return
        await cq.message.edit_text("Pick an account:", reply_markup=acct_kb(sessions))
        await cq.answer()
        return
    if data == "m:status":
        await cq.answer()
        await _status_text(cq.message)
        return
    if data == "m:tutorial":
        await cq.answer()
        await _tutorial(cq.message)
        return
    if data == "m:users":
        await cq.answer()
        users = await db.list_users()
        await cq.message.edit_text(
            "**Authorized Users:**\n"
            + ("\n".join(f"• `{u}`" for u in users) if users else "None added."),
            reply_markup=main_menu(),
        )
        return

    if data.startswith("acct:"):
        name = data.split(":", 1)[1]
        acct_select[uid] = name
        joined = vcmanager.joined_targets(name)
        if name in vcmanager._dead:
            status = "❌ Dead session"
        elif name in vcmanager._clients:
            status = "🟢 Active"
        else:
            status = "⚪ Inactive"
        await cq.message.edit_text(
            f"**Account:** `{name}`\n**Status:** {status}\n**Joined VCs:** {len(joined)}",
            reply_markup=acct_action_kb(name),
        )
        await cq.answer()

    elif data.startswith("ajoin:"):
        name = data.split(":", 1)[1]
        targets = await db.list_targets()
        if not targets:
            await cq.answer("No targets set.", show_alert=True)
            return
        sess = await db.get_session(name)
        sstr = sess.get("session_string", "") if sess else ""
        await vcmanager.start_client(name, sstr)
        await cq.answer("Joining...")
        res = await vcmanager.join_all_targets(name, targets)
        ok = sum(1 for v in res.values() if v)
        await cq.message.edit_text(
            f"**Account:** `{name}`\nJoined {ok}/{len(targets)} voice chats.",
            reply_markup=acct_action_kb(name),
        )

    elif data.startswith("aleave:"):
        name = data.split(":", 1)[1]
        joined = vcmanager.joined_targets(name)
        for cid in joined:
            await vcmanager.leave_vc(name, cid)
        await cq.answer("Left all VCs.")
        await cq.message.edit_text(
            f"**Account:** `{name}`\nLeft all voice chats.",
            reply_markup=acct_action_kb(name),
        )

    elif data.startswith("arestart:"):
        name = data.split(":", 1)[1]
        sess = await db.get_session(name)
        sstr = sess.get("session_string", "") if sess else ""
        await cq.answer("Restarting...")
        await vcmanager.stop_client(name)
        ok = await vcmanager.start_client(name, sstr)
        await cq.message.edit_text(
            f"**Account:** `{name}`\n{'✅ Restarted' if ok else '❌ Failed'}",
            reply_markup=acct_action_kb(name),
        )

    elif data.startswith("adelete:"):
        name = data.split(":", 1)[1]
        await vcmanager.stop_client(name)
        await db.remove_session(name)
        import os
        for ext in (".session", ".session-journal"):
            p = os.path.join(SESSIONS_DIR, name + ext)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        await cq.answer("Deleted.")
        await cq.message.edit_text(f"🗑 Account `{name}` deleted.")

    elif data == "back_acct":
        sessions = await db.list_sessions()
        if not sessions:
            await cq.message.edit_text("No accounts.")
            await cq.answer()
            return
        await cq.message.edit_text("**🆔 Pick an account to control:**", reply_markup=acct_kb(sessions))
        await cq.answer()

    elif data == "back_menu":
        await cq.message.delete()
        await cq.answer()

    elif data.startswith("tdel:"):
        cid_raw = data.split(":", 1)[1]
        try:
            cid = int(cid_raw)
        except Exception:
            cid = cid_raw
        await db.remove_target(cid)
        await cq.answer("Target removed.")
        targets = await db.list_targets()
        if targets:
            await cq.message.edit_text("Targets (tap to remove):", reply_markup=target_kb(targets))
        else:
            await cq.message.edit_text("No targets left.")


async def _tutorial(m: Message):
    await m.reply(
        "**📚 Tutorial — VC Joiner Bot**\n\n"
        "**Step 1 — Add an account**\n"
        "Tap **➕ Add String** and paste a Pyrogram string session.\n"
        "Or tap **➕ Add Login** and enter a phone number → OTP → 2FA.\n\n"
        "**Step 2 — Add targets**\n"
        "Tap **➕ Add Target GC** and send a group/channel link or chat ID.\n"
        "Works on public, private, groups, and channels.\n\n"
        "**Step 3 — Start VC join**\n"
        "Tap **▶️ Start All VC**. Every account joins every target voice chat (muted).\n\n"
        "**Step 4 — Auto-rejoin**\n"
        "Toggle **🤖 Auto Join** ON. If a call ends and a new one starts, accounts rejoin automatically.\n\n"
        "**Step 5 — Control a single account**\n"
        "Tap **🎯 Control Account**, pick one, then join/leave/restart/delete it.\n\n"
        "**Step 6 — Owner tools**\n"
        "Owner can use `/adduser`, `/deluser`, `/delacc`, `/deltarget`.\n\n"
        "**Tips**\n"
        "• `/status` shows health and counts.\n"
        "• String sessions are easiest for hosting.\n"
        "• Keep your API credentials private."
    )


@bot.on_message(filters.command("adduser") & owner_filter)
async def adduser_cmd(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply("Usage: `/adduser <user_id>`")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await m.reply("User ID must be a number.")
        return
    ok = await db.add_user(uid)
    await m.reply("✅ User added." if ok else "User already exists.")


@bot.on_message(filters.command("deluser") & owner_filter)
async def deluser_cmd(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply("Usage: `/deluser <id>`")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await m.reply("User ID must be a number.")
        return
    ok = await db.remove_user(uid)
    await m.reply("✅ User removed." if ok else "User not found.")


@bot.on_message(filters.command("delacc") & owner_filter)
async def delacc_cmd(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply("Usage: `/delacc <name>`")
        return
    name = parts[1]
    await vcmanager.stop_client(name)
    await db.remove_session(name)
    import os
    for ext in (".session", ".session-journal"):
        p = os.path.join(SESSIONS_DIR, name + ext)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    await m.reply(f"✅ Account `{name}` removed.")


@bot.on_message(filters.command("deltarget") & owner_filter)
async def deltarget_cmd(_, m: Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply("Usage: `/deltarget <chat_id>`")
        return
    try:
        cid = int(parts[1])
    except ValueError:
        cid = parts[1]
    ok = await db.remove_target(cid)
    await m.reply("✅ Target removed." if ok else "Target not found.")
