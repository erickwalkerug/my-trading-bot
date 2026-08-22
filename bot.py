import os
import pandas as pd
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
import asyncio

# 1. Start the web server application
app = FastAPI()

# 2. Grab tokens automatically from Render environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "8919300615")  # Fixed Chat ID backup
bot = Bot(token=TELEGRAM_TOKEN)

# 3. Standard headers to bypass connection blocks
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Blockchain.info public API ticker format
DATA_URL = "https://blockchain.info"

def fetch_market_data():
    """Gets market information safely."""
    try:
        response = requests.get(DATA_URL, headers=API_HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def analyze_and_trade():
    """Extracts price data safely."""
    raw_data = fetch_market_data()
    if not raw_data:
        return "Failed to grab a clean data payload from the API server."
    
    try:
        btc_price = raw_data.get("USD", {}).get("buy", "Unknown")
        return f"Market Sweep Complete. Current Bitcoin Price: ${btc_price} USD"
    except Exception as e:
        return f"Data parsed incorrectly: {e}"

@app.get("/")
def home():
    """Basic health endpoint."""
    return {"status": "bot_running", "system": "active"}

async def keep_awake_loop():
    """Pings itself every 4 minutes to stay 24/7 active."""
    await asyncio.sleep(30)
    while True:
        try:
            port = os.environ.get('PORT', 10000)
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
            print("Pinging system self to stay awake!")
        except Exception as e:
            print(f"Awake ping notice: {e}")
        await asyncio.sleep(240)

async def trading_loop():
    """Runs trade logic instantly on startup, then loops every 5 minutes."""
    # NO delay on boot! This runs immediately when Render turns on
    while True:
        try:
            summary = analyze_and_trade()
            print(summary)
            target_chat = str(CHAT_ID).strip()
            await bot.send_message(chat_id=target_chat, text=summary)
        except Exception as e:
            print(f"Error in background task loop: {e}")
        
        # Wait 5 minutes before sending the next one
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    """Starts background loops."""
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
