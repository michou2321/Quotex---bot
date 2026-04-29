import asyncio
import random
import time
import os
import json
from datetime import datetime, timedelta
from pyquotex.stable_api import Quotex
from telethon import TelegramClient
from telethon.sessions import StringSession

# Load from environment variables
EMAIL = os.getenv("EMAIL", "wagife9306@mugstock.com")
PASSWORD = os.getenv("PASSWORD", "latchi23@@")
API_ID = int(os.getenv("API_ID", "33567199"))
API_HASH = os.getenv("API_HASH", "3fdd30ef25043c39d8cc897d6251b8f1")
CHANNEL = os.getenv("CHANNEL", "@latchidz0")
SESSION_STRING = os.getenv("SESSION_STRING", "")

ASSETS = ["NZDCHF_otc", "USDINR_otc", "USDBDT_otc", "USDARS_otc", "USDPKR_otc"]
BASE_AMOUNT = 1.0

async def decide_direction(client, asset):
    call_score = 0
    put_score = 0
    try:
        candles = await client.get_candles(asset, int(time.time()), 5, 60)
        if candles:
            ups = sum(1 for c in candles if c["close"] > c["open"])
            downs = sum(1 for c in candles if c["close"] < c["open"])
            if ups >= 3: call_score += 3
            if downs >= 3: put_score += 3
            last_close = candles[-1]["close"]
        else:
            last_close = 0

        rsi = await client.calculate_indicator(asset, "RSI", {"period":14}, history_size=3600, timeframe=60)
        if rsi and "current" in rsi and rsi["current"]:
            if float(rsi["current"]) < 35: call_score += 2
            elif float(rsi["current"]) > 65: put_score += 2

        ema = await client.calculate_indicator(asset, "EMA", {"period":20}, history_size=3600, timeframe=60)
        if ema and "current" in ema and ema["current"]:
            if last_close > float(ema["current"]): call_score += 2
            elif last_close < float(ema["current"]): put_score += 2

        sma = await client.calculate_indicator(asset, "SMA", {"period":20}, history_size=3600, timeframe=60)
        if sma and "current" in sma and sma["current"]:
            if last_close > float(sma["current"]): call_score += 1
            elif last_close < float(sma["current"]): put_score += 1

        macd = await client.calculate_indicator(asset, "MACD", {}, history_size=3600, timeframe=60)
        if macd and "macd" in macd and macd["macd"]:
            if macd["macd"][-1] > macd["signal"][-1]: call_score += 2
            else: put_score += 2

        boll = await client.calculate_indicator(asset, "BOLLINGER", {"period":20,"std":2}, history_size=3600, timeframe=60)
        if boll and "middle" in boll:
            if last_close < boll["lower"][-1]: call_score += 2
            elif last_close > boll["upper"][-1]: put_score += 2

        stoch = await client.calculate_indicator(asset, "STOCHASTIC", {"k_period":14,"d_period":3}, history_size=3600, timeframe=60)
        if stoch and "current" in stoch and stoch["current"]:
            if stoch["current"] < 20: call_score += 1
            elif stoch["current"] > 80: put_score += 1

        atr = await client.calculate_indicator(asset, "ATR", {"period":14}, history_size=3600, timeframe=60)
        if atr and "current" in atr and atr["current"]:
            if float(atr["current"]) > 0.5:
                call_score += 1; put_score += 1

        adx = await client.calculate_indicator(asset, "ADX", {"period":14}, history_size=3600, timeframe=60)
        if adx and "adx" in adx and adx["adx"]:
            if adx["adx"][-1] > 25:
                if call_score > put_score: call_score += 1
                elif put_score > call_score: put_score += 1

        ichi = await client.calculate_indicator(asset, "ICHIMOKU", {"tenkan_period":9,"kijun_period":26,"senkou_b_period":52}, history_size=3600, timeframe=60)
        if ichi and "tenkan" in ichi and ichi["tenkan"]:
            if last_close > ichi["tenkan"][-1]: call_score += 1
            elif last_close < ichi["tenkan"][-1]: put_score += 1

        if call_score > put_score: return "call"
        elif put_score > call_score: return "put"
        else: return random.choice(["call","put"])

    except Exception as e:
        print(f"DECIDE ERROR: {e}")
        return random.choice(["call","put"])


