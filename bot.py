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

# Pulling 30 clean 1-minute candlestick arrays from Binance
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
    """Lightweight 1-minute tracking engine with fixed indexing math."""
    raw_candles = fetch_market_data()
    if not raw_candles or len(raw_candles) < 10:
        return "⏳ System gathering data..."

    # Index structure for Binance Klines lists:
    # [idx][1]=Open, [idx][2]=High, [idx][3]=Low, [idx][4]=Close
    idx_curr = len(raw_candles) - 2  # Last completed closed candle
    idx_prev = len(raw_candles) - 3  # Previous closed candle

    try:
        open_p  = float(raw_candles[idx_curr][1])
        high_p  = float(raw_candles[idx_curr][2])
        low_p   = float(raw_candles[idx_curr][3])
        close_p = float(raw_candles[idx_curr][4])

        prev_close = float(raw_candles[idx_prev][4])

        # 1. Math Calculation: 3-Period Simple Moving Average (SMA)
        c_0 = float(raw_candles[len(raw_candles)-2][4])
        c_1 = float(raw_candles[len(raw_candles)-3][4])
        c_2 = float(raw_candles[len(raw_candles)-4][4])
        sma_3 = (c_0 + c_1 + c_2) / 3

        # 2. Strategy Rules: Simple Trend Identification
        is_bullish_trend = close_p > sma_3 and close_p > prev_close
        is_bearish_trend = close_p < sma_3 and close_p < prev_close

        # 3. Strategy Rules: Candlestick Body Structure Metrics
        candle_range = (high_p - low_p) if (high_p - low_p) > 0 else 0.0001
        candle_body  = abs(close_p - open_p)
        upper_wick   = high_p - max(open_p, close_p)
        lower_wick   = min(open_p, close_p) - low_p

        is_rejection   = (upper_wick > (candle_range * 0.4)) or (lower_wick > (candle_range * 0.4))
        is_strong_body = candle_body > (candle_range * 0.5)

        if not (is_rejection or is_strong_body):
            return "⏳ Neutral candlestick structure."

        # 4. Strategy Rules: Swing Points for dynamic Stop Loss boundaries
        recent_lows = [float(candle[3]) for candle in raw_candles[-6:-1]]
        recent_highs = [float(candle[2]) for candle in raw_candles[-6:-1]]
        local_swing_low = min(recent_lows)
        local_swing_high = max(recent_highs)

        # -------------------------------------------------------------------
        # BUY / SELL SIGNAL EXECUTION GATES
        # -------------------------------------------------------------------
        if is_bullish_trend:
            return (
                f"🚀 **BUY SETUP TRIGGERED** 🚀\n\n"
                f"💰 **Entry Price:** ${close_p:,.2f} USD\n"
                f"📈 **Trend Condition:** Bullish Momentum\n"
                f"🛡️ **Target Stop Loss:** ${local_swing_low:,.2f} USD"
            )

        if is_bearish_trend:
            return (
                f"⚠️ **SELL SETUP TRIGGERED** ⚠️\n\n"
                f"💰 **Entry Price:** ${close_p:,.2f} USD\n"
                f"📉 **Trend Condition:** Bearish Momentum\n"
                f"🛡️ **Target Stop Loss:** ${local_swing_high:,.2f} USD"
            )

    except Exception as e:
        print(f"Calculation Error: {e}")
        return "⏳ Processing indicators..."

    return "⏳ Scanning..."

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
        except Exception:
            pass
        await asyncio.sleep(240)

async def trading_loop():
    """Tracks markets every 1-minute and only text-alerts real entries."""
    try:
        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(), 
                text="✅ **Matrix Bot Core Online**\nYour 1-minute execution loops are running perfectly!"
            )
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade()
            target_chat = str(CHAT_ID).strip()
            
            # This filter blocks the bot from sending text unless a BUY or SELL hits!
            if "⏳" not in summary:
                async with bot:
                    await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
                print("Signal dispatched successfully.")
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
