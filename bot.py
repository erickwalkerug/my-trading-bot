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

# Secure network settings for modern Telegram connections
tg_request = HTTPXRequest(connection_pool_size=4, read_timeout=10, write_timeout=10)
bot = Bot(token=TELEGRAM_TOKEN, request=tg_request)

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Live 1-minute candle history from Binance API
DATA_URL = "https://binance.com"

def fetch_market_data():
    """Fetches real live 1-minute candlestick arrays safely."""
    try:
        response = requests.get(DATA_URL, headers=API_HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Market Data Fetch Error: {e}")
    return None

def analyze_and_trade():
    """Simplified, bulletproof core matching your exact 1-minute rules."""
    raw_candles = fetch_market_data()
    if not raw_candles or len(raw_candles) < 5:
        return "⚠️ Status: System gathering market candle arrays..."

    # Extract historical indices cleanly:
    # index -1 is live data, index -2 is the last fully finalized closed candle
    idx_curr = len(raw_candles) - 2
    idx_prev = len(raw_candles) - 3

    # Parse essential float metrics for the latest completed candle
    open_p  = float(raw_candles[idx_curr][1])
    high_p  = float(raw_candles[idx_curr][2])
    low_p   = float(raw_candles[idx_curr][3])
    close_p = float(raw_candles[idx_curr][4])

    # Parse essential float metrics for the previous candle
    prev_close = float(raw_candles[idx_prev][4])

    # 1. Native Moving Average Math (3-Period SMA)
    c_0 = float(raw_candles[-2][4])
    c_1 = float(raw_candles[-3][4])
    c_2 = float(raw_candles[-4][4])
    sma_3 = (c_0 + c_1 + c_2) / 3

    # 2. Simplified Trend & Crossover Momentum Indicators
    is_bullish_trend = close_p > sma_3 and close_p > prev_close
    is_bearish_trend = close_p < sma_3 and close_p < prev_close

    # 3. Native Candlestick Wick Structure Metrics
    candle_range = (high_p - low_p) if (high_p - low_p) > 0 else 0.0001
    upper_wick = high_p - max(open_p, close_p)
    lower_wick = min(open_p, close_p) - low_p

    # Isolate clear rejections or clean trend continuations
    is_rejection = (upper_wick > (candle_range * 0.4)) or (lower_wick > (candle_range * 0.4))
    is_strong_body = abs(close_p - open_p) > (candle_range * 0.5)

    if not (is_rejection or is_strong_body):
        return "🛑 SKIP: Weak or unclear candlestick momentum profile."

    # 4. Native Lookback Channel Swing Points for Stop Loss
    recent_lows = [float(candle[3]) for candle in raw_candles[-6:-2]]
    recent_highs = [float(candle[2]) for candle in raw_candles[-6:-2]]
    local_swing_low = min(recent_lows)
    local_swing_high = max(recent_highs)

    # -----------------------------------------------------------------------
    # SIMPLIFIED STRATEGY EVALUATION GATES
    # -----------------------------------------------------------------------
    
    # BUY Trigger Execution
    if is_bullish_trend:
        stop_loss = local_swing_low
        return (
            f"🚀 **BUY SETUP TRIGGERED** 🚀\n\n"
            f"💰 Entry Price: ${close_p:,.2f} USD\n"
            f"📈 Trend Condition: Bullish (Price above SMA)\n"
            f"🛡️ Set Stop Loss below previous swing low: ${stop_loss:,.2f} USD"
        )

    # SELL Trigger Execution
    if is_bearish_trend:
        stop_loss = local_swing_high
        return (
            f"⚠️ **SELL SETUP TRIGGERED** ⚠️\n\n"
            f"💰 Entry Price: ${close_p:,.2f} USD\n"
            f"📉 Trend Condition: Bearish (Price below SMA)\n"
            f"🛡️ Set Stop Loss above previous swing high: ${stop_loss:,.2f} USD"
        )

    return "⏳ Scanning Matrix... Conditions neutral. No clear 1-minute execution setups found."

@app.get("/")
def home():
    return {"status": "bot_running", "system": "active"}

async def keep_awake_loop():
    """Internal loop to keep Render free tier awake."""
    await asyncio.sleep(15)
    while True:
        try:
            port = os.environ.get('PORT', 10000)
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
            print("Pinging system self to stay awake!")
        except Exception:
            pass
        await asyncio.sleep(240)

async def trading_loop():
    """Sends prices and custom setup metrics to Telegram every 1-minute interval loop."""
    try:
        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(), 
                text="✅ **Matrix Bot Online**\nYour simplified, lightweight 1-minute bot is active!"
            )
            print("Startup notification sent successfully.")
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade()
            target_chat = str(CHAT_ID).strip()
            
            # Prevent empty text alerts by filtering neutral scans
            if "⏳" not in summary:
                async with bot:
                    await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
                print("Strategic milestone alert dispatched to Telegram!")
        except Exception as e:
            print(f"Telegram Send Error: {e}")

        # Sync loop timing precisely to 1-minute candle intervals
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
