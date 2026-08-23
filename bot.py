import os
import time
import datetime
from threading import Thread
from flask import Flask
import requests

# ============================================================
# RENDER WEB SERVER
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Matrix Strategy Engine Online"

def keep_web_server_alive():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(token, chat_id, message):
    if not token or not chat_id:
        print("Telegram credentials missing.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        print("Telegram:", response.status_code, response.text[:300])
    except Exception as e:
        print("Telegram error:", e)

# ============================================================
# EMA
# ============================================================

def calculate_ema(prices, period):
    if not prices:
        return 0.0

    if len(prices) < period:
        return sum(prices) / len(prices)

    multiplier = 2 / (period + 1)

    ema = sum(prices[:period]) / period

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return ema

# ============================================================
# RSI
# ============================================================

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))

# ============================================================
# ONE MACD ONLY
# MACD = 12 / 26 / 9
# ============================================================

def calculate_macd(prices):
    if len(prices) < 40:
        return None

    macd_values = []

    for i in range(26, len(prices) + 1):

        window = prices[:i]

        ema12 = calculate_ema(window, 12)
        ema26 = calculate_ema(window, 26)

        macd_values.append(ema12 - ema26)

    if len(macd_values) < 10:
        return None

    current_macd = macd_values[-1]
    previous_macd = macd_values[-2]

    current_signal = calculate_ema(macd_values, 9)
    previous_signal = calculate_ema(macd_values[:-1], 9)

    return (
        current_macd,
        previous_macd,
        current_signal,
        previous_signal
    )

# ============================================================
# TWELVE DATA MARKET DATA
# ============================================================

def fetch_1m_candles(symbol, api_key):

    if not api_key:
        print("ERROR: TWELVE_DATA_API_KEY is missing.")
        return []

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": symbol,
        "interval": "1min",
        "outputsize": 100,
        "timezone": "UTC",
        "order": "asc",
        "apikey": api_key
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            print(
                f"Market API HTTP error for {symbol}: "
                f"{response.status_code}"
            )
            return []

        data = response.json()

        if data.get("status") == "error":
            print(
                f"Market API error for {symbol}: "
                f"{data.get('message', 'Unknown error')}"
            )
            return []

        values = data.get("values", [])

        candles = []

        for c in values:

            try:
                candles.append({
                    "datetime": c["datetime"],
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"])
                })

            except (KeyError, ValueError, TypeError):
                continue

        return candles

    except Exception as e:

        print(
            f"Market data connection error for {symbol}: {e}"
        )

        return []

# ============================================================
# DUPLICATE SIGNAL PROTECTION
# ============================================================

last_signal = {}

# ============================================================
# STRATEGY
# ============================================================

