import os
import time
import datetime
from threading import Thread
from flask import Flask
import requests

# =====================================================================
# 1. RENDER PORT BINDING & SELF-AWAKE WORKAROUND (100% FREE)
# =====================================================================
app = Flask('')

@app.route('/')
def home():
    return "<h1>Matrix Strategy Engine Online (Anti-Block Enabled)!</h1>"

def keep_web_server_alive():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def self_awake_loop():
    time.sleep(30)
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        return
    while True:
        try:
            requests.get(render_url, timeout=10)
        except Exception:
            pass
        time.sleep(600)

# =====================================================================
# 2. SECURE TELEGRAM UTILITY (UNCOMPROMISED DIRECT CONNECTION)
# =====================================================================
def send_secure_signal(token, chat_id, message_text):
    clean_api_url = f"https://telegram.org{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(clean_api_url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"⚠️ Telegram Transmission Error: {e}")
        return None

# =====================================================================
# 3. LIGHTWEIGHT MATHEMATICAL ENGINE (FORMULAS FROM SCRATCH)
# =====================================================================
def calculate_ema(prices, period):
    if len(prices) < period:
        return prices[-1] if prices else 0
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price * k) + (ema * (1 - k))
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0: return 100
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    macd_lines = []
    for i in range(15, len(prices) + 1):
        window = prices[:i]
        ema12 = calculate_ema(window, 12)
        ema26 = calculate_ema(window, 26)
        macd_lines.append(ema12 - ema26)
    
    if len(macd_lines) < 9:
        return 0.0, 0.0, 0.0, 0.0
        
    current_macd = macd_lines[-1]
    previous_macd = macd_lines[-2]
    current_signal = calculate_ema(macd_lines, 9)
    previous_signal = calculate_ema(macd_lines[:-1], 9)
    
    return current_macd, previous_macd, current_signal, previous_signal

# =====================================================================
# 4. DATA PIPELINE (UPDATED: ANTI-BLOCKING INFRASTRUCTURE)
# =====================================================================
def fetch_1m_candles(asset_type, gecko_key):
    try:
        if asset_type == "BTC":
            # Switched to Bybit Public Node (Does not block Render cloud server IPs)
            url = "https://bybit.com"
            res = requests.get(url, timeout=10).json()
            raw_candles = res['result']['list']
            # Bybit list is sorted newest to oldest, reverse it to match math EMA flows
            raw_candles.reverse()
            return [{
                'open': float(c[1]), 'high': float(c[2]),
                'low': float(c[3]), 'close': float(c[4])
            } for c in raw_candles]
        else:
            # Uses specialized CoinGecko Developer Key headers to bypass bot blocks
            headers = {"x-cg-demo-api-key": gecko_key} if gecko_key else {}
            url = "https://coingecko.com"
            data = requests.get(url, headers=headers, timeout=10).json()
            return [{
                'open': float(c[1]), 'high': float(c[2]),
                'low': float(c[3]), 'close': float(c[4])
            } for c in data[-50:]]
    except Exception as e:
        print(f"⚠️ Cloud Data Stream Blocked for {asset_type}: {e}")
        return []

# =====================================================================
# 5. CORE SIGNAL MATRIX ENGINE (RUNS EVERY 1 MINUTE)
# =====================================================================
def run_matrix_strategy(telegram_token, telegram_chat_id, gecko_key):
    print("🚀 Advanced Multi-Indicator Matrix Activated...")

    while True:
        try:
            for asset in ["BTC", "GOLD"]:
                candles = fetch_1m_candles(asset, gecko_key)
                if len(candles) < 30:
                    continue
                
                close_prices = [c['close'] for c in candles]
                current_price = close_prices[-1]
                prev_price = close_prices[-2]
                price_diff = current_price - prev_price
                price_pct = (price_diff / prev_price) * 100

                rsi = calculate_rsi(close_prices, 14)
                curr_macd, prev_macd, curr_sig, prev_sig = calculate_macd(close_prices)

                h0, h1 = candles[-1]['high'], candles[-2]['high']
                l0, l1 = candles[-1]['low'], candles[-2]['low']
                higher_high_low = (h0 > h1) and (l0 > l1)
                lower_high_low = (h0 < h1) and (l0 < l1)

                buy_signal = (rsi > 30) and (prev_macd <= prev_sig and curr_macd > curr_sig) and (curr_macd > 0 and curr_sig > 0) and higher_high_low
                sell_signal = (rsi < 70) and (prev_macd >= prev_sig and curr_macd < curr_sig) and (curr_macd < 0 and curr_sig < 0) and lower_high_low

                if buy_signal or sell_signal:
                    direction = "🟢 BUY / LONG" if buy_signal else "🔴 SELL / SHORT"
                    move_arrow = "↗️" if price_diff >= 0 else "↘️"
                    multiplier = 1 if buy_signal else -1
                    
                    tp_spread = 0.015 if asset == "BTC" else 0.005
                    sl_spread = 0.0075 if asset == "BTC" else 0.0025
                    
                    tp_price = current_price * (1 + (tp_spread * multiplier))
                    sl_price = current_price * (1 - (sl_spread * multiplier))
                    duration = "⏳ 5 - 15 Mins (Fast Scalp)" if asset == "BTC" else "⏳ 3 - 10 Mins (Micro Scalp)"
                    
                    utc_now = datetime.datetime.utcnow()
                    eat_now = utc_now + datetime.timedelta(hours=3)
                    timestamp = eat_now.strftime("%Y-%m-%d %H:%M:%S EAT")

                    msg = (
                        f"🤖 *CONFIRMED SIGNAL MATCH: {asset}USD*\n"
                        f"───────────────────\n"
                        f"📈 *Direction:* {direction}\n"
                        f"📊 *Market Move (1m):* {move_arrow} ${price_diff:,.2f} ({price_pct:+.2f}%)\n"
                        f"🎯 *Entry / Close:* ${current_price:,.2f}\n"
                        f"🏁 *Take Profit:* ${tp_price:,.2f}\n"
                        f"🛑 *Stop Loss:* ${sl_price:,.2f}\n"
                        f"⏱️ *Signal Duration:* {duration}\n"
                        f"⏰ *Time Sent:* {timestamp}\n"
                        f"───────────────────\n"
                        f"📝 *Indicator Breakdown Status:*\n"
                        f"├ RSI: {rsi:.2f}\n"
                        f"├ MACD Line: {curr_macd:.4f} (Signal: {curr_sig:.4f})\n"
                        f"└ Structure: {'Higher High/Low' if higher_high_low else 'Lower High/Low' if lower_high_low else 'Consolidating'}\n"
                    )
                    print(f"🎯 Strategy matched for {asset}! Sending secure message...")
                    send_secure_signal(telegram_token, telegram_chat_id, msg)
                else:
                    print(f"ℹ️ {asset} scanned. RSI: {rsi:.1f} | MACD: {curr_macd:.2f} | Indicators unaligned.")

        except Exception as loop_error:
            print(f"Runtime Warning within matrix: {loop_error}")

        time.sleep(60)

# =====================================================================
# 6. ORCHESTRATION PIPELINE (PULLING ENVIRONMENT KEYS)
# =====================================================================
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    GECKO_KEY = os.environ.get("COINGECKO_API_KEY") # Added for secure authentication

    Thread(target=keep_web_server_alive, daemon=True).start()
    Thread(target=self_awake_loop, daemon=True).start()

    run_matrix_strategy(BOT_TOKEN, CHAT_ID, GECKO_KEY)
