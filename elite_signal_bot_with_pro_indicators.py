import time, json, pytz, threading
from datetime import datetime
from flask import Flask, jsonify
import pandas as pd, numpy as np
from playwright.sync_api import sync_playwright
import requests, ta

# === CONFIGURATION ===
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1360244182870003913/ZVKKaYMiWc9UYMGZfJd_iRLoKFhOZTXCVoXALSVqC2a9UxIL6VdHn_g0l0MvqtwEy_L5"
CURRENCY_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY"]
TIMEFRAME_SECONDS = 60
DATA_POINTS_NEEDED = 30
SIGNAL_THRESHOLD = 80  # % rating threshold to send signal

# === STRATEGY LOGIC ===
def calculate_indicators(df):
    df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=5)
    df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=14)
    macd = ta.trend.macd(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"])
    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    return df

def get_signal(df):
    latest = df.iloc[-1]
    signal = "NO TRADE"
    rating = 0

    if latest["ema_fast"] > latest["ema_slow"]:
        rating += 25
    if latest["macd"] > latest["macd_signal"]:
        rating += 25
    if latest["adx"] > 20:
        rating += 15
    if latest["rsi"] > 55:
        rating += 10
    if latest["rsi"] < 45:
        rating -= 10

    if rating >= SIGNAL_THRESHOLD:
        signal = "BUY" if latest["ema_fast"] > latest["ema_slow"] else "SELL"

    return signal, rating

# === SCRAPER ===
def scrape_chart_data(pair):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://pocketoption.com/en/cabinet/demo-quick/")
        time.sleep(8)  # allow chart to load
        chart_data = page.evaluate("""() => {
            return window.tvWidget.activeChart().getSeriesData().map(c => ({
                time: c.time,
                open: c.value[0],
                high: c.value[1],
                low: c.value[2],
                close: c.value[3],
            }));
        }""")
        browser.close()
    return chart_data

# === SIGNAL ENGINE ===
def analyze_and_signal():
    while True:
        for pair in CURRENCY_PAIRS:
            try:
                raw_data = scrape_chart_data(pair)
                df = pd.DataFrame(raw_data)
                df = calculate_indicators(df)

                signal, rating = get_signal(df)
                if signal != "NO TRADE":
                    message = f"**TRADE ALERT: {pair} | Signal: {signal} | Time: {datetime.now().strftime('%H:%M:%S')} | Rating: {rating}%**"
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
                    print(message)

            except Exception as e:
                print(f"[{pair}] ERROR:", e)
        time.sleep(TIMEFRAME_SECONDS)

# === FLASK API ===
app = Flask(__name__)
@app.route("/")
def index():
    return "Elite Signal Bot is running"

@app.route("/test-signal")
def test_signal():
    message = f"**TEST SIGNAL: EUR/USD | BUY | Time: {datetime.now().strftime('%H:%M:%S')}**"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    return "Test signal sent!"

@app.route("/status")
def status():
    return jsonify({
        "currency_pairs": CURRENCY_PAIRS,
        "strategy": ["MACD", "EMA", "ADX", "RSI", "Candlestick logic"],
        "interval": f"{TIMEFRAME_SECONDS}s",
        "status": "Live"
    })

# === LAUNCH ENGINE ===
if __name__ == "__main__":
    threading.Thread(target=analyze_and_signal, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)




