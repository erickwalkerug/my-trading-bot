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

# Separate endpoints for Bitcoin and Gold (Tether Gold XAUT)
BTC_URL  = "https://binance.com"
GOLD_URL = "https://binance.com"

def fetch_asset_data(url):
    """Fetches real-time 1-minute candlestick arrays for a specific URL endpoint."""
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Data Fetch Error for {url}: {e}")
    return None

def process_strategy(raw_candles, asset_name, asset_emoji):
    """Processes your 1-minute strategy math for a single asset with correct index unpacking."""
    if not raw_candles or len(raw_candles) < 10:
        return f"{asset_emoji} **{asset_name}:** Data stream unavailable..."

    idx_curr = len(raw_candles) - 2  # Last completed closed candle
    idx_prev = len(raw_candles) - 3  # Previous closed candle

    try:
        # FIXED: Extract explicit internal list positions from the Binance package layout
        open_p  = float(raw_candles[idx_curr][1]) # Position 1 is Open Price
        high_p  = float(raw_candles[idx_curr][2]) # Position 2 is High Price
        low_p   = float(raw_candles[idx_curr][3]) # Position 3 is Low Price
        close_p = float(raw_candles[idx_curr][4]) # Position 4 is Close Price

        prev_close = float(raw_candles[idx_prev][4]) # Position 4 is Close Price

        # 1. 3-Period Simple Moving Average (SMA) Math using Close positions
        c_0 = float(raw_candles[len(raw_candles)-2][4])
        c_1 = float(raw_candles[len(raw_candles)-3][4])
        c_2 = float(raw_candles[len(raw_candles)-4][4])
        sma_3 = (c_0 + c_1 + c_2) / 3

        # 2. Trend Logic Check
        is_bullish_trend = close_p > sma_3 and close_p > prev_close
        is_bearish_trend = close_p < sma_3 and close_p < prev_close

        # 3. Candlestick Structure Tracking
        candle_range = (high_p - low_p) if (high_p - low_p) > 0 else 0.0001
        candle_body  = abs(close_p - open_p)
        upper_wick   = high_p - max(open_p, close_p)
        lower_wick   = min(open_p, close_p) - low_p

        is_rejection   = (upper_wick > (candle_range * 0.4)) or (lower_wick > (candle_range * 0.4))
        is_strong_body = candle_body > (candle_range * 0.5)

        if is_rejection:
            candle_style = "Wick Rejection ⚠️"
        elif is_strong_body:
            candle_style = "Strong Momentum 🚀"
        else:
            candle_style = "Neutral / Doji ⏳"

        # 4. Support/Resistance Swing Channels for Stop Loss (pulls from Low position [3] and High position)
        recent_lows = [float(candle[3]) for candle in raw_candles[-6:-1]]
        recent_highs = [float(candle[2]) for candle in raw_candles[-6:-1]]
        local_swing_low = min(recent_lows)
        local_swing_high = max(recent_highs)

        # 5. Compile Separate Dynamic Signal Tags
        if is_bullish_trend:
            signal_text = "🟢 BUY ACTIVE"
            risk_text = f"🛡️ Stop Loss: ${local_swing_low:,.2f}"
        elif is_bearish_trend:
            signal_text = "🔴 SELL ACTIVE"
            risk_text = f"🛡️ Stop Loss: ${local_swing_high:,.2f}"
        else:
            signal_text = "⚪ NEUTRAL SCAN"
            risk_text = "🛡️ Stop Loss: No active setup"

        # Return formatted block for this specific asset
        return (
            f"{asset_emoji} **{asset_name} Profile**\n"
            f"💰 Price: ${close_p:,.2f} USD\n"
            f"📈 SMA (3): ${sma_3:,.2f}\n"
            f"🕯️ Candle: {candle_style}\n"
            f"🤖 Signal: {signal_text}\n"
            f"{risk_text}\n"
        )

    except Exception as e:
        return f"{asset_emoji} **{asset_name}:** Calculation failed ({str(e)})"

def analyze_and_trade_dual():
    """Gathers data for both streams and joins them together."""
    btc_candles = fetch_asset_data(BTC_URL)
    gold_candles = fetch_asset_data(GOLD_URL)

    # Process each asset independently with clear distinguishing labels
    btc_report  = process_strategy(btc_candles, "BITCOIN (BTC)", "🪙")
    gold_report = process_strategy(gold_candles, "GOLD (XAUT)", "✨")

    # Combine both individual profiles into a single easy-to-read message payload
    combined_summary = (
        f"📊 **1-MINUTE MARKET UPDATE MATRIX**\n\n"
        f"{btc_report}\n"
        f"-------------------------------------\n\n"
        f"{gold_report}"
    )
    return combined_summary

@app.get("/")
def home():
    return {"status": "dual_bot_running", "system": "active"}

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
                text="✅ **Dual Matrix Update Stream Online**\nNow scanning Bitcoin 🪙 and Gold ✨ together every 60 seconds!"
            )
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade_dual()
            target_chat = str(CHAT_ID).strip()
            
            async with bot:
                await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
            print("Dual asset 1-minute matrix update successfully sent.")
            
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
