import os
import asyncio
from fastapi import FastAPI
from telegram import Bot
import pandas as pd
import requests

app = FastAPI()

# 🤖 Telegram Setup (Uses the keys you saved in Render)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
telegram_bot = Bot(token=TELEGRAM_TOKEN)

# 📊 Helper to calculate your 9/26 EMAs, RSI, and 5 MACDs from raw bars
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # 1. EMAs
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # 2. RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. MACD #1: Normal (12, 26, 9)
    df['macd1_line'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd1_signal'] = df['macd1_line'].ewm(span=9, adjust=False).mean()
    
    # 4. MACD #5: Fast Execution
    df['macd5_line'] = df['close'].ewm(span=3, adjust=False).mean() - df['close'].ewm(span=6, adjust=False).mean()
    df['macd5_signal'] = df['macd5_line'].ewm(span=2, adjust=False).mean()
    
    # Swing calculations for Stop Loss
    df['low_lows'] = df['low'].rolling(window=5).min()
    df['high_highs'] = df['high'].rolling(window=5).max()
    return df

# ⚙️ Rules Engine
def check_trading_rules(df: pd.DataFrame):
    if len(df) < 30: return "Waiting for data..."
    
    current = df.iloc[-1]
    prev = df.iloc[-2]
    
    close = current['close']
    ema9 = current['ema9']
    ema26 = current['ema26']
    rsi = current['rsi']
    
    is_bullish_trend = ema9 > ema26
    is_bearish_trend = ema9 < ema26
    
    # Skip-Trade Rule: Price touching both EMAs
    is_touching_both = (current['high'] >= max(ema9, ema26)) and (current['low'] <= min(ema9, ema26))
    if is_touching_both: return "Skip Trade: Messy market."

    # MACD Crossover tracking
    macd1_bullish_alert = (prev['macd1_line'] <= prev['macd1_signal']) and (current['macd1_line'] > current['macd1_signal'])
    macd1_bearish_alert = (prev['macd1_line'] >= prev['macd1_signal']) and (current['macd1_line'] < current['macd1_signal'])
    
    macd5_bullish_cross = (prev['macd5_line'] <= prev['macd5_signal']) and (current['macd5_line'] > current['macd5_signal'])
    macd5_bearish_cross = (prev['macd5_line'] >= prev['macd5_signal']) and (current['macd5_line'] < current['macd5_signal'])

    # 🟢 BUY RULE EXECUTION
    if is_bullish_trend and close > ema9 and rsi > 30:
        if macd1_bullish_alert or current['macd1_line'] > current['macd1_signal']:
            if macd5_bullish_cross:
                return f"🟢 BUY SIGNAL MATCHED (1M)!\nPrice: {close}\nStop Loss: {current['low_lows']}"

    # 🔴 SELL RULE EXECUTION
    if is_bearish_trend and close < ema9 and rsi < 70:
        if macd1_bearish_alert or current['macd1_line'] < current['macd1_signal']:
            if macd5_bearish_cross:
                return f"🔴 SELL SIGNAL MATCHED (1M)!\nPrice: {close}\nStop Loss: {current['high_highs']}"
                
    # If no rules match, return the current price state as a placeholder
    return f"ℹ️ Market Watch: BTC is at ${close}. Waiting for strategy crossover setups..."

# 🔄 Free Live Data Fetcher Loop (Pulls from Binance Public API)
async def fetch_market_data_loop():
    while True:
        try:
            # Pull live 1-minute Bitcoin candlestick data
            url = "https://binance.com"
            response = requests.get(url).json()
            
            # Map data array
            data = [[float(c[1]), float(c[2]), float(c[3]), float(c[4])] for c in response]
            df = pd.DataFrame(data, columns=['open', 'high', 'low', 'close'])
            
            # Process and check strategy status
            df = calculate_indicators(df)
            result = check_trading_rules(df)
            
            # 🧪 TEST TRICK: Always text your phone the results so you know it works!
            await telegram_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=result)
                
        except Exception as e:
            print(f"Error fetching data: {e}")
            
        # Wait 60 seconds (1 minute) before sending the next price update log
        await asyncio.sleep(60)

# Start the worker loop when Render boots up
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(fetch_market_data_loop())

@app.get("/health")
def health_check(): 
    return {"status": "awake"}

