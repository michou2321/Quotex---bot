import os
import json
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from pyquotex.stable_api import Quotex
from telethon import TelegramClient
from telethon.sessions import StringSession
import random

app = Flask(__name__)

# Environment variables
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL = os.getenv("CHANNEL")
SESSION_STRING = os.getenv("SESSION_STRING")

# Bot state
bot_state = {
    "running": False,
    "status": "متوقف",
    "balance": 0.0,
    "trades": 0,
    "wins": 0,
    "losses": 0,
    "win_rate": 0,
    "signals": [],
    "log": []
}

bot_thread = None
stop_event = threading.Event()
ASSETS = ["NZDCHF_otc", "USDINR_otc", "USDBDT_otc", "USDARS_otc", "USDPKR_otc"]
BASE_AMOUNT = 1.0

def add_log(msg):
    """Add message to log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    bot_state["log"].append(log_msg)
    if len(bot_state["log"]) > 50:
        bot_state["log"] = bot_state["log"][-50:]
    print(log_msg)

def update_stats():
    """Update win rate"""
    total = bot_state["wins"] + bot_state["losses"]
    if total > 0:
        bot_state["win_rate"] = int((bot_state["wins"] / total) * 100)

async def decide_direction(client, asset):
    """Decide CALL or PUT"""
    try:
        # Simple analysis (can be enhanced)
        return random.choice(["call", "put"])
    except:
        return random.choice(["call", "put"])

async def run_bot():
    """Main bot loop"""
    add_log("🚀 تشغيل البوت...")
    bot_state["running"] = True
    bot_state["status"] = "شغّال"
    
    max_retries = 10
    client = None
    tg = None
    
    # Connect to Quotex
    for attempt in range(max_retries):
        try:
            add_log(f"📡 محاولة الاتصال {attempt + 1}/{max_retries}...")
            client = Quotex(email=EMAIL, password=PASSWORD, lang="en")
            client.set_account_mode("PRACTICE")
            
            connected, reason = await client.connect()
            if connected:
                add_log("✅ متصل بـ Quotex!")
                break
            else:
                add_log(f"⚠️ فشل الاتصال: {reason}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(30 + (attempt * 10))
        except Exception as e:
            add_log(f"❌ خطأ: {str(e)[:80]}")
            if attempt < max_retries - 1:
                await asyncio.sleep(30 + (attempt * 10))
    
    if not client:
        add_log("❌ فشل الاتصال بـ Quotex بعد المحاولات!")
        bot_state["running"] = False
        bot_state["status"] = "متوقف (فشل الاتصال)"
        return
    
    try:
        await client.change_account("PRACTICE")
        bot_state["balance"] = float(await client.get_balance())
        add_log(f"💰 الرصيد: ${bot_state['balance']:.2f}")
    except:
        pass
    
    # Connect to Telegram
    try:
        tg = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await tg.start()
        add_log(f"✅ متصل بـ Telegram!")
        await tg.send_message(CHANNEL, "🚀 بدء تشغيل البوت")
    except Exception as e:
        add_log(f"⚠️ خطأ في Telegram: {e}")
    
    # Main loop
    while bot_state["running"] and not stop_event.is_set():
        try:
            asset = random.choice(ASSETS)
            direction = await decide_direction(client, asset)
            
            now = datetime.now()
            time_str = now.strftime("%H:%M:%S")
            
            # Add signal
            signal = {
                "asset": asset.upper(),
                "direction": "CALL" if direction == "call" else "PUT",
                "entry": "M1",
                "time": time_str,
                "result": "pending",
                "profit": None
            }
            
            bot_state["signals"].insert(0, signal)
            if len(bot_state["signals"]) > 20:
                bot_state["signals"] = bot_state["signals"][:20]
            
            add_log(f"📊 إشارة جديدة: {asset.upper()} {signal['direction']}")
            
            # Try to trade
            try:
                success, order_info = await client.buy(
                    BASE_AMOUNT, asset, direction, 60, time_mode="TIME"
                )
                
                if success:
                    bot_state["trades"] += 1
                    add_log(f"✅ صفقة مفتوحة #{bot_state['trades']}")
                    
                    # Wait for result
                    await asyncio.sleep(70)
                    
                    # Check result
                    try:
                        history = await client.get_history()
                        if history and "data" in history:
                            for trade in history["data"]:
                                if str(trade.get("id")) == str(order_info.get("id")):
                                    result = "win" if float(trade.get("profit", 0)) > 0 else "loss"
                                    profit = float(trade.get("profit", 0))
                                    
                                    if result == "win":
                                        bot_state["wins"] += 1
                                        add_log(f"🟢 ربح! +${profit:.2f}")
                                    else:
                                        bot_state["losses"] += 1
                                        add_log(f"🔴 خسارة! ${profit:.2f}")
                                    
                                    signal["result"] = result
                                    signal["profit"] = profit
                                    update_stats()
                                    break
                    except:
                        pass
                else:
                    signal["result"] = "fail"
                    add_log(f"❌ فشلت الصفقة")
            
            except Exception as e:
                add_log(f"⚠️ خطأ في الصفقة: {str(e)[:60]}")
                signal["result"] = "fail"
            
            # Try to get balance
            try:
                bot_state["balance"] = float(await client.get_balance())
            except:
                pass
            
            # Wait before next trade
            await asyncio.sleep(random.randint(30, 60))
            
        except Exception as e:
            add_log(f"❌ خطأ عام: {str(e)[:60]}")
            await asyncio.sleep(10)
    
    bot_state["running"] = False
    bot_state["status"] = "متوقف"
    add_log("🛑 توقف البوت")

def bot_thread_func():
    """Run bot in thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