def analyze_market(asset_name, symbol, candles):

    if len(candles) < 40:
        return None

    closes = [c["close"] for c in candles]

    current = candles[-1]
    previous = candles[-2]

    current_price = current["close"]

    # --------------------------------------------------------
    # EMA 9 / EMA 26
    # --------------------------------------------------------

    ema9 = calculate_ema(closes, 9)
    ema26 = calculate_ema(closes, 26)

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = calculate_rsi(closes, 14)

    # --------------------------------------------------------
    # ONE MACD
    # --------------------------------------------------------

    macd = calculate_macd(closes)

    if macd is None:
        return None

    curr_macd, prev_macd, curr_signal, prev_signal = macd

    # --------------------------------------------------------
    # CANDLE STRUCTURE
    # --------------------------------------------------------

    current_high = current["high"]
    previous_high = previous["high"]

    current_low = current["low"]
    previous_low = previous["low"]

    higher_high = current_high > previous_high
    higher_low = current_low > previous_low

    lower_high = current_high < previous_high
    lower_low = current_low < previous_low

    higher_structure = higher_high and higher_low
    lower_structure = lower_high and lower_low

    # --------------------------------------------------------
    # MACD CROSS
    # --------------------------------------------------------

    bullish_cross = (
        prev_macd <= prev_signal
        and curr_macd > curr_signal
    )

    bearish_cross = (
        prev_macd >= prev_signal
        and curr_macd < curr_signal
    )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    bullish_direction = (
        ema9 > ema26
        and current_price > ema9
    )

    bearish_direction = (
        ema9 < ema26
        and current_price < ema9
    )

    # --------------------------------------------------------
    # RSI
    # User rule:
    # BUY above 30
    # SELL below 70
    # --------------------------------------------------------

    buy_rsi = rsi > 30
    sell_rsi = rsi < 70

    # --------------------------------------------------------
    # FINAL BUY
    # --------------------------------------------------------

    buy_signal = (
        bullish_direction
        and bullish_cross
        and buy_rsi
        and higher_structure
    )

    # --------------------------------------------------------
    # FINAL SELL
    # --------------------------------------------------------

    sell_signal = (
        bearish_direction
        and bearish_cross
        and sell_rsi
        and lower_structure
    )

    if not buy_signal and not sell_signal:
        return None

    # --------------------------------------------------------
    # SWING STOP LOSS
    # --------------------------------------------------------

    if buy_signal:

        direction = "🟢 BUY / LONG"

        entry = current_price

        # Previous swing low
        swing_low = min(
            candles[-5]["low"],
            candles[-4]["low"],
            candles[-3]["low"],
            candles[-2]["low"]
        )

        stop_loss = swing_low

        # Risk-based TP: 2R
        risk = entry - stop_loss

        if risk <= 0:
            return None

        take_profit = entry + (risk * 2)

    else:

        direction = "🔴 SELL / SHORT"

        entry = current_price

        # Previous swing high
        swing_high = max(
            candles[-5]["high"],
            candles[-4]["high"],
            candles[-3]["high"],
            candles[-2]["high"]
        )

        stop_loss = swing_high

        risk = stop_loss - entry

        if risk <= 0:
            return None

        take_profit = entry - (risk * 2)

    # --------------------------------------------------------
    # SIGNAL CANDLE ID
    # --------------------------------------------------------

    candle_id = current["datetime"]

    signal_key = f"{asset_name}_{direction}_{candle_id}"

    if last_signal.get(asset_name) == signal_key:
        return None

    last_signal[asset_name] = signal_key

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    now_utc = datetime.datetime.now(
        datetime.timezone.utc
    )

    now_eat = now_utc + datetime.timedelta(hours=3)

    timestamp = now_eat.strftime(
        "%Y-%m-%d %H:%M:%S EAT"
    )

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    message = (
        f"🤖 *CONFIRMED SIGNAL — {asset_name}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 *Direction:* {direction}\n"
        f"🎯 *Entry:* ${entry:,.2f}\n"
        f"🏁 *Take Profit:* ${take_profit:,.2f}\n"
        f"🛑 *Stop Loss:* ${stop_loss:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *1-MIN STRATEGY CHECK*\n"
        f"├ EMA 9: ${ema9:,.2f}\n"
        f"├ EMA 26: ${ema26:,.2f}\n"
        f"├ RSI(14): {rsi:.2f}\n"
        f"├ MACD: {curr_macd:.5f}\n"
        f"├ Signal: {curr_signal:.5f}\n"
        f"└ Structure: "
        f"{'Higher High + Higher Low' if buy_signal else 'Lower High + Lower Low'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ *Time:* {timestamp}\n"
        f"⚠️ *Signal only — manage risk carefully.*"
    )

    return message

# ============================================================
# MAIN ENGINE
# ============================================================

def run_strategy():

    telegram_token = os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )

    telegram_chat_id = os.environ.get(
        "TELEGRAM_CHAT_ID"
    )

    twelve_key = os.environ.get(
        "TWELVE_DATA_API_KEY"
    )

    if not telegram_token:
        print("❌ TELEGRAM_BOT_TOKEN is missing.")

    if not telegram_chat_id:
        print("❌ TELEGRAM_CHAT_ID is missing.")

    if not twelve_key:
        print("❌ TWELVE_DATA_API_KEY is missing.")

    print("🚀 Matrix Strategy Engine started.")
    print("📊 Timeframe: 1 minute")
    print("📈 Indicators: EMA 9 / EMA 26 + RSI + ONE MACD")
    print("💰 Markets: BTC/USD + XAU/USD")

    while True:

        try:

            markets = {
                "BTC": "BTC/USD",
                "GOLD": "XAU/USD"
            }

            for asset, symbol in markets.items():

                print(
                    f"🔎 Scanning {asset} "
                    f"({symbol})..."
                )

                candles = fetch_1m_candles(
                    symbol,
                    twelve_key
                )

                if not candles:

                    print(
                        f"⚠️ No market data for {asset}"
                    )

                    continue

                price = candles[-1]["close"]

                print(
                    f"💵 {asset}: ${price:,.2f} "
                    f"| Candles: {len(candles)}"
                )

                signal = analyze_market(
                    asset,
                    symbol,
                    candles
                )

                if signal:

                    print(
                        f"🎯 CONFIRMED {asset} SIGNAL!"
                    )

                    send_telegram(
                        telegram_token,
                        telegram_chat_id,
                        signal
                    )

                else:

                    print(
                        f"ℹ️ {asset}: "
                        f"No complete setup."
                    )

        except Exception as e:

            print(
                f"⚠️ Strategy engine error: {e}"
            )

        # Scan approximately once every minute
        time.sleep(60)

# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    Thread(
        target=keep_web_server_alive,
        daemon=True
    ).start()

    run_strategy()
