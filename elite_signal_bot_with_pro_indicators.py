
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

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1360244182870003913/ZVKKaYMiWc9UYMGZfJd_iRLoKFhOZTXCVoXALSVqC2a9UxIL6VdHn_g0l0MvqtwEy_L5"
CURRENCY_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY"]
TIMEFRAME_SECONDS = 60
DATA_POINTS_NEEDED = 30

price_data = {pair: [] for pair in CURRENCY_PAIRS}
signal_log = {pair: {"count": 0, "last_time": "", "last_dir": "", "last_price": 0} for pair in CURRENCY_PAIRS}

def fetch_prices():
    with sync_playwright() as p:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://pocketoption.com/en/cabinet/demo-quick/")
        time.sleep(10)
        while True:
            for pair in CURRENCY_PAIRS:
                try:
                    price_element = page.locator(f'text={pair}').first
                    price_element.click()
                    time.sleep(2)
                    price_str = page.locator('.asset-price').first.inner_text()
                    price = float(price_str)
                    now = datetime.utcnow()
                    price_data[pair].append({"time": now, "price": price})
                    if len(price_data[pair]) > DATA_POINTS_NEEDED:
                        price_data[pair] = price_data[pair][-DATA_POINTS_NEEDED:]
                    analyze(pair)
                except:
                    continue
            time.sleep(TIMEFRAME_SECONDS)

def analyze(pair):
    if len(price_data[pair]) < DATA_POINTS_NEEDED:
        return

    df = pd.DataFrame(price_data[pair])
    df["price"] = pd.to_numeric(df["price"])
    df["ema5"] = ta.trend.ema_indicator(df["price"], window=5)
    df["ema20"] = ta.trend.ema_indicator(df["price"], window=20)
    macd = ta.trend.macd(df["price"])
    adx = ta.trend.adx(df["price"])
    rsi = ta.momentum.RSIIndicator(df["price"]).rsi()

    last_row = df.iloc[-1]

    if (last_row["ema5"] > last_row["ema20"] and
        macd.macd_diff().iloc[-1] > 0 and
        adx.adx().iloc[-1] > 20 and
        rsi.iloc[-1] < 70):
        send_signal(pair, "CALL", last_row["price"])

    elif (last_row["ema5"] < last_row["ema20"] and
          macd.macd_diff().iloc[-1] < 0 and
          adx.adx().iloc[-1] > 20 and
          rsi.iloc[-1] > 30):
        send_signal(pair, "PUT", last_row["price"])

def send_signal(pair, direction, price):
    utc_now = datetime.utcnow().strftime("%H:%M")
    est_now = datetime.now(pytz.timezone("US/Eastern")).strftime("%I:%M %p")
    content = (
        message = f"**TRADE ALERT: {pair} | Signal: {signal} | Time: {datetime.now().strftime('%H:%M:%S')}**"
"message = f"**TRADE ALERT: {pair} | Signal: {signal} | Time: {datetime.now().strftime('%H:%M:%S')}**"
        f"Direction: {direction}
"
        f"Timeframe: 1 Minute
"
        f"SET PRICE NOW
"
        f"- Current Price: {price}
"
        f"- UTC Time: {utc_now}
"
        f"- EST Time: {est_now}
"
        f"Signal Strength: ELITE
"
        f"Strategy: EMA + MACD + ADX + RSI
"
        f"——————————————
"
        f"Open a 1 Minute {direction} trade on Pocket Option at {price}."
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    signal_log[pair]["count"] += 1
    signal_log[pair]["last_time"] = est_now
    signal_log[pair]["last_dir"] = direction
    signal_log[pair]["last_price"] = price

@app.route("/")
def home():
    return "Signal bot is live!"

@app.route("/status")
def status():
    return jsonify({
        pair: {
            "data_points_collected": len(price_data[pair]),
            "enough_for_signal": len(price_data[pair]) >= DATA_POINTS_NEEDED
        }
        for pair in CURRENCY_PAIRS
    })

@app.route("/leaderboard")
def leaderboard():
    return (
        "<b>Live Signal Leaderboard</b><br>"
        "<table border='1'><tr><th>Pair</th><th>Signals Sent</th><th>Last Time</th><th>Last Direction</th><th>Last Price</th></tr>" +
        "".join(
            f"<tr><td>{pair}</td><td>{signal_log[pair]['count']}</td><td>{signal_log[pair]['last_time']}</td>"
            f"<td>{signal_log[pair]['last_dir']}</td><td>{signal_log[pair]['last_price']}</td></tr>"
            for pair in CURRENCY_PAIRS
        ) +
        "</table>"
    )

@app.route("/test-signal")
def test_signal():
    send_signal("EUR/USD", "CALL", 1.23456)
    return "Test signal sent!"

def run_bot():
    thread = threading.Thread(target=fetch_prices)
    thread.daemon = True
    thread.start()
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    run_bot()
