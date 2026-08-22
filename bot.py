import os
import pandas as pd
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
import asyncio

# 1. Start the web server application
app = FastAPI()

# 2. Grab your secret tokens automatically from Render environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "8919300615")  # Fixed Chat ID backup
bot = Bot(token=TELEGRAM_TOKEN)

# 3. Custom browser headers to prevent empty data responses
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Switched to Blockchain.info ticker API - 100% free and open public data feed
DATA_URL = "https://blockchain.info"

def fetch_market_data():
    """Fetches market information safely without getting blocked."""
    try:
        response = requests.get(DATA_URL, headers=API_HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def analyze_and_trade():
    """Runs your calculations and strategies."""
    raw_data = fetch_market_data()
    if not raw_data:
        return "Failed to grab a clean data payload from the API server."
    
    try:
        # Extracting USD buying price safely from Blockchain.info's data structure
        btc_price = raw_data.get("USD", {}).get("buy", "Unknown")
        return f"Market Sweep Complete. Current Bitcoin Price: ${btc_price} USD"
    except Exception as e:
        return f"Data parsed incorrectly: {e}"

@app.get("/")
def home():
    """Basic webpage endpoint for Render to monitor."""
    return {"status": "bot_running", "system": "active"}

async def keep_awake_loop():
    """Pings the app internally every 4 minutes to keep it awake 24/7."""
    await asyncio.sleep(15)  # Wait for startup
    while True:
        try:
            port = os.environ.get('PORT', 10000)
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
            print("Pinging system self to stay awake!")
        except Exception as e:
            print(f"Awake ping notice: {e}")
        
        await asyncio.sleep(240)

async def trading_loop():
    """Runs your trade logic every 5 minutes and messages Telegram."""
    await asyncio.sleep(5)  # Let server bind completely first
    while True:
        try:
            summary = analyze_and_trade()
            print(summary)
            target_chat = str(CHAT_ID).strip()
            await bot.send_message(chat_id=target_chat, text=summary)
        except Exception as e:
            print(f"Error in background task loop: {e}")
        
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    """Starts both background systems simultaneously."""
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
