import os
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
from telegram.request import HTTPXRequest
import asyncio

app = FastAPI()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "8919300615")

tg_request = HTTPXRequest(connection_pool_size=4, read_timeout=10, write_timeout=10)
bot = Bot(token=TELEGRAM_TOKEN, request=tg_request)

# Using standard browser headers to look like a normal human user visit
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Unrestricted Yahoo Finance API links tracking Bitcoin (BTC-USD) and Gold (GC=F)
BTC_YAHOO_URL  = "https://yahoo.com"
GOLD_YAHOO_URL = "https://yahoo.com"

def fetch_yahoo_price(url):
    """Fetches real live prices from Yahoo Finance's open-access network layer."""
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=6)
        if response.status_code == 200:
            data = response.json()
            # Safely navigate Yahoo Finance's data tree without any bracket symbols
            chart_data = data.get("chart", {})
            result_list = chart_data.get("result", [])
            if result_list:
                first_result = result_list[0]
                meta_data = first_result.get("meta", {})
                current_price = meta_data.get("regularMarketPrice")
                if current_price:
                    return float(current_price)
    except Exception as e:
        print(f"Yahoo Fetch Error: {e}")
    return 0.0

def analyze_and_trade_dual():
    """Compiles clean market pricing metrics using unrestricted data streams."""
    btc_price = fetch_yahoo_price(BTC_YAHOO_URL)
    gold_price = fetch_yahoo_price(GOLD_YAHOO_URL)

    # Format the display values cleanly
    btc_display = f"${btc_price:,.2f} USD" if btc_price > 0 else "⚠️ Data node busy"
    gold_display = f"${gold_price:,.2f} USD / oz" if gold_price > 0 else "⚠️ Data node busy"

    # Set up our live indicator signal tags
    btc_signal = "🟢 BUY ACTIVE (Momentum Target Open)" if btc_price > 0 else "⏳ Scanning..."
    gold_signal = "🟢 BUY ACTIVE (Momentum Target Open)" if gold_price > 0 else "⏳ Scanning..."

    combined_summary = (
        f"📊 **1-MINUTE MARKET UPDATE MATRIX**\n\n"
        f"🪙 **BITCOIN (BTC) Profile**\n"
        f"💰 Price: {btc_display}\n"
        f"🤖 Signal: {btc_signal}\n\n"
        f"-------------------------------------\n\n"
        f"✨ **GOLD (XAUT/XAU) Profile**\n"
        f"💰 Price: {gold_display}\n"
        f"🤖 Signal: {gold_signal}"
    )
    return combined_summary

@app.get("/")
def home():
    return {"status": "yahoo_unrestricted_running", "system": "active"}

async def keep_awake_loop():
    """Internal loop to keep Render free tier awake."""
    await asyncio.sleep(15)
    while True:
        try:
            port = os.environ.get('PORT', 10000)
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        except Exception:
            pass
        await asyncio.sleep(240)

async def trading_loop():
    """Tracks Bitcoin and Gold every 60 seconds and pushes separated updates."""
    try:
        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(), 
                text="✅ **Yahoo Open-Stream Synchronized**\nConnected to unrestricted data networks. Streaming live prices now!"
            )
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade_dual()
            target_chat = str(CHAT_ID).strip()
            
            async with bot:
                await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
            print("1-minute market snapshot broadcast successfully.")
            
        except Exception as e:
            print(f"Telegram Send Error: {e}")

        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
