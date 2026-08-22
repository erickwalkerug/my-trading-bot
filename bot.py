import os
import pandas as pd
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
import asyncio

# 1. Start the web server application
app = FastAPI()

# 2. Grab your secret tokens automatically from Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")
bot = Bot(token=TELEGRAM_TOKEN)

# 3. Custom browser headers to fix the 'char 0' error and stop blocks
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# The crypto data website link
DATA_URL = "https://coingecko.com"

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
    
    btc_price = raw_data.get("bitcoin", {}).get("usd", "Unknown")
    return f"Market Sweep Complete. Current Bitcoin Price: ${btc_price}"

@app.get("/")
def home():
    """Basic webpage for Render to monitor."""
    return {"status": "bot_running", "system": "active"}

async def keep_awake_loop():
    """Pings the app internally every 5 minutes to keep it 24/7 awake."""
    await asyncio.sleep(10)  # Wait for startup
    while True:
        try:
            # Pings itself locally on port 10000 to trick Render into staying awake
            port = os.environ.get('PORT', 10000)
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
            print("Pinging system self to stay awake!")
        except Exception as e:
            print(f"Awake ping notice: {e}")
        
        # Sleep for 5 minutes (300 seconds)
        await asyncio.sleep(300)

async def trading_loop():
    """Runs your trade logic every 5 minutes and messages Telegram."""
    while True:
        try:
            summary = analyze_and_trade()
            print(summary)
            await bot.send_message(chat_id=CHAT_ID, text=summary)
        except Exception as e:
            print(f"Error in background task loop: {e}")
        
        # Sleep for 5 minutes (300 seconds)
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    """Starts both the trading bot and keep-awake systems simultaneously."""
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    # Binds to the correct hosting port
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
