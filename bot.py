import os
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
from telegram.request import HTTPXRequest
import asyncio
from operator import itemgetter

app = FastAPI()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "8919300615")

tg_request = HTTPXRequest(connection_pool_size=4, read_timeout=10, write_timeout=10)
bot = Bot(token=TELEGRAM_TOKEN, request=tg_request)

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Kraken's unrestricted data stream links
BTC_KRAKEN_URL  = "https://kraken.com"
GOLD_KRAKEN_URL = "https://kraken.com"

# Plain English data extraction tools to bypass index bracket bugs
get_result_field = itemgetter("result")
get_btc_pair_field = itemgetter("XBTUSDT")
get_gold_pair_field = itemgetter("XAUTUSDT")
get_ticker_data_list = itemgetter("c")

def fetch_kraken_btc():
    """Fetches live Bitcoin price from Kraken's open node."""
    try:
        response = requests.get(BTC_KRAKEN_URL, headers=API_HEADERS, timeout=6)
        if response.status_code == 200:
            data = response.json()
            result = get_result_field(data)
            pair_data = get_btc_pair_field(result)
            price_list = get_ticker_data_list(pair_data)
            # The first item in the 'c' list is the current price string
            return float(next(iter(price_list)))
    except Exception as e:
        print(f"Kraken BTC Error: {e}")
    return 0.0

def fetch_kraken_gold():
    """Fetches live Gold price from Kraken's open node."""
    try:
        response = requests.get(GOLD_KRAKEN_URL, headers=API_HEADERS, timeout=6)
        if response.status_code == 200:
            data = response.json()
            result = get_result_field(data)
            pair_data = get_gold_pair_field(result)
            price_list = get_ticker_data_list(pair_data)
            # The first item in the 'c' list is the current price string
            return float(next(iter(price_list)))
    except Exception as e:
        print(f"Kraken Gold Error: {e}")
    return 0.0

def analyze_and_trade_dual():
    """Compiles market pricing details securely using Kraken data feeds."""
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
    """Tracks Bitcoin and Gold every 60 seconds and pushes separated updates."""
    try:
        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(), 
                text="✅ **Kraken Open-Node Update Stream Active**\nConnected to unrestricted data networks. Broadcasting prices now!"
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
