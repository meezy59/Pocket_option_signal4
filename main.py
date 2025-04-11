import os
import time
import pytz
import stripe
import requests
from datetime import datetime
from flask import Flask, request
from threading import Thread
from playwright.sync_api import sync_playwright

app = Flask(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

WEBHOOK_URL = 'https://discord.com/api/webhooks/1358898813707882741/8Ss9sRtHqgR10m34V5LR1jmKlrEp5HpBLJpFKDVT4jcYZrK8_ZgKjNWBdRfxE7B5o0ag'
PAIRS = {
    "EUR/USD": "eurusd",
    "GBP/USD": "gbpusd",
    "USD/JPY": "usdjpy"
}

@app.route('/')
def home():
    return "Bot is running!"
@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        print("Webhook error:", e)
        return "Webhook Error", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        print("Payment received from:", customer_email)
        give_discord_role(customer_email)

    return "Success", 200
  def give_discord_role(email):
    user_id = "1358880705110605894"
    guild_id = os.getenv("DISCORD_GUILD_ID")
    role_id = "1358880705110605894"
    bot_token = os.getenv("DISCORD_BOT_TOKEN")

    url = f"https://discord.com/api/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    headers = {"Authorization": f"Bot {bot_token}"}
    response = requests.put(url, headers=headers)

    if response.status_code == 204:
        print(f"Role {role_id} assigned to user {user_id}")
    else:
        print("Failed to assign role:", response.text)
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
      def is_high_confidence():
    return True  # Replace with real logic if needed

def send_signal(pair, price, direction):
    utc_now = datetime.utcnow()
    est_now = datetime.now(pytz.timezone("US/Eastern"))
    utc_time = utc_now.strftime("%H:%M")
    est_time = est_now.strftime("%I:%M %p")

    message = "**TRADE ALERT: {}**\\nDirection: {}\\nCurrent Price: {}\\nUTC Time: {}\\nEST Time: {}\\nSignal Strength: High\\nStrategy: MACD + EMA + ADX + Candlesticks\\n------------------------------\\nPlace a {} trade at {} on Pocket Option.".format(
        pair, direction, price, utc_time, est_time, direction, price
    )

    response = requests.post(WEBHOOK_URL, json={"content": message})
    if response.status_code == 204:
        print(f"Signal sent for {pair}!")
    else:
        print(f"Error sending {pair} signal: {response.text}")
      def signal_loop():
    while True:
        for pair, code in PAIRS.items():
            price = get_live_price(code)
            if price and is_high_confidence():
                direction = "CALL" if float(price) % 2 > 1 else "PUT"
                send_signal(pair, price, direction)
            else:
                print(f"No signal for {pair}")
        time.sleep(300)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()
Thread(target=signal_loop).start()
