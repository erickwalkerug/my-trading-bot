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
        print("❌ Telegram credentials missing.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        print(
            "Telegram:",
            response.status_code,
            response.text[:300]
        )

        return response.status_code == 200

    except Exception as e:

        print(
            f"❌ Telegram error: {e}"
        )

        return False


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

        ema = (
            (price - ema) * multiplier
            + ema
        )

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

        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

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

        ema12 = calculate_ema(
            window,
            12
        )

        ema26 = calculate_ema(
            window,
            26
        )

        macd_values.append(
            ema12 - ema26
        )

    if len(macd_values) < 10:
        return None

    current_macd = macd_values[-1]
    previous_macd = macd_values[-2]

    current_signal = calculate_ema(
        macd_values,
        9
    )

    previous_signal = calculate_ema(
        macd_values[:-1],
        9
    )

    return (
        current_macd,
        previous_macd,
        current_signal,
        previous_signal
    )


# ============================================================
# TWELVE DATA
# 1-MINUTE MARKET DATA
# ============================================================

def fetch_1m_candles(symbol, api_key):

    if not api_key:

        print(
            "❌ ERROR: "
            "TWELVE_DATA_API_KEY is missing."
        )

        return []

    url = (
        "https://api.twelvedata.com/time_series"
    )

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
                f"Market API HTTP error "
                f"for {symbol}: "
                f"{response.status_code}"
            )

            return []

        data = response.json()

        if data.get("status") == "error":

            print(
                f"Market API error "
                f"for {symbol}: "
                f"{data.get('message', 'Unknown error')}"
            )

            return []

        values = data.get(
            "values",
            []
        )

        candles = []

        for c in values:

            try:

                candles.append({

                    "datetime":
                        c["datetime"],

                    "open":
                        float(c["open"]),

                    "high":
                        float(c["high"]),

                    "low":
                        float(c["low"]),

                    "close":
                        float(c["close"])
                })

            except (
                KeyError,
                ValueError,
                TypeError
            ):

                continue

        return candles

    except Exception as e:

        print(
            f"Market data connection error "
            f"for {symbol}: {e}"
        )

        return []


# ============================================================
# DUPLICATE SIGNAL PROTECTION
# ============================================================

last_signal = {}


# ============================================================
# STRATEGY
# ============================================================

