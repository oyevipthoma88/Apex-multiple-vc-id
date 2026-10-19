# VC Joiner Bot

A clean, professional Telegram bot that joins voice chats in your target groups, channels, and private/public chats and stays connected. Built with Pyrogram + PyTgCalls, MongoDB for storage, and a Flask keep-alive server for free-tier hosting.

## Features

- **Multiple account login** — add accounts via **String Session** or **phone + OTP + 2FA** login flow.
- **Unlimited target chats** — add any group/channel (public, private, or by chat ID) by link or ID.
- **Voice-chat joiner** — one tap to sit all accounts in target voice chats (muted).
- **Owner + authorized users** — only the owner and explicitly-added users can use the bot.
- **MongoDB persistence** — sessions, targets, and users are saved across restarts.
- **Web keep-alive** — built-in Flask server keeps free-tier hosting awake.

## Setup

### 1. Get Telegram API credentials
1. Go to https://my.telegram.org → API Development Tools.
2. Create an app. Copy `api_id` and `api_hash`.

### 2. Create the bot
1. Talk to [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Copy the **bot token**.

### 3. Get a MongoDB URI
- Free cluster at https://www.mongodb.com/atlas (MongoDB Atlas).
- Connection string looks like: `mongodb+srv://user:pass@cluster0.xxxx.mongodb.net`

### 4. Environment variables

| Variable      | Required | Example                          |
|---------------|----------|----------------------------------|
| `API_ID`      | Yes      | `12345678`                       |
| `API_HASH`    | Yes      | `abcd1234...`                    |
| `BOT_TOKEN`   | Yes      | `1234:abcd...`                   |
| `MONGO_URI`   | Yes      | `mongodb+srv://...`              |
| `OWNER_IDS`   | Yes      | `987654321` (space-separated)    |
| `DB_NAME`     | No       | `vcjoiner` (default)             |
| `SESSIONS_DIR`| No       | `sessions` (default)             |
| `PORT`        | No       | `8080` (default)                 |

### 5. Local run

```bash
pip install -r requirements.txt
python main.py
```

In Telegram, open your bot and press **/start**.

## Deploy to Render

1. Push this repo to a **private** GitHub repository.
2. In Render Dashboard → **New → Web Service** → connect the repo.
3. Render auto-detects `render.yaml`. Set the env vars in the dashboard:
   - `API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_URI`, `OWNER_IDS`
4. Deploy. The 1 GB disk persists `.session` files across restarts.

## Bot commands

| Command                    | Who    | Purpose                          |
|----------------------------|--------|----------------------------------|
| `/start`                   | All    | Open the menu                    |
| `/adduser <id>`            | Owner  | Authorize a user                 |
| `/deluser <id>`            | Owner  | Remove a user                    |
| `/delacc <name>`           | Owner  | Remove a saved account           |
| `/deltarget <id>`          | Owner  | Remove a target chat             |
| `/status`                  | Owner  | Show accounts/targets counts     |
| `/help`                    | Owner  | Command list                     |

Menu buttons: **Add Account (String)**, **Add Account (Login)**, **My Accounts**, **Add Target GC**, **Target List**, **Start VC Join**, **Stop VC Join**, **Manage Users**.

## Notes

- Voice-chat joining uses PyTgCalls with muted streams — accounts sit silently in the call.
- String sessions are the simplest way to add accounts (no OTP flow on the hosting side).
- This code is provided as-is for educational use. Ensure you comply with Telegram's Terms of Service.

© 2026 VC Joiner. All rights reserved.
