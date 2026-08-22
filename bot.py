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
    """Tracks markets and builds a comprehensive status report."""
    raw_candles = fetch_market_data()
    if not raw_candles or len(raw_candles) < 10:
        return "⏳ System gathering data... Please wait for the next interval."

    idx_curr = len(raw_candles) - 2  # Last completed closed candle
    idx_prev = len(raw_candles) - 3  # Previous closed candle

    try:
        # Extract specific list items accurately from the Binance matrix array
        open_p  = float(raw_candles[idx_curr][1])
        high_p  = float(raw_candles[idx_curr][2])
        low_p   = float(raw_candles[idx_curr][3])
        close_p = float(raw_candles[idx_curr][4])

        prev_close = float(raw_candles[idx_prev][4])

        # 1. 3-Period Simple Moving Average (SMA)
        c_0 = float(raw_candles[len(raw_candles)-2][4])
        c_1 = float(raw_candles[len(raw_candles)-3][4])
        c_2 = float(raw_candles[len(raw_candles)-4][4])
        sma_3 = (c_0 + c_1 + c_2) / 3

        # 2. Trend Rules
        is_bullish_trend = close_p > sma_3 and close_p > prev_close
        is_bearish_trend = close_p < sma_3 and close_p < prev_close

        # 3. Candlestick Structure Calculations
        candle_range = (high_p - low_p) if (high_p - low_p) > 0 else 0.0001
        candle_body  = abs(close_p - open_p)
        upper_wick   = high_p - max(open_p, close_p)
        lower_wick   = min(open_p, close_p) - low_p

        is_rejection   = (upper_wick > (candle_range * 0.4)) or (lower_wick > (candle_range * 0.4))
        is_strong_body = candle_body > (candle_range * 0.5)

        # Determine candlestick descriptive label
        if is_rejection:
            candle_style = "Rejection Candle ⚠️"
        elif is_strong_body:
            candle_style = "Strong Momentum Body 🚀"
        else:
            candle_style = "Neutral / Doji Structure ⏳"

        # 4. Swing Channel Point Extractions
        recent_lows = [float(candle[3]) for candle in raw_candles[-6:-1]]
        recent_highs = [float(candle[2]) for candle in raw_candles[-6:-1]]
        local_swing_low = min(recent_lows)
        local_swing_high = max(recent_highs)

        # Determine strategy signal status output text
        if is_bullish_trend:
            signal_text = "🟢 BUY SETUP ACTIVE (Price above SMA)"
            risk_text = f"🛡️ Stop Loss (Below Swing HL): ${local_swing_low:,.2f}"
        elif is_bearish_trend:
            signal_text = "🔴 SELL SETUP ACTIVE (Price below SMA)"
            risk_text = f"🛡️ Stop Loss (Above Swing LH): ${local_swing_high:,.2f}"
        else:
            signal_text = "⚪ NEUTRAL SCAN (Consolidating / Choppy)"
            risk_text = "🛡️ Stop Loss: No active setup"

        # Construct the final 1-minute output text profile
        return (
            f"📊 **1-Minute Market Update**\n\n"
            f"💰 **Current Price:** ${close_p:,.2f} USD\n"
            f"📈 **Indicator SMA (3):** ${sma_3:,.2f} USD\n"
            f"🕯️ **Candle Structure:** {candle_style}\n"
            f"🤖 **Strategy Signal:** {signal_text}\n"
            f"{risk_text}"
        )

    except Exception as e:
        return f"⚠️ Calculation status update failed: {str(e)}"

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
    """Tracks markets and broadcasts updates directly every 1-minute interval loop."""
    try:
        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(), 
                text="✅ **1-Minute Update Stream Online**\nYou will now receive market report texts every 60 seconds!"
            )
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade()
            target_chat = str(CHAT_ID).strip()
            
            # REMOVED FILTER: Send the message unconditionally every 60 seconds
            async with bot:
                await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
            print("1-Minute update message sent successfully.")
            
        except Exception as e:
            print(f"Telegram Send Error: {e}")

        # Sleep for exactly 1 minute (60 seconds)
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