def analyze_market(
    asset_name,
    symbol,
    candles
):

    if len(candles) < 40:
        return None

    closes = [
        c["close"]
        for c in candles
    ]

    current = candles[-1]
    previous = candles[-2]

    current_price = current["close"]

    # ========================================================
    # EMA 9 / EMA 26
    # ========================================================

    ema9 = calculate_ema(
        closes,
        9
    )

    ema26 = calculate_ema(
        closes,
        26
    )

    # ========================================================
    # RSI
    # ========================================================

    rsi = calculate_rsi(
        closes,
        14
    )

    # ========================================================
    # ONE MACD
    # ========================================================

    macd = calculate_macd(
        closes
    )

    if macd is None:
        return None

    (
        curr_macd,
        prev_macd,
        curr_signal,
        prev_signal
    ) = macd

    # ========================================================
    # CANDLE STRUCTURE
    # ========================================================

    current_high = current["high"]
    previous_high = previous["high"]

    current_low = current["low"]
    previous_low = previous["low"]

    higher_high = (
        current_high > previous_high
    )

    higher_low = (
        current_low > previous_low
    )

    lower_high = (
        current_high < previous_high
    )

    lower_low = (
        current_low < previous_low
    )

    higher_structure = (
        higher_high
        and higher_low
    )

    lower_structure = (
        lower_high
        and lower_low
    )

    # ========================================================
    # MACD CROSS
    # ========================================================

    bullish_cross = (

        prev_macd <= prev_signal

        and

        curr_macd > curr_signal
    )

    bearish_cross = (

        prev_macd >= prev_signal

        and

        curr_macd < curr_signal
    )

    # ========================================================
    # DIRECTION
    # ========================================================

    bullish_direction = (

        ema9 > ema26

        and

        current_price > ema9
    )

    bearish_direction = (

        ema9 < ema26

        and

        current_price < ema9
    )

    # ========================================================
    # RSI
    #
    # BUY above 30
    # SELL below 70
    # ========================================================

    buy_rsi = rsi > 30

    sell_rsi = rsi < 70

    # ========================================================
    # FINAL BUY
    # ========================================================

    buy_signal = (

        bullish_direction

        and

        bullish_cross

        and

        buy_rsi

        and

        higher_structure
    )

    # ========================================================
    # FINAL SELL
    # ========================================================

    sell_signal = (

        bearish_direction

        and

        bearish_cross

        and

        sell_rsi

        and

        lower_structure
    )

    # ========================================================
    # NO SIGNAL
    # ========================================================

    if not buy_signal and not sell_signal:
        return None

    # ========================================================
    # STOP LOSS + TAKE PROFIT
    # ========================================================

    if buy_signal:

        direction = "🟢 BUY / LONG"

        entry = current_price

        swing_low = min(

            candles[-5]["low"],

            candles[-4]["low"],

            candles[-3]["low"],

            candles[-2]["low"]
        )

        stop_loss = swing_low

        risk = (
            entry - stop_loss
        )

        if risk <= 0:
            return None

        # 2R TAKE PROFIT

        take_profit = (
            entry + (risk * 2)
        )

    else:

        direction = "🔴 SELL / SHORT"

        entry = current_price

        swing_high = max(

            candles[-5]["high"],

            candles[-4]["high"],

            candles[-3]["high"],

            candles[-2]["high"]
        )

        stop_loss = swing_high

        risk = (
            stop_loss - entry
        )

        if risk <= 0:
            return None

        # 2R TAKE PROFIT

        take_profit = (
            entry - (risk * 2)
        )

    # ========================================================
    # EXPECTED MARKET PRICE MOVE
    # ========================================================

    price_move = (
        take_profit - entry
    )

    price_move_percent = (

        price_move
        / entry
        * 100
    )

    # ========================================================
    # ESTIMATED TRADE DURATION
    #
    # Based on recent 1-minute candle ranges.
    # This is ONLY an estimate.
    # ========================================================

    recent_ranges = []

    for candle in candles[-10:]:

        candle_range = (
            candle["high"]
            - candle["low"]
        )

        if candle_range > 0:

            recent_ranges.append(
                candle_range
            )

    if recent_ranges:

        average_range = (
            sum(recent_ranges)
            / len(recent_ranges)
        )

        distance_to_tp = abs(
            take_profit - entry
        )

        estimated_minutes = (

            distance_to_tp
            / average_range
        )

        estimated_minutes = max(
            1,
            estimated_minutes
        )

        lower_time = max(
            1,
            int(
                estimated_minutes * 0.7
            )
        )

        upper_time = max(

            lower_time + 1,

            int(
                estimated_minutes * 1.3
            )
        )

        duration_text = (
            f"{lower_time}-"
            f"{upper_time} minutes"
        )

    else:

        duration_text = (
            "Unable to estimate"
        )

    # ========================================================
    # SIGNAL CANDLE ID
    # ========================================================

    candle_id = current[
        "datetime"
    ]

    signal_key = (
        f"{asset_name}_"
        f"{direction}_"
        f"{candle_id}"
    )

    if last_signal.get(
        asset_name
    ) == signal_key:

        return None

    last_signal[
        asset_name
    ] = signal_key

    # ========================================================
    # TIME
    # ========================================================

    now_utc = datetime.datetime.now(
        datetime.timezone.utc
    )

    now_eat = (
        now_utc
        + datetime.timedelta(
            hours=3
        )
    )

    timestamp = (
        now_eat.strftime(
            "%Y-%m-%d %H:%M:%S EAT"
        )
    )

    # ========================================================
    # SIGNAL MESSAGE
    # ========================================================

    move_sign = (
        "+"
        if price_move >= 0
        else ""
    )

    percent_sign = (
        "+"
        if price_move_percent >= 0
        else ""
    )

    structure_text = (

        "Higher High + Higher Low"

        if buy_signal

        else

        "Lower High + Lower Low"
    )

    message = (

        f"🤖 *CONFIRMED SIGNAL — "
        f"{asset_name}*\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"📈 *Direction:* "
        f"{direction}\n"

        f"📍 *Market Price:* "
        f"${entry:,.2f}\n"

        f"🎯 *Take Profit:* "
        f"${take_profit:,.2f}\n"

        f"🛑 *Stop Loss:* "
        f"${stop_loss:,.2f}\n"

        f"📊 *Expected Price Move:* "
        f"{move_sign}"
        f"${price_move:,.2f} "
        f"({percent_sign}"
        f"{price_move_percent:.2f}%)\n"

        f"⏱️ *Estimated Duration:* "
        f"{duration_text}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"📊 *1-MIN STRATEGY CHECK*\n"

        f"├ EMA 9: "
        f"${ema9:,.2f}\n"

        f"├ EMA 26: "
        f"${ema26:,.2f}\n"

        f"├ RSI(14): "
        f"{rsi:.2f}\n"

        f"├ MACD: "
        f"{curr_macd:.5f}\n"

        f"├ Signal: "
        f"{curr_signal:.5f}\n"

        f"└ Structure: "
        f"{structure_text}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"⏰ *Time:* "
        f"{timestamp}\n"

        f"⚠️ *Signal only — "
        f"manage risk carefully.*"
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

    # ========================================================
    # CHECK VARIABLES
    # ========================================================

    if not telegram_token:

        print(
            "❌ TELEGRAM_BOT_TOKEN "
            "is missing."
        )

    if not telegram_chat_id:

        print(
            "❌ TELEGRAM_CHAT_ID "
            "is missing."
        )

    if not twelve_key:

        print(
            "❌ TWELVE_DATA_API_KEY "
            "is missing."
        )

    print(
        "🚀 Matrix Strategy Engine started."
    )

    print(
        "📊 Timeframe: 1 minute"
    )

    print(
        "📈 Indicators: "
        "EMA 9 / EMA 26 + RSI + ONE MACD"
    )

    print(
        "💰 Markets: BTC/USD + XAU/USD"
    )

    # ========================================================
    # TELEGRAM STARTUP TEST
    # ========================================================

    startup_message = (

        "🤖 *MATRIX STRATEGY "
        "ENGINE ONLINE*\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "✅ Telegram connected\n"

        "✅ Render service running\n"

        "📊 Timeframe: 1 minute\n"

        "💰 Markets: GOLD + BTC\n"

        "📈 EMA 9 / EMA 26\n"

        "📊 RSI(14)\n"

        "📉 ONE MACD\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "🔄 Market updates will be "
        "sent every minute.\n\n"

        "ℹ️ You will receive an update "
        "even when there is NO "
        "COMPLETE SETUP."
    )

    send_telegram(

        telegram_token,

        telegram_chat_id,

        startup_message
    )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while True:

        cycle_start = time.time()

        try:

            markets = {

                "BTC":
                    "BTC/USD",

                "GOLD":
                    "XAU/USD"
            }

            telegram_updates = []

            # =================================================
            # SCAN EACH MARKET
            # =================================================

            for asset, symbol in markets.items():

                print(
                    f"🔎 Scanning {asset} "
                    f"({symbol})..."
                )

                candles = fetch_1m_candles(

                    symbol,

                    twelve_key
                )

                # =============================================
                # NO MARKET DATA
                # =============================================

                if not candles:

                    print(
                        f"⚠️ No market data "
                        f"for {asset}"
                    )

                    telegram_updates.append(

                        f"❌ *{asset}*\n"

                        f"Market data unavailable."
                    )

                    continue

                # =============================================
                # CURRENT PRICE
                # =============================================

                price = candles[-1]["close"]

                print(

                    f"💵 {asset}: "
                    f"${price:,.2f} "

                    f"| Candles: "
                    f"{len(candles)}"
                )

                # =============================================
                # ANALYZE
                # =============================================

                signal = analyze_market(

                    asset,

                    symbol,

                    candles
                )

                # =============================================
                # CONFIRMED SIGNAL
                # =============================================

                if signal:

                    print(

                        f"🎯 CONFIRMED "
                        f"{asset} SIGNAL!"
                    )

                    # Send signal
                    send_telegram(

                        telegram_token,

                        telegram_chat_id,

                        signal
                    )

                    telegram_updates.append(

                        f"🎯 *{asset}: "
                        f"SIGNAL CONFIRMED*\n"

                        f"📍 Market Price: "
                        f"${price:,.2f}\n"

                        f"🟢 Full signal "
                        f"sent above."
                    )

                # =============================================
                # NO COMPLETE SETUP
                # =============================================

                else:

                    print(

                        f"ℹ️ {asset}: "
                        f"No complete setup."
                    )

                    telegram_updates.append(

                        f"ℹ️ *{asset}: "
                        f"NO COMPLETE SETUP*\n"

                        f"📍 Market Price: "
                        f"${price:,.2f}\n"

                        f"📊 Candles: "
                        f"{len(candles)}\n"

                        f"⏳ Waiting for all "
                        f"strategy conditions."
                    )

            # =================================================
            # CURRENT TIME
            # =================================================

            now_utc = datetime.datetime.now(
                datetime.timezone.utc
            )

            now_eat = (

                now_utc

                + datetime.timedelta(
                    hours=3
                )
            )

            timestamp = (

                now_eat.strftime(
                    "%Y-%m-%d %H:%M:%S EAT"
                )
            )

            # =================================================
            # EVERY-MINUTE TELEGRAM UPDATE
            # =================================================

            update_message = (

                "📡 *1-MINUTE "
                "MARKET UPDATE*\n"

                "━━━━━━━━━━━━━━━━━━\n"

                + "\n\n".join(
                    telegram_updates
                )

                + "\n━━━━━━━━━━━━━━━━━━\n"

                f"⏰ {timestamp}\n"

                "🔄 Next update: "
                "~1 minute"
            )

            # ALWAYS SEND UPDATE
            send_telegram(

                telegram_token,

                telegram_chat_id,

                update_message
            )

        except Exception as e:

            print(
                f"⚠️ Strategy engine "
                f"error: {e}"
            )

            # =============================================
            # SEND ERROR TO TELEGRAM
            # =============================================

            error_message = (

                "⚠️ *MATRIX BOT ERROR*\n"

                "━━━━━━━━━━━━━━━━━━\n"

                f"`{str(e)[:500]}`\n"

                "━━━━━━━━━━━━━━━━━━\n"

                "🔄 Bot will continue "
                "trying."
            )

            send_telegram(

                telegram_token,

                telegram_chat_id,

                error_message
            )

        # ====================================================
        # MAINTAIN APPROXIMATELY 1-MINUTE SCAN INTERVAL
        # ====================================================

        elapsed = (
            time.time()
            - cycle_start
        )

        sleep_time = max(

            1,

            60 - elapsed
        )

        print(

            f"⏱️ Next scan in "
            f"{sleep_time:.1f} seconds."
        )

        time.sleep(
            sleep_time
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    Thread(

        target=keep_web_server_alive,

        daemon=True

    ).start()

    run_strategy()
