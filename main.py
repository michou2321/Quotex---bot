import asyncio
import random
import time
from datetime import datetime, timedelta
from flask import Flask, request
from pyquotex.stable_api import Quotex

app = Flask(__name__)
sessions = {}

ASSETS = ["NZDCHF_otc", "USDINR_otc", "USDBDT_otc", "USDARS_otc", "USDPKR_otc"]
BASE_AMOUNT = 1.0

async def decide_direction(client, asset):
    signals = []
    candles = await client.get_candles(asset, int(time.time()), 3, 60)
    if candles:
        ups = sum(1 for c in candles if c["close"] > c["open"])
        downs = sum(1 for c in candles if c["close"] < c["open"])
        signals.append("call" if ups > downs else "put")

    rsi = await client.calculate_indicator(asset, "RSI", {"period":14}, history_size=3600, timeframe=60)
    if rsi and "current" in rsi and rsi["current"] is not None:
        if rsi["current"] < 30:
            signals.append("call")
        elif rsi["current"] > 70:
            signals.append("put")

    if not signals:
        return random.choice(["call","put"])
    return max(set(signals), key=signals.count)

@app.route('/login', methods=['POST'])
def login
