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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

# Stable Public API URL tracking both Bitcoin and Tether Gold prices simultaneously
COINGECKO_URL = "https://coingecko.com"

def fetch_market_rates():
    """Fetches real-time price updates securely without cloud server IP block restrictions."""
    try:
        response = requests.get(COINGECKO_URL, headers=API_HEADERS, timeout=8)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Network stream connection error: {e}")
    return None

def analyze_and_trade_dual():
    """Processes pricing data maps and generates clear directional signals."""
    data = fetch_market_rates()
    if not data:
        return (
            "📊 **1-MINUTE MARKET UPDATE MATRIX**\n\n"
            "🪙 **BITCOIN (BTC) Profile**\n"
            "⚠️ Status: Data link busy, retrying stream...\n\n"
            "-------------------------------------\n\n"
            "✨ **GOLD (XAUT) Profile**\n"
            "⚠️ Status: Data link busy, retrying stream..."
        )

    # 1. Safely extract specific dictionary pairs using plain word lookups
    btc_data = data.get("bitcoin", {})
    gold_data = data.get("tether-gold", {})

    btc_price = float(btc_data.get("usd", 0.0))
    btc_change = float(btc_data.get("usd_24h_change", 0.0))

    gold_price = float(gold_data.get("usd", 0.0))
    gold_change = float(gold_data.get("usd_24h_change", 0.0))

    # 2. Determine simple directional strategy setups using recent price movements
    if btc_change > 0:
        btc_signal = "🟢 BUY ACTIVE (Daily Momentum Up)"
    elif btc_change < 0:
        btc_signal = "🔴 SELL ACTIVE (Daily Momentum Down)"
    else:
        btc_signal = "⚪ NEUTRAL SCAN"

    if gold_change > 0:
        gold_signal = "🟢 BUY ACTIVE (Daily Momentum Up)"
    elif gold_change < 0:
        gold_signal = "🔴 SELL ACTIVE (Daily Momentum Down)"
    else:
        gold_signal = "⚪ NEUTRAL SCAN"

    # 3. Construct the clean message matrix template
    combined_summary = (
        f"📊 **1-MINUTE MARKET UPDATE MATRIX**\n\n"
        f"🪙 **BITCOIN (BTC) Profile**\n"
        f"💰 Price: ${btc_price:,.2f} USD\n"
        f"📊 24h Change: {btc_change:+.2f}%\n"
        f"🤖 Signal: {btc_signal}\n\n"
        f"-------------------------------------\n\n"
        f"✨ **GOLD (XAUT) Profile**\n"
        f"💰 Price: ${gold_price:,.2f} USD / oz\n"
        f"📊 24h Change: {gold_change:+.2f}%\n"
        f"🤖 Signal: {gold_signal}"
    )
    return combined_summary

@app.get("/")
def home():
    return {"status": "coingecko_dual_bot_running", "system": "active"}

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
                text="✅ **Stable Update Stream Active**\nConnecting to cloud-safe data nodes. Scanning prices now!"
            )
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade_dual()
            target_chat = str(CHAT_ID).strip()
            
            async with bot:
                await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
            print("1-minute market rate snapshot sent.")
            
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
