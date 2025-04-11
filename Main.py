
import time
import json
import pytz
import threading
from datetime import datetime
from flask import Flask, jsonify
import pandas as pd
import numpy as np
from playwright.sync_api import sync_playwright
import requests
import ta

# === Configuration ===
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/your_webhook_here"
CURRENCY_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY"]
TIMEFRAME_SECONDS = 60
DATA_POINTS_NEEDED = 30

signal_log = {}
data_cache = {}

# === Flask App ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot with indicators and leaderboard is running!"

@app.route('/test-signal')
def test_signal():
    send_discord_signal("NZD/USD", "PUT", 1.33274, datetime.utcnow(), "TEST")
    return "Test signal sent!"

@app.route('/leaderboard')
def leaderboard():
    return jsonify(signal_log)

@app.route('/status')
def status():
    status_report = {}
    for pair in CURRENCY_PAIRS:
        count = len(data_cache.get(pair, []))
        status_report[pair] = {
            "data_points_collected": count,
            "enough_for_signal": count >= DATA_POINTS_NEEDED
        }
    return jsonify(status_report)

# === Signal + Analysis Functions ===
def send_discord_signal(pair, direction, price, utc_time, strategy="MACD + EMA + ADX + Zig-Zag"):
    payload = {
        "username": "RICHSIGNALBOT",
        "content": f"**TRADE ALERT: {pair}**\n"
                   f"Direction: {direction}\n"
                   f"Current Price: {price}\n"
                   f"UTC Time: {utc_time.strftime('%H:%M')}\n"
                   f"Strategy: {strategy}\n"
                   f"\nOpen a 1 Minute {direction} trade on Pocket Option at {price}"
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

    log = signal_log.setdefault(pair, {
        "signals_sent": 0,
        "last_time": "",
        "last_direction": "",
        "last_price": 0
    })
    log["signals_sent"] += 1
    log["last_time"] = utc_time.strftime('%Y-%m-%d %H:%M')
    log["last_direction"] = direction
    log["last_price"] = price

def analyze_data(pair, df):
    if df.shape[0] < DATA_POINTS_NEEDED:
        return None

    # Indicators
    df['ema'] = ta.trend.ema_indicator(df['close'], window=10)
    macd = ta.trend.macd_diff(df['close'])
    adx = ta.trend.adx(df['high'], df['low'], df['close'])

    # Entry Conditions
    if macd.iloc[-1] > 0 and df['close'].iloc[-1] > df['ema'].iloc[-1] and adx.iloc[-1] > 20:
        return "CALL"
    elif macd.iloc[-1] < 0 and df['close'].iloc[-1] < df['ema'].iloc[-1] and adx.iloc[-1] > 20:
        return "PUT"
    return None

def collect_data(pair, page):
    price_list = data_cache.setdefault(pair, [])

    while True:
        try:
            # Simulated fetch (replace this with real scrape from Pocket Option chart or DOM)
            current_price = round(np.random.uniform(1.05, 1.35), 5)
            price_list.append(current_price)
            if len(price_list) > DATA_POINTS_NEEDED:
                price_list.pop(0)

            if len(price_list) >= DATA_POINTS_NEEDED:
                df = pd.DataFrame(price_list, columns=["close"])
                df["high"] = df["close"] + 0.0001
                df["low"] = df["close"] - 0.0001

                signal = analyze_data(pair, df)
                if signal:
                    send_discord_signal(pair, signal, df['close'].iloc[-1], datetime.utcnow())
                    price_list.clear()

        except Exception as e:
            print(f"[ERROR] {pair}: {e}")
        time.sleep(TIMEFRAME_SECONDS)

def start_browser_scraper():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        threads = []

        for pair in CURRENCY_PAIRS:
            t = threading.Thread(target=collect_data, args=(pair, page))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

# === Run Bot and Web Server ===
if __name__ == '__main__':
    threading.Thread(target=start_browser_scraper).start()
    app.run(host="0.0.0.0", port=8080)
