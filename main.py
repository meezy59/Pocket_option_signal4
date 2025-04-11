import os
import time
import pytz
import stripe
import requests
import pandas as pd
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from threading import Thread
from collections import deque
from playwright.sync_api import sync_playwright
from ta.trend import EMAIndicator, MACD, ADXIndicator

app = Flask(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

WEBHOOK_URL = 'https://discord.com/api/webhooks/1358898813707882741/8Ss9sRtHqgR10m34V5LR1jmKlrEp5HpBLJpFKDVT4jcYZrK8_ZgKjNWBdRfxE7B5o0ag'
PAIRS = {
    "EUR/USD": "eurusd",
    "GBP/USD": "gbpusd",
    "USD/JPY": "usdjpy"
}

price_history = {
    "EUR/USD": deque(maxlen=50),
    "GBP/USD": deque(maxlen=50),
    "USD/JPY": deque(maxlen=50)
}

signal_log_file = "data.json"

if os.path.exists(signal_log_file):
    with open(signal_log_file, "r") as f:
        leaderboard_data = json.load(f)
else:
    leaderboard_data = {}

def save_leaderboard():
    with open(signal_log_file, "w") as f:
        json.dump(leaderboard_data, f)

@app.route('/')
def home():
    return "Bot with indicators and leaderboard is running!"

@app.route("/leaderboard")
def leaderboard():
    html = """
    <h2>Live Signal Leaderboard</h2>
    <table border="1" cellpadding="5">
        <tr><th>Pair</th><th>Signals Sent</th><th>Last Time</th><th>Last Direction</th><th>Last Price</th></tr>
        {% for pair, data in leaderboard.items() %}
        <tr>
            <td>{{ pair }}</td>
            <td>{{ data.count }}</td>
            <td>{{ data.time }}</td>
            <td>{{ data.direction }}</td>
            <td>{{ data.price }}</td>
        </tr>
        {% endfor %}
    </table>
    """
    return render_template_string(html, leaderboard=leaderboard_data)

def get_live_price(pair_code):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://pocketoption.com/en/login/")
        page.fill('input[name="email"]', "Armeezybooking@gmail.com")
        page.fill('input[name="password"]', "Bankk59!!")
        page.click('button[type="submit"]')
        page.wait_for_timeout(8000)
        page.goto("https://pocketoption.com/en/cabinet/trade/")
        page.wait_for_timeout(10000)

        try:
            price_el = page.query_selector("div.chart-price")
            price_text = price_el.inner_text()
            price = float(price_text.replace(',', ''))
            print(f"Live price: {price}")
        except Exception as e:
            print("Price scrape error:", e)
            price = None

        browser.close()
        return price

def update_price(pair, price):
    now = datetime.utcnow()
    price_history[pair].append({"time": now, "price": price})

def generate_candles(pair):
    df = pd.DataFrame(price_history[pair])
    if len(df) < 10:
        return None

    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    resampled = df['price'].resample('1T').ohlc().dropna()
    return resampled

def check_indicators(candles):
    if candles is None or len(candles) < 26:
        return False, None

    candles['ema_fast'] = EMAIndicator(candles['close'], window=5).ema_indicator()
    candles['ema_slow'] = EMAIndicator(candles['close'], window=20).ema_indicator()
    candles['macd_line'] = MACD(candles['close']).macd()
    candles['macd_signal'] = MACD(candles['close']).macd_signal()
    candles['adx'] = ADXIndicator(candles['high'], candles['low'], candles['close']).adx()

    last = candles.iloc[-1]

    macd_cross = last['macd_line'] > last['macd_signal']
    ema_trend = last['ema_fast'] > last['ema_slow']
    strong_adx = last['adx'] > 20

    direction = "CALL" if macd_cross and ema_trend else "PUT"

    return macd_cross and ema_trend and strong_adx, direction

def send_signal(pair, price, direction):
    utc_now = datetime.utcnow()
    est_now = datetime.now(pytz.timezone("US/Eastern"))
    utc_time = utc_now.strftime("%H:%M")
    est_time = est_now.strftime("%I:%M %p")

    message = f"""**TRADE ALERT: {pair}**
Direction: {direction}
Current Price: {price}
UTC Time: {utc_time}
EST Time: {est_time}
Signal Strength: High
Strategy: MACD + EMA + ADX + Candlesticks
——————————————
Open a 1 Minute {direction} trade at {price} on Pocket Option."""
    response = requests.post(WEBHOOK_URL, json={"content": message})
    print("Signal sent!" if response.status_code == 204 else response.text)

    leaderboard_data.setdefault(pair, {"count": 0, "time": "", "direction": "", "price": ""})
    leaderboard_data[pair]["count"] += 1
    leaderboard_data[pair]["time"] = est_time
    leaderboard_data[pair]["direction"] = direction
    leaderboard_data[pair]["price"] = price
    save_leaderboard()

def strategy_loop():
    while True:
        for pair, code in PAIRS.items():
            price = get_live_price(code)
            if price:
                update_price(pair, price)
                candles = generate_candles(pair)
                passed, direction = check_indicators(candles)
                if passed:
                    send_signal(pair, price, direction)
        time.sleep(60)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()
Thread(target=strategy_loop).start()
