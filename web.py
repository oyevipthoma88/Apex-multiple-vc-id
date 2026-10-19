import threading
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VC Joiner Bot</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center}
  .card{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:48px 40px;text-align:center;max-width:520px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.4)}
  .dot{width:14px;height:14px;border-radius:50%;background:#22c55e;margin:0 auto 20px;box-shadow:0 0 16px #22c55e;animation:p 1.6s infinite}
  @keyframes p{0%,100%{opacity:1}50%{opacity:.35}}
  h1{font-size:26px;margin-bottom:8px;letter-spacing:.3px}
  p{color:#94a3b8;font-size:15px;line-height:1.6;margin-bottom:6px}
  .tag{display:inline-block;margin-top:16px;padding:6px 14px;background:#0f172a;border:1px solid #334155;border-radius:999px;font-size:12px;color:#64748b}
</style>
</head>
<body>
<div class="card">
  <div class="dot"></div>
  <h1>VC Joiner Bot</h1>
  <p>Voice-chat joiner service is online.</p>
  <p>Configure via your Telegram bot in the app.</p>
  <span class="tag">Powered by Pyrogram + PyTgCalls</span>
</div>
</body>
</html>"""


@app.route("/")
def home():
    return render_template_string(PAGE)


@app.route("/health")
def health():
    import vcmanager
    import database as db_sync
    return jsonify(
        status="ok",
        active_accounts=len(vcmanager.active_accounts()),
        auto_rejoin=vcmanager.auto_rejoin_enabled(),
    )


def run_web(port: int):
    app.run(host="0.0.0.0", port=port)


def start_in_thread(port: int):
    t = threading.Thread(target=run_web, args=(port,), daemon=True)
    t.start()