# HTML Template (from your file)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
<title>LATCHI DZ — لوحة التحكم</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet" />
<style>
  :root {
    --bg: #0b1220;
    --card: #131c2e;
    --line: #1f2b44;
    --text: #e7ecf3;
    --muted: #93a0b8;
    --green: #16a34a;
    --green-2: #22c55e;
    --red: #ef4444;
    --red-2: #dc2626;
    --gold: #facc15;
    --header: #126b3d;
    --header-2: #0f5d35;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0;
    background: var(--bg);
    color: var(--text);
    font-family: 'Cairo', system-ui, -apple-system, Segoe UI, Tahoma, Arial;
  }
  .app { max-width: 540px; margin: 0 auto; min-height: 100vh; padding-bottom: 32px; }
  .header {
    background: linear-gradient(180deg, var(--header) 0%, var(--header-2) 100%);
    padding: 22px 18px 18px;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .header .title { text-align: left; }
  .header h1 { margin: 0; font-size: 22px; font-weight: 800; }
  .header .sub { margin-top: 4px; color: #c8e6d3; font-size: 14px; font-weight: 600; }
  .clock { text-align: right; color: #ffffff; }
  .clock .label { font-size: 12px; color: #c8e6d3; }
  .clock .time { font-size: 22px; font-weight: 800; }
  .stack { padding: 14px; display: flex; flex-direction: column; gap: 12px; }
  .card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 16px;
  }
  .card .row { display:flex; justify-content: space-between; align-items: center; }
  .card .label { color: var(--muted); font-size: 14px; font-weight: 600; }
  .status-card .dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: #6b7280;
  }
  .status-card.is-running .dot { background: var(--green-2); animation: pulse 1.4s infinite; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.6); }
    70% { box-shadow: 0 0 0 10px rgba(34,197,94,0); }
    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
  }
  .status-text { font-weight: 700; font-size: 18px; }
  .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
  .btn {
    border: 0; cursor: pointer; padding: 14px 16px; border-radius: 12px;
    font-family: inherit; font-weight: 800; font-size: 16px;
    color: #fff; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .btn-stop { background: linear-gradient(180deg, #ef4444, #dc2626); }
  .btn-start { background: linear-gradient(180deg, #22c55e, #16a34a); }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .stat .label { font-size: 14px; color: var(--muted); margin-bottom: 6px; }
  .stat .value { font-size: 26px; font-weight: 800; font-variant-numeric: tabular-nums; }
  .stat.balance .value { color: var(--green-2); }
  .stat.win .value { color: var(--green-2); }
  .stat.loss .value { color: #f87171; }
  .stat.rate .value { color: var(--gold); }
  .log-box {
    background: #0a1020; border: 1px solid var(--line); border-radius: 10px;
    padding: 10px; max-height: 280px; overflow-y: auto;
    font-family: 'Courier New', monospace; font-size: 12px;
    direction: ltr; text-align: left;
  }
  .log-line { padding: 3px 4px; border-bottom: 1px dashed #1a2236; color: #cbd5e1; }
  .toast {
    position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
    background: #1e293b; color: #fff; padding: 10px 16px; border-radius: 10px;
    border: 1px solid var(--line); font-size: 14px; opacity: 0;
    transition: opacity .25s ease; z-index: 99;
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
  <div class="app">
    <header class="header">
      <div class="clock">
        <div class="label">توقيت الجزائر</div>
        <div class="time" id="clock">--:--:--</div>
      </div>
      <div class="title">
        <h1>LATCHI DZ ⚡</h1>
        <div class="sub">بوت Quotex × Telegram</div>
      </div>
    </header>

    <div class="stack">
      <div class="card status-card" id="statusCard">
        <div class="row">
          <div class="label">الحالة</div>
          <div style="display:flex; align-items: center; gap: 10px;">
            <span class="status-text" id="statusText">متوقف</span>
            <span class="dot"></span>
          </div>
        </div>
        <div class="controls">
          <button class="btn btn-stop" id="btnStop">■ إيقاف</button>
          <button class="btn btn-start" id="btnStart">▶ تشغيل</button>
        </div>
      </div>

      <div class="grid-2">
        <div class="card stat balance">
          <div class="label">الرصيد</div>
          <div class="value">$ <span id="balance">0.00</span></div>
        </div>
        <div class="card stat">
          <div class="label">صفقات</div>
          <div class="value" id="trades">0</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card stat win">
          <div class="label">رابحة</div>
          <div class="value" id="wins">0</div>
        </div>
        <div class="card stat loss">
          <div class="label">خاسرة</div>
          <div class="value" id="losses">0</div>
        </div>
      </div>

      <div class="card stat rate">
        <div class="label">نسبة النجاح</div>
        <div class="value"><span id="rate">0</span>%</div>
      </div>

      <div class="card">
        <div style="margin-bottom: 10px;">
          <h3 style="margin: 0; font-size: 16px;">📜 السجل</h3>
        </div>
        <div class="log-box" id="logBox">
          <div style="color: #93a0b8; text-align: center; padding: 12px 0;">في انتظار التشغيل...</div>
        </div>
      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>

<script>
  const $ = (id) => document.getElementById(id);

  function fmtClock() {
    const now = new Date();
    const opts = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    $('clock').textContent = new Intl.DateTimeFormat('en-GB', opts).format(now);
  }
  setInterval(fmtClock, 1000); fmtClock();

  function showToast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => t.classList.remove('show'), 2200);
  }

  function render(state) {
    $('statusText').textContent = state.status || '—';
    $('balance').textContent = (state.balance || 0).toFixed(2);
    $('trades').textContent = state.trades || 0;
    $('wins').textContent = state.wins || 0;
    $('losses').textContent = state.losses || 0;
    $('rate').textContent = state.win_rate || 0;

    const card = $('statusCard');
    card.classList.toggle('is-running', !!state.running);

    $('btnStart').disabled = !!state.running;
    $('btnStop').disabled = !state.running;

    const logBox = $('logBox');
    if (state.log && state.log.length) {
      logBox.innerHTML = state.log.slice().reverse().map(l => `<div class="log-line">${l}</div>`).join('');
      logBox.scrollTop = logBox.scrollHeight;
    } else {
      logBox.innerHTML = '<div style="color: #93a0b8; text-align: center; padding: 12px 0;">في انتظار التشغيل...</div>';
    }
  }

  async function refresh() {
    try {
      const r = await fetch('/api/state');
      const data = await r.json();
      render(data);
    } catch (e) { console.error(e); }
  }

  async function postJson(url) {
    const r = await fetch(url, { method: 'POST' });
    return r.json();
  }

  $('btnStart').addEventListener('click', async () => {
    $('btnStart').disabled = true;
    const res = await postJson('/api/start');
    showToast(res.ok ? 'تم تشغيل البوت' : 'البوت يعمل بالفعل');
    refresh();
  });

  $('btnStop').addEventListener('click', async () => {
    $('btnStop').disabled = true;
    const res = await postJson('/api/stop');
    showToast(res.ok ? 'جاري الإيقاف...' : 'البوت متوقف بالفعل');
    refresh();
  });

  refresh();
  setInterval(refresh, 2000);
</script>
</body>
</html>'''

# API Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/state')
def get_state():
    return jsonify(bot_state)

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_thread
    
    if bot_state["running"]:
        return jsonify({"ok": False, "state": bot_state})
    
    stop_event.clear()
    bot_thread = threading.Thread(target=bot_thread_func, daemon=True)
    bot_thread.start()
    
    return jsonify({"ok": True, "state": bot_state})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    if not bot_state["running"]:
        return jsonify({"ok": False, "state": bot_state})
    
    stop_event.set()
    bot_state["running"] = False
    bot_state["status"] = "متوقف"
    
    return jsonify({"ok": True, "state": bot_state})

@app.route('/api/reset', methods=['POST'])
def reset_stats():
    bot_state["trades"] = 0
    bot_state["wins"] = 0
    bot_state["losses"] = 0
    bot_state["win_rate"] = 0
    bot_state["signals"] = []
    bot_state["log"] = []
    
    return jsonify({"ok": True, "state": bot_state})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
