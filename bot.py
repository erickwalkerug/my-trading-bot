import os
import pandas as pd
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
from telegram.request import HTTPXRequest
import asyncio

app = FastAPI()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "8919300615")

tg_request = HTTPXRequest(connection_pool_size=8, read_timeout=10, write_timeout=10)
bot = Bot(token=TELEGRAM_TOKEN, request=tg_request)

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Live 1-minute streaming candle endpoint from Binance API
DATA_URL = "https://binance.com"

def fetch_market_data():
    """Fetches real 1-minute candlestick data from the market."""
    try:
        response = requests.get(DATA_URL, headers=API_HEADERS, timeout=5)
        if response.status_code == 200:
            raw = response.json()
            df = pd.DataFrame(raw, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "q_volume", "trades", "taker_base", "taker_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)
            return df
    except Exception as e:
        print(f"Data Fetch Error: {e}")
    return None

# --- Native Math Implementations replacing pandas_ta ---
def calculate_ema(series, period):
    """Calculates Exponential Moving Average using pure pandas math."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    """Calculates Relative Strength Index using pure pandas math."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast, slow, signal, multiplier):
    """Calculates custom MACD with scalar multipliers natively."""
    m_fast = int(fast * multiplier)
    m_slow = int(slow * multiplier)
    m_signal = int(signal * multiplier)
    
    ema_fast = calculate_ema(series, m_fast)
    ema_slow = calculate_ema(series, m_slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, m_signal)
    hist_line = macd_line - signal_line
    return macd_line, signal_line, hist_line

def calculate_atr(df, period=14):
    """Calculates Average True Range natively."""
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def analyze_and_trade():
    """Applies your exact 1-minute multi-indicator framework with pure math."""
    df = fetch_market_data()
    if df is None or len(df) < 140:
        return "⚠️ Status: System gathering market candle data..."

    # Focus on index -2 (the last fully completed 1-minute candlestick)
    idx = len(df) - 2
    prev_idx = len(df) - 3
    
    close_series = df["close"]
    close_p = close_series.iloc[idx]
    high_p = df["high"].iloc[idx]
    low_p = df["low"].iloc[idx]
    open_p = df["open"].iloc[idx]

    # 1. Base EMA calculations
    ema9_series = calculate_ema(close_series, 9)
    ema26_series = calculate_ema(close_series, 26)
    ema9 = ema9_series.iloc[idx]
    ema26 = ema26_series.iloc[idx]

    # 2. RSI calculations
    rsi_series = calculate_rsi(close_series, 14)
    rsi = rsi_series.iloc[idx]

    # 3. Process all 5 custom MACD Multipliers natively
    m1_line, m1_sig, m1_hist = calculate_macd(close_series, 12, 26, 9, 1)
    m2_line, m2_sig, m2_hist = calculate_macd(close_series, 12, 26, 9, 2)
    m3_line, m3_sig, m3_hist = calculate_macd(close_series, 12, 26, 9, 3)
    _, _, m4_hist = calculate_macd(close_series, 12, 26, 9, 4)
    m5_line, m5_sig, _ = calculate_macd(close_series, 12, 26, 9, 5)

    # 4. Check for final execution crossovers on the 5th MACD
    m5_cross_buy = (m5_line.iloc[prev_idx] <= m5_sig.iloc[prev_idx]) and (m5_line.iloc[idx] > m5_sig.iloc[idx])
    m5_cross_sell = (m5_line.iloc[prev_idx] >= m5_sig.iloc[prev_idx]) and (m5_line.iloc[idx] < m5_sig.iloc[idx])

    # 5. Determine general direction (1st MACD lines relative to 0)
    is_bullish_dir = (m1_line.iloc[idx] > 0) and (m1_sig.iloc[idx] > 0)
    is_bearish_dir = (m1_line.iloc[idx] < 0) and (m1_sig.iloc[idx] < 0)

    # 6. Rule Out: Choppy market filter (Average True Range filter)
    atr_series = calculate_atr(df, 14)
    atr = atr_series.iloc[idx]
    if atr < (close_p * 0.00015):
        return "🛑 SKIP: Market environment is too choppy for stable 1m execution."

    # 7. Rule Out: Price touching both EMA 9 and EMA 26 at the same time
    touching_ema9 = (low_p <= ema9 <= high_p)
    touching_ema26 = (low_p <= ema26 <= high_p)
    if touching_ema9 and touching_ema26:
        return "🛑 SKIP: Price is overlapping both EMA 9 and EMA 26 concurrently."

    # 8. Math-Backed Candlestick Structure Confirmation
    candle_body = abs(close_p - open_p)
    candle_range = high_p - low_p if (high_p - low_p) > 0 else 0.00001
    upper_wick = high_p - max(open_p, close_p)
    lower_wick = min(open_p, close_p) - low_p

    is_rejection = (upper_wick > (candle_range * 0.45)) or (lower_wick > (candle_range * 0.45))
    is_continuation = candle_body > (candle_range * 0.55)
    
    if not (is_rejection or is_continuation):
        return "🛑 SKIP: Weak or unclear candlestick confirmation layout."

    # 9. Track dynamic swing structures for Stop Loss boundaries
    local_swing_low = df["low"].iloc[-15:-2].min()
    local_swing_high = df["high"].iloc[-15:-2].max()

    # -----------------------------------------------------------------------
    # CRITERIA EVALUATION FOR BUY / SELL SETUPS
    # -----------------------------------------------------------------------
    
    # BUY Trigger Conditions
    if is_bullish_dir and m5_cross_buy:
        if close_p > ema9 and rsi > 30:
            if m1_hist.iloc[idx] > 0 and m2_hist.iloc[idx] > 0 and m3_hist.iloc[idx] > 0 and m4_hist.iloc[idx] > 0:
                stop_loss = local_swing_low - (atr * 0.1)
                return (
                    f"🚀 **BUY SETUP TRIGGERED** 🚀\n\n"
                    f"💰 Entry Price: ${close_p:,.2f} USD\n"
                    f"📈 RSI Level: {rsi:.2f}\n"
                    f"🎯 5th MACD Cross: Confirmed\n"
                    f"🛡️ Target Stop Loss (Below Swing HL): ${stop_loss:,.2f} USD"
                )
            else:
                return "🛑 SKIP: Signal aborted due to conflicting multi-MACD momentum alignment."

    # SELL Trigger Conditions
    if is_bearish_dir and m5_cross_sell:
        if close_p < ema9 and rsi < 70:
            if m1_hist.iloc[idx] < 0 and m2_hist.iloc[idx] < 0 and m3_hist.iloc[idx] < 0 and m4_hist.iloc[idx] < 0:
                stop_loss = local_swing_high + (atr * 0.1)
                return (
                    f"⚠️ **SELL SETUP TRIGGERED** ⚠️\n\n"
                    f"💰 Entry Price: ${close_p:,.2f} USD\n"
                    f"📉 RSI Level: {rsi:.2f}\n"
                    f"🎯 5th MACD Cross: Confirmed\n"
                    f"🛡️ Target Stop Loss (Above Swing LH): ${stop_loss:,.2f} USD"
                )
            else:
                return "🛑 SKIP: Signal aborted due to conflicting multi-MACD momentum alignment."

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
                text="✅ **Matrix Bot Online**\nYour math-optimized, compiler-safe bot is successfully active!"
            )
            print("Startup notification sent successfully.")
    except Exception as e:
        print(f"Startup Telegram Error: {e}.")

    while True:
        try:
            summary = analyze_and_trade()
            target_chat = str(CHAT_ID).strip()
            
            if "⏳" not in summary:
                async with bot:
                    await bot.send_message(chat_id=target_chat, text=summary, parse_mode="Markdown")
                print("Strategic milestone alert dispatched to Telegram!")
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
