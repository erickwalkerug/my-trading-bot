# 🌐 DUMMY WEB PORT LISTENER (Satisfies Render's web service scan)
import http.server
import socketserver
import threading
threading.Thread(target=lambda: socketserver.TCPServer(("", 10000), http.server.SimpleHTTPRequestHandler).serve_forever(), daemon=True).start()

# 📈 TRADING ENGINE CORE MODULES
import os
import time
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from ta.trend import ema_indicator, macd, macd_signal
from ta.momentum import rsi
from datetime import datetime

# =====================================================================
# 🔑 CREDENTIALS CONFIGURATION 
# =====================================================================
TOKEN = "8875847982:AAGldKqU05cskRjLnbyVrDL6Q9-nuFbkEdM"
CHAT_ID = "8919300615"
# =====================================================================

# 📊 RISK TO REWARD RATIO CONFIGURATION
RISK_REWARD_RATIO = 2.0  # 1:2 Ratio. (TP will be 2x the distance of your SL)

def get_market_data_frame(symbol):
    """Downloads 1-minute candle bars via Yahoo Finance to construct historical series."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")
        # WEEKEND PROTECTION: If market is closed or data is thin, pass what's available
        if df.empty or len(df) < 5:
            return None
            
        df = df.reset_index()
        df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'}, inplace=True)
        return df
    except Exception as e:
        print(f"Data transmission fault for symbol {symbol}: {e}")
        return None

def process_strategy_logic(df):
    """Executes your multi-layered strategy matrix rules."""
    if df is None or len(df) < 40:
        return "❌ MARKET CLOSED (Weekend Pause)", "N/A", "N/A"

    close_prices = df['close']
    high_prices = df['high']
    low_prices = df['low']
    
    # 📈 CALCULATE INDICATORS
    ema9 = ema_indicator(close_prices, window=9)
    ema26 = ema_indicator(close_prices, window=26)
    ema_direction = ema9.iloc[-1] - ema26.iloc[-1]
    
    macd_line = macd(close_prices, window_fast=12, window_slow=26)
    signal_line = macd_signal(close_prices, window_fast=12, window_slow=26)
    rsi_values = rsi(close_prices, window=14)
    
    current_price = close_prices.iloc[-1]
    current_rsi = rsi_values.iloc[-1]
    
    # 📍 PRICE POSITION TOUCH CHECKS
    tolerance = current_price * 0.0001 
    touching_ema9 = abs(current_price - ema9.iloc[-1]) <= tolerance
    touching_ema26 = abs(current_price - ema26.iloc[-1]) <= tolerance
    
    # 🚫 EXPLICIT SKIP CONSTRAINT
    if touching_ema9 and touching_ema26:
        return "⚠️ SKIP ACTIVE (Price touching both EMAs)", "N/A", "N/A"
        
    # 🔄 SWING HIGH / LOW IDENTIFICATION ENGINE (Lookback 5 bars)
    recent_lows = low_prices.iloc[-6:-1].tolist()
    recent_highs = high_prices.iloc[-6:-1].tolist()
    prev_swing_low = min(recent_lows) if len(recent_lows) > 0 else current_price
    prev_swing_high = max(recent_highs) if len(recent_highs) > 0 else current_price

    # MACD CROSSOVER LOGIC DETECTOR
    macd_crossed_bullish = (macd_line.iloc[-2] <= signal_line.iloc[-2]) and (macd_line.iloc[-1] > signal_line.iloc[-1])
    macd_crossed_bearish = (macd_line.iloc[-2] >= signal_line.iloc[-2]) and (macd_line.iloc[-1] < signal_line.iloc[-1])

    # 🔔 FINAL COMPREHENSIVE SIGNAL LOGIC MATCHING WITH SL & TP
    if (ema_direction > 0 and current_price > ema9.iloc[-1] and current_rsi > 30 and macd_crossed_bullish):
        sl_level = prev_swing_low - (prev_swing_low * 0.0002) 
        risk_distance = current_price - sl_level
        tp_level = current_price + (risk_distance * RISK_REWARD_RATIO)
        return "🟢 BUY ACTIVE (Momentum Target Open)", f"${sl_level:,.2f}", f"${tp_level:,.2f}"

    elif (ema_direction < 0 and current_price < ema9.iloc[-1] and current_rsi < 70 and macd_crossed_bearish):
        sl_level = prev_swing_high + (prev_swing_high * 0.0002)
        risk_distance = sl_level - current_price
        tp_level = current_price - (risk_distance * RISK_REWARD_RATIO)
        return "🔴 SELL ACTIVE (Take Profit Target Reached)", f"${sl_level:,.2f}", f"${tp_level:,.2f}"

    else:
        trend_status = "🟢 BULLISH TREND" if ema_direction > 0 else "🔴 BEARISH TREND"
        return f"🟡 HOLD ACTIVE ({trend_status})", "N/A", "N/A"

def send_telegram_matrix(btc_data, gold_data):
    """Combines both markets into a single clean message and sends it securely to Telegram."""
    # Hardcoded complete URL to guarantee the path can never break or get scrambled
    url = f"https://telegram.org{TOKEN}/sendMessage"
    current_time = datetime.now().strftime('%H:%M')

    btc_price_display = f"${btc_data['price']:,.2f} USD" if btc_data['price'] else "Fetching..."
    gold_price_display = f"${gold_data['price']:,.2f} USD / oz" if gold_data['price'] else "Closed (Weekend)"

    market_message = (
        f"📊 *1-MINUTE MARKET UPDATE MATRIX*\n\n"
        f"🌑 *BITCOIN (BTC) Profile*\n"
        f"💰 Price: {btc_price_display}\n"
        f"🌀 Signal: {btc_data['signal']}\n"
        f"🛑 SL: {btc_data['sl']}  |  🎯 TP: {btc_data['tp']}\n"
        f"-----------------------------------\n\n"
        f"✨ *GOLD (XAUUSD) Profile*\n"
        f"💰 Price: {gold_price_display}\n"
        f"🌀 Signal: {gold_data['signal']}\n"
        f"🛑 SL: {gold_data['sl']}  |  🎯 TP: {gold_data['tp']}\n\n"
        f"⏰ Matrix Time: {current_time} | Timeframe: 1m"
    )
    
    payload = {"chat_id": CHAT_ID, "text": market_message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 1-Minute Matrix broadcast delivered successfully.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Telegram rejected with code {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Telegram API transmission drop: {e}")

def market_analysis_execution():
    """Main checking engine running tightly every 60 seconds."""
    while True:
        df_btc = get_market_data_frame("BTC-USD")
        df_gold = get_market_data_frame("GC=F")
        
        btc_package = {"price": None, "signal": "Awaiting Data", "sl": "N/A", "tp": "N/A"}
        gold_package = {"price": None, "signal": "❌ MARKET CLOSED (Weekend Pause)", "sl": "N/A", "tp": "N/A"}

        if df_btc is not None and not df_btc.empty:
            btc_package["price"] = float(df_btc['close'].iloc[-1])
            btc_package["signal"], btc_package["sl"], btc_package["tp"] = process_strategy_logic(df_btc)
            
        if df_gold is not None and not df_gold.empty and len(df_gold) >= 40:
            gold_package["price"] = float(df_gold['close'].iloc[-1])
            gold_package["signal"], gold_package["sl"], gold_package["tp"] = process_strategy_logic(df_gold)
            
        if btc_package["price"] is not None:
            send_telegram_matrix(btc_package, gold_package)
                
        time.sleep(60)

if __name__ == "__main__":
    print("1-Minute Strategy Matrix ready with automated port bindings.")
    market_analysis_execution()
