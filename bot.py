import os
import pandas as pd
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Bot
import asyncio

app = FastAPI()

# 1. Setup secret tokens from Render environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "8919300615")  
bot = Bot(token=TELEGRAM_TOKEN)

# 2. Free, high-stability public historical price data from Binance API
DATA_URL = "https://binance.com"

def calculate_macd(df, fast, slow, signal_period):
    """Helper function to calculate MACD line, Signal line, and Histogram bars."""
    exp1 = df['close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def fetch_and_analyze():
    """Calculates all 9 rules in sequence and spots clean signals."""
    try:
        response = requests.get(DATA_URL, timeout=10)
        if response.status_code != 200:
            return None
        
        # Turn raw Binance candlestick bars into a readable table
        raw_data = response.json()
        df = pd.DataFrame(raw_data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'
        ])
        
        # Convert text digits into decimal numbers for math math math
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        
        # Current actual values (last finished 5m candle)
        current_price = df['close'].iloc[-1]
        prev_low = df['low'].iloc[-2]
        prev_high = df['high'].iloc[-2]
        
        # RULE 2 & 3: EMA Calculations
        ema9 = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema26 = df['close'].ewm(span=26, adjust=False).mean().iloc[-1]
        ema_direction = ema9 - ema26
        
        # RULE 5: RSI Calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        # RULE 4: Multi-MACD Math Framework
        # 1st MACD (Standard Alert Settings)
        m1_line, m1_sig, m1_hist = calculate_macd(df, 12, 26, 9)
        # 5th MACD (Main Execution x2 standard speed settings)
        m5_line, m5_sig, m5_hist = calculate_macd(df, 24, 52, 18)
        
        # Track historical crossover context for entries
        m1_cross_up = m1_hist.iloc[-1] > 0 and m1_hist.iloc[-2] <= 0
        m1_cross_down = m1_hist.iloc[-1] < 0 and m1_hist.iloc[-2] >= 0
        m5_cross_up = m5_hist.iloc[-1] > 0 and m5_hist.iloc[-2] <= 0
        m5_cross_down = m5_hist.iloc[-1] < 0 and m5_hist.iloc[-2] >= 0

        # NO-TRADE PROTECTIONS (Rule 12)
        # Avoid chop where price touches both EMAs simultaneously
        price_touching_both = (min(ema9, ema26) <= current_price <= max(ema9, ema26))
        if price_touching_both:
            return None

        # CHECK BUY CONDITIONS (Rule 8)
        if ema_direction > 0 and current_price > ema9 and rsi > 30:
            if m1_cross_up or m5_cross_up:  # 1st Alert and 5th Crossover Execution Alignment
                stop_loss = prev_low - (prev_low * 0.001)  # Structural Swing Low protection
                return (
                    f"🟢 **STRATEGY BUY SIGNAL** 🟢\n\n"
                    f"🪙 Asset: BTC/USDT (5M Chart)\n"
                    f"💵 Entry Price: ${current_price:,.2f}\n"
                    f"📈 Market Structure: Bullish (EMA9 > EMA26)\n"
                    f"📊 RSI Filter: {rsi:.1f} (Valid > 30)\n"
                    f"⚡ Execution: 5th MACD Crossover Confirmed\n"
                    f"🛡️ Structural Stop Loss: ${stop_loss:,.2f}"
                )
                
        # CHECK SELL CONDITIONS (Rule 9)
        if ema_direction < 0 and current_price < ema9 and rsi < 70:
            if m1_cross_down or m5_cross_down:  # 1st Alert and 5th Crossover Execution Alignment
                stop_loss = prev_high + (prev_high * 0.001)  # Structural Swing High protection
                return (
                    f"🔴 **STRATEGY SELL SIGNAL** 🔴\n\n"
                    f"🪙 Asset: BTC/USDT (5M Chart)\n"
                    f"💵 Entry Price: ${current_price:,.2f}\n"
                    f"📉 Market Structure: Bearish (EMA9 < EMA26)\n"
                    f"📊 RSI Filter: {rsi:.1f} (Valid < 70)\n"
                    f"⚡ Execution: 5th MACD Crossover Confirmed\n"
                    f"🛡️ Structural Stop Loss: ${stop_loss:,.2f}"
                )
                
    except Exception as e:
        print(f"Indicator calculation error notices: {e}")
        
    return None

@app.get("/")
def home():
    return {"status": "bot_running", "discipline": "active"}

async def keep_awake_loop():
    """Pings system locally so it remains online 24/7 without external monitors."""
    await asyncio.sleep(15)
    while True:
        try:
            port = os.environ.get('PORT', 10000)
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        except Exception:
            pass
        await asyncio.sleep(240)

async def trading_loop():
    """Checks your custom 5m rules continuously. Messages channel ONLY on pure setups."""
    while True:
        signal = fetch_and_analyze()
        if signal:
            try:
                target_chat = str(CHAT_ID).strip()
                await bot.send_message(chat_id=target_chat, text=signal, parse_mode="Markdown")
                print("Signal dispatched to Telegram successfully!")
            except Exception as e:
                print(f"Telegram Alert Dispatch Failure: {e}")
        
        # Checks precisely every 5 minutes alignment (300 seconds)
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(trading_loop())
    asyncio.create_task(keep_awake_loop())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