async def trade_once(client, asset, amount, direction, duration, target_time):
    now = datetime.now()
    wait_seconds = (target_time - now).total_seconds() - 2.0
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    try:
        before_balance = float(await client.get_balance())
    except:
        before_balance = 0.0

    order_id = None
    order_info = None
    try:
        print(f"🟡 محاولة شراء: {asset} | {direction}")
        success, order_info = await client.buy(amount, asset, direction, duration, time_mode="TIME")
    except Exception as e:
        print(f"BUY ERROR: {e}")
        return None, None, None, "none"

    if not success or not isinstance(order_info, dict):
        print("❌ فشل فتح الصفقة")
        return None, None, None, "none"

    order_id = order_info.get("id", None)

    await asyncio.sleep(duration + 10)

    result = "loss"
    try:
        history = await client.get_history()
        if history and "data" in history:
            for trade in history["data"]:
                if str(trade.get("id")) == str(order_id):
                    if trade.get("result", "").lower() == "win":
                        result = "win"
                    elif trade.get("result", "").lower() == "loss":
                        result = "loss"
                    elif float(trade.get("profit", 0)) > 0:
                        result = "win"
                    elif float(trade.get("profit", 0)) < 0:
                        result = "loss"
                    break
        else:
            final_balance = float(await client.get_balance())
            if final_balance > before_balance:
                result = "win"
    except Exception as e:
        print(f"RESULT ERROR: {e}")

    return order_id, asset, direction, result


async def main():
    print("🚀 Bot starting...")
    
    # Load session from file
    session_data = None
    if os.path.exists("session.json"):
        print("📂 Loading session.json...")
        try:
            with open("session.json", "r") as f:
                session_data = json.load(f)
                print(f"✅ Session loaded for {EMAIL}")
        except Exception as e:
            print(f"⚠️ Could not load session.json: {e}")
    
    # Retry logic for Quotex connection
    max_retries = 10
    client = None
    
    for attempt in range(max_retries):
        try:
            print(f"📡 Connection attempt {attempt + 1}/{max_retries}...")
            
            client = Quotex(email=EMAIL, password=PASSWORD, lang="en")
            
            # If we have session data, use it
            if session_data and EMAIL in session_data:
                print("🔑 Using session authentication...")
                # Store session for future use
                client.session_data = session_data[EMAIL]
            
            client.set_account_mode("PRACTICE")

            connected, reason = await client.connect()
            if connected:
                print("✅ Connected to Quotex!")
                break
            else:
                print(f"⚠️ Connection failed: {reason}")
                if attempt < max_retries - 1:
                    wait_time = 30 + (attempt * 10)
                    print(f"⏳ Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"❌ Error: {str(e)[:100]}")
            if attempt < max_retries - 1:
                wait_time = 30 + (attempt * 10)
                print(f"⏳ Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
            else:
                print("❌ Failed to connect after all retries!")
                return
    
    if not client:
        print("❌ Could not initialize client!")
        return

    await client.change_account("PRACTICE")

    # Connect to Telegram
    tg = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await tg.start()

    first_asset = random.choice(ASSETS)
    first_direction = await decide_direction(client, first_asset)
    await tg.send_message(CHANNEL,
        f"🚀✨ LATCHI PRO BOT ✨🚀\n"
        f"📊 تحليل أولي: الزوج المختار هو {first_asset.upper()}\n"
        f"✅ الدخول في الدقيقة القادمة على الشمعة الجديدة\n"
        f"{'🔼 CALL' if first_direction=='call' else '⬇️ PUT'} حسب التحليل\n\n"
        "#LATCHI_PRO #QUOTEX"
    )

    while True:
        try:
            asset = random.choice(ASSETS)
            direction = await decide_direction(client, asset)

            now = datetime.now()
            next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            target_time = next_minute.replace(second=0)

            preview_msg = f"""📊 صفقة جديدة LATCHI DZ VIP 🌟:

{asset.upper()} | M1 | {target_time.strftime("%H:%M")} | {"CALL 🔼" if direction=="call" else "PUT ⬇️"}

#QUOTEX"""
            await tg.send_message(CHANNEL, preview_msg)

            order_id, asset_used, dir_used, result = await trade_once(
                client, asset, BASE_AMOUNT, direction, 60, target_time
            )

            if dir_used is None:
                await tg.send_message(CHANNEL, f"⚠️ الصفقة لم تنفذ | {asset.upper()}")
                await asyncio.sleep(5)
                continue

            if result == "win":
                await tg.send_message(CHANNEL, f"🟢 ربح ✅ | {asset_used.upper()} | {dir_used.upper()}")
            elif result == "loss":
                await tg.send_message(CHANNEL, f"🔴 خسارة ❌ | {asset_used.upper()} | {dir_used.upper()}")
            else:
                await tg.send_message(CHANNEL, f"⚠️ النتيجة غير معروفة | {asset_used.upper()}")

            # Wait longer to avoid rate limiting
            await asyncio.sleep(random.randint(30, 60))

        except Exception as e:
            print(f"MAIN LOOP ERROR: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
