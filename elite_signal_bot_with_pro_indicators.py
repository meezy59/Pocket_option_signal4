import time, json, pytz, threading
from datetime import datetime
from flask import Flask, jsonify
import pandas as pd
import numpy as np
from playwright.sync_api import sync_playwright
import requests
import ta

# === Configuration ===
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1360244182870003913/ZVKKaYMiWc9UYMGZfJd_iRLoKFhOZTXCVoXALSVqC2a9UxIL6VdHn_g0l0MvqtwEy_L5"  # replace with your webhook
CURRENCY_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY"]
TIMEFRAME_SECONDS = 60
DATA_POINTS_NEEDED = 50

# === Flask Setup ===
app = Flask(__name__)
logs = []

@app.route("/")
def index():
    return "Bot is running!"

@app.route("/test-signal")
def test_signal():
    send_to_discord("**TEST SIGNAL** | EUR/USD | BUY | Confidence: 99% | Time: " + datetime.now().strftime('%H:%M:%S'))
    return "Test signal sent!"

@app.route("/status")
def status():
    return jsonify({
        "running": True,
        "pairs": CURRENCY_PAIRS,
        "data_collected": len(logs)
    })

@app.route("/leaderboard")
def leaderboard():
    return jsonify(logs[-50:])

# === Utility Functions ===
def send_to_discord(message):
    requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def calculate_indicators(df):
    df['ema'] = ta.trend.ema_indicator(df['close'], window=10)
    macd = ta.trend.macd_diff(df['close'])
    df['macd'] = macd

    adx = ta.trend.adx(df['high'], df['low'], df['close'])
    df['adx'] = adx

    df['rsi'] = ta.momentum.rsi(df['close'])

    df['zigzag'] = np.where((df['close'].shift(1) < df['close']) & (df['close'].shift(-1) < df['close']), df['close'], np.nan)
    df['bullish_pinbar'] = (df['close'] > df['open']) & ((df['low'] < df['close'] * 0.998))
    df['bearish_pinbar'] = (df['close'] < df['open']) & ((df['high'] > df['close'] * 1.002))
    return df

def generate_signal(df):
    latest = df.iloc[-1]
    score = 0
    reasons = []

    if latest['close'] > latest['ema']:
        score += 1
        reasons.append("EMA up")
    if latest['macd'] > 0:
        score += 1
        reasons.append("MACD bullish")
    if latest['adx'] > 20:
        score += 1
        reasons.append("Strong trend")
    if latest['rsi'] < 70 and latest['rsi'] > 50:
        score += 1
        reasons.append("RSI in buy zone")
    if latest['bullish_pinbar']:
        score += 1
        reasons.append("Pinbar bullish")
    if latest['bearish_pinbar']:
        score -= 1
        reasons.append("Pinbar bearish")

    if score >= 4:
        return "BUY", score * 20, reasons
    elif score <= -3:
        return "SELL", abs(score) * 20, reasons
    else:
        return "NO TRADE", 0, reasons

def fetch_price_data(page, pair):
    try:
        page.goto("https://pocketoption.com/en/cabinet/")
        # Replace with actual scraping logic
        prices = [1.105 + 0.0001 * i for i in range(DATA_POINTS_NEEDED)]
        df = pd.DataFrame({
            "open": prices,
            "high": [p + 0.0002 for p in prices],
            "low": [p - 0.0002 for p in prices],
            "close": prices
        })
        return df
    except Exception as e:
        print(f"[ERROR] {e}")
        return None

def run_bot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        while True:
            for pair in CURRENCY_PAIRS:
                df = fetch_price_data(page, pair)
                if df is None or len(df) < DATA_POINTS_NEEDED:
                    continue
                df = calculate_indicators(df)
                signal, confidence, reasons = generate_signal(df)

                if signal in ["BUY", "SELL"]:
                    msg = f"**TRADE ALERT** | {pair} | {signal} | Confidence: {confidence}% | Time: {datetime.now().strftime('%H:%M:%S')}"
                    send_to_discord(msg)
                    logs.append({"pair": pair, "signal": signal, "confidence": confidence, "time": datetime.now().strftime('%H:%M:%S')})
                    print(msg)

            time.sleep(TIMEFRAME_SECONDS)

# === Start Bot Thread ===
threading.Thread(target=run_bot, daemon=True).start()

# === Start Flask App ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
      




