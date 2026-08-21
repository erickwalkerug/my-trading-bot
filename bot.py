import os
from fastapi import FastAPI, Request
from telegram import Bot
import pandas as pd
import pydantic
import asyncio

app = FastAPI()

# 🤖 Telegram Setup (Get these from BotFather and your chat)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
telegram_bot = Bot(token=TELEGRAM_TOKEN)

# 📊 Helper to calculate technical indicators
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # 1. EMAs
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # 2. RSI (Relative Strength Index)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. The 5 MACD Structures (MACD Line = Fast - Slow)
    # MACD #1: Normal (12, 26, 9)
    df['macd1_line'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd1_signal'] = df['macd1_line'].ewm(span=9, adjust=False).mean()
    
    # MACD #5: Fast Execution (Multiplied speed)
    df['macd5_line'] = df['close'].ewm(span=3, adjust=False).mean() - df['close'].ewm(span=6, adjust=False).mean()
    df['macd5_signal'] = df['macd5_line'].ewm(span=2, adjust=False).mean()
    
    # Simple Swing High / Swing Low logic for Stop Loss
    df['low_lows'] = df['low'].rolling(window=5).min()
    df['high_highs'] = df['high'].rolling(window=5).max()
    
    return df

# ⚙️ Rules Engine
def check_trading_rules(df: pd.DataFrame):
    if len(df) < 30:
        return "Not enough data yet."

    # Get the latest closed candle data
    current = df.iloc[-1]
    prev = df.iloc[-2]
    
    close = current['close']
    ema9 = current['ema9']
    ema26 = current['ema26']
    rsi = current['rsi']
    
    # 1. Trend Direction Rules
    is_bullish_trend = ema9 > ema26
    is_bearish_trend = ema9 < ema26
    
    # 2. Skip-Trade Filter: Is price touching BOTH EMAs?
    # (If price high is above the top EMA and price low is below the bottom EMA, it's touching both)
    top_ema = max(ema9, ema26)
    bot_ema = min(ema9, ema26)
    is_touching_both = (current['high'] >= top_ema) and (current['low'] <= bot_ema)
    
    if is_touching_both:
        return "Skip Trade: Price is messy and touching both EMAs."

    # 3. Check MACD Crossovers (Current state vs Previous state)
    macd1_bullish_alert = (prev['macd1_line'] <= prev['macd1_signal']) and (current['macd1_line'] > current['macd1_signal'])
    macd1_bearish_alert = (prev['macd1_line'] >= prev['macd1_signal']) and (current['macd1_line'] < current['macd1_signal'])
    
    macd5_bullish_cross = (prev['macd5_line'] <= prev['macd5_signal']) and (current['macd5_line'] > current['macd5_signal'])
    macd5_bearish_cross = (prev['macd5_line'] >= prev['macd5_signal']) and (current['macd5_line'] < current['macd5_signal'])

    # 🟢 BUY RULE EXECUTION
    if is_bullish_trend and close > ema9 and rsi > 30:
        if macd1_bullish_alert or current['macd1_line'] > current['macd1_signal']: # MACD #1 Alert active
            if macd5_bullish_cross: # MACD #5 Confirms
                stop_loss = current['low_lows']
                return f"🟢 BUY SIGNAL MATCHED!\nPrice: {close}\nStop Loss: {stop_loss}\nRSI: {round(rsi, 2)}"

    # 🔴 SELL RULE EXECUTION
    if is_bearish_trend and close < ema9 and rsi < 70:
        if macd1_bearish_alert or current['macd1_line'] < current['macd1_signal']: # MACD #1 Alert active
            if macd5_bearish_cross: # MACD #5 Confirms
                stop_loss = current['high_highs']
                return f"🔴 SELL SIGNAL MATCHED!\nPrice: {close}\nStop Loss: {stop_loss}\nRSI: {round(rsi, 2)}"

    return "Watching market... No rules triggered."

# 📡 Webhook Target: Send chart data here from TradingView or your data source
@app.post("/webhook")
async def receive_signals(request: Request):
    data = await request.json()
    
    # Expecting data format: {"candles": [{"close": 60000, "high": 60100, "low": 59900, "open": 60000}, ...]}
    if "candles" in data:
        df = pd.DataFrame(data["candles"])
        df = calculate_indicators(df)
        result = check_trading_rules(df)
        
        # Send to telegram if it's an actionable signal
        if "SIGNAL MATCHED" in result:
            await telegram_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=result)
            return {"status": "Signal sent to Telegram", "details": result}
        
        return {"status": "Processed", "message": result}
    
    return {"status": "Error", "message": "Invalid candle data format received."}

# 😴 Keep-Alive route for Render Free Tier
@app.get("/health")
def health_check():
    return {"status": "awake"}
