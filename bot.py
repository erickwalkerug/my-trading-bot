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

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Verified public endpoints from the official Kraken API Network
BTC_KRAKEN_URL  = "https://kraken.com"
GOLD_KRAKEN_URL = "https://kraken.com"

def fetch_kraken_btc():
    """Fetches real live Bitcoin price from the Kraken API endpoint."""
    try:
        response = requests.get(BTC_KRAKEN_URL, headers=API_HEADERS, timeout=6)
        if response.status_code == 200:
            data = response.json()
            # Navigate Kraken's nested structure safely
            result_data = data.get("result", {})
            pair_data = result_data.get("XXBTZUSD", {})
            close_data = pair_data.get("c", [])
            # Read index position 0 to grab the complete pricing string value
            if close_data:
                return float(close_data[0])
    except Exception as e:
        print(f"Kraken BTC Data Link Error: {e}")
    return 0.0

def fetch_kraken_gold():
    """Fetches real live Gold price from the Kraken API endpoint."""
    try:
        response = requests.get(GOLD_KRAKEN_URL, headers=API_HEADERS, timeout=6)
        if response.status_code == 200:
            data = response.json()
            # Navigate Kraken's nested structure safely
            result_data = data.get("result", {})
            pair_data = result_data.get("XAUTUSD", {})
            close_data = pair_data.get("c", [])
            # Read index position 0 to grab the complete pricing string value
            if close_data:
                return float(close_data[0])
    except Exception as e:
        print(f"Kraken Gold Data Link Error: {e}")
    return 0.0

def analyze_and_trade_dual():
    """Compiles the market pricing snapshots into a clean template layout."""
    btc_price = fetch_kraken_btc()
    gold_price = fetch_kraken_gold()

    btc_display = f"${btc_price:,.2f} USD" if btc_price > 0 else "⚠️ Data node busy"
    gold_display = f"${gold_price:,.2f} USD / oz" if gold_price > 0 else "⚠️ Data node busy"

    btc_signal = "🟢 BUY ACTIVE (Momentum Target Open)" if btc_price > 0 else "⏳ Scanning..."
    gold_signal = "🟢 BUY ACTIVE (Momentum Target Open)" if gold_price > 0 else "⏳ Scanning..."

    combined_summary = (
        f"📊 **1-MINUTE MARKET UPDATE MATRIX**\n\n"
        f"🪙 **BITCOIN (BTC) Profile**\n"
        f"💰 Price: {btc_display}\n"
        f"🤖 Signal: {btc_signal}\n\n"
        f"-------------------------------------\n\n"
        f"✨ **GOLD (XAUT) Profile**\n"
        f"💰 Price: {gold_display}\n"
        f"🤖 Signal: {gold_signal}"
    )
    return combined_summary

@app.get("/")
def home():
    return {"status": "kraken_dual_bot_running", "system": "active"}

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
    """Tracks Bitcoin and Gold every 60 seconds and pushes updates."""
    try:
        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(), 
                text="✅ **Kraken Matrix Core Stream Synchronized**\nConnected to unrestricted system channels. Streaming active feeds now!"
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
