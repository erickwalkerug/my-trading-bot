import os
import time
import datetime
from threading import Thread
from flask import Flask
import requests

# ============================================================
# MATRIX STRATEGY ENGINE
# EARLY ENTRY VERSION
#
# TIMEFRAME: 1 MINUTE
# SCAN: EVERY 2 MINUTES
#
# INDICATORS:
# EMA 9 / EMA 26
# RSI 14
# ONE MACD 12 / 26 / 9
#
# SIGNALS:
# Sends every qualifying setup.
# Signal strength = strategy alignment score, NOT win probability.
# ============================================================


# ============================================================
# RENDER WEB SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Matrix Strategy Engine Online"


def keep_web_server_alive():
    port = int(os.environ.get("PORT", 8080))

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(token, chat_id, message):

    if not token or not chat_id:

        print("❌ Telegram credentials missing.")

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

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
# EAST AFRICAN TIME
# UTC + 3
# ============================================================

def get_eat_time():

    now_utc = datetime.datetime.now(
        datetime.timezone.utc
    )

    now_eat = (
        now_utc
        + datetime.timedelta(hours=3)
    )

    return now_eat


# ============================================================
# TRADING HOURS
# 06:00 AM - 06:00 PM EAT
# ============================================================

def trading_hours_open():

    now_eat = get_eat_time()

    current_time = now_eat.time()

    start_time = datetime.time(
        6,
        0
    )

    end_time = datetime.time(
        18,
        0
    )

    return (
        start_time
        <= current_time
        < end_time
    )


# ============================================================
# MARKET SELECTION
#
# MONDAY-FRIDAY:
# BTC + GOLD
#
# SATURDAY-SUNDAY:
# BTC ONLY
# ============================================================

def get_markets():

    now_eat = get_eat_time()

    weekday = now_eat.weekday()

    if weekday >= 5:

        return {
            "BTC": "BTC/USD"
        }

    return {
        "BTC": "BTC/USD",
        "GOLD": "XAU/USD"
    }


# ============================================================
# EMA
# ============================================================

def calculate_ema(prices, period):

    if not prices:

        return 0.0

    if len(prices) < period:

        return sum(prices) / len(prices)

    multiplier = 2 / (period + 1)

    ema = (
        sum(prices[:period])
        / period
    )

    for price in prices[period:]:

        ema = (
            (price - ema)
            * multiplier
            + ema
        )

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    prices,
    period=14
):

    if len(prices) < period + 1:

        return 50.0

    gains = []
    losses = []

    for i in range(
        1,
        len(prices)
    ):

        change = (
            prices[i]
            - prices[i - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
            )
            + losses[i]
        ) / period

    if avg_loss == 0:

        return 100.0

    rs = (
        avg_gain
        / avg_loss
    )

    return (
        100
        - (100 / (1 + rs))
    )


# ============================================================
# MACD SERIES
#
# ONE MACD ONLY
# 12 / 26 / 9
# ============================================================

def calculate_macd_series(prices):

    if len(prices) < 40:

        return None

    macd_values = []

    for i in range(
        26,
        len(prices) + 1
    ):

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

    if len(macd_values) < 12:

        return None

    signal_values = []

    for i in range(
        9,
        len(macd_values) + 1
    ):

        signal_values.append(
            calculate_ema(
                macd_values[:i],
                9
            )
        )

    if not signal_values:

        return None

    current_macd = (
        macd_values[-1]
    )

    previous_macd = (
        macd_values[-2]
    )

    current_signal = (
        signal_values[-1]
    )

    previous_signal = (
        signal_values[-2]
    )

    return {
        "macd": current_macd,
        "previous_macd": previous_macd,
        "signal": current_signal,
        "previous_signal": previous_signal,
        "macd_values": macd_values,
        "signal_values": signal_values
    }


# ============================================================
# DETECT RECENT MACD CROSS
#
# Allows an early entry shortly after a crossover.
# ============================================================

def recent_bullish_macd_cross(
    macd_values,
    signal_values,
    lookback=3
):

    usable = min(
        lookback,
        len(macd_values) - 1,
        len(signal_values) - 1
    )

    if usable <= 0:

        return False

    for i in range(
        1,
        usable + 1
    ):

        current_index = (
            len(macd_values) - i
        )

        previous_index = (
            current_index - 1
        )

        if previous_index < 0:

            continue

        current_macd = (
            macd_values[current_index]
        )

        previous_macd = (
            macd_values[previous_index]
        )

        current_signal = (
            signal_values[
                min(
                    current_index
                    - 8,
                    len(signal_values) - 1
                )
            ]
        )

        previous_signal = (
            signal_values[
                min(
                    previous_index
                    - 8,
                    len(signal_values) - 1
                )
            ]
        )

        if (
            previous_macd <= previous_signal
            and
            current_macd > current_signal
        ):

            return True

    return False


def recent_bearish_macd_cross(
    macd_values,
    signal_values,
    lookback=3
):

    usable = min(
        lookback,
        len(macd_values) - 1,
        len(signal_values) - 1
    )

    if usable <= 0:

        return False

    for i in range(
        1,
        usable + 1
    ):

        current_index = (
            len(macd_values) - i
        )

        previous_index = (
            current_index - 1
        )

        if previous_index < 0:

            continue

        current_macd = (
            macd_values[current_index]
        )

        previous_macd = (
            macd_values[previous_index]
        )

        current_signal = (
            signal_values[
                min(
                    current_index
                    - 8,
                    len(signal_values) - 1
                )
            ]
        )

        previous_signal = (
            signal_values[
                min(
                    previous_index
                    - 8,
                    len(signal_values) - 1
                )
            ]
        )

        if (
            previous_macd >= previous_signal
            and
            current_macd < current_signal
        ):

            return True

    return False


# ============================================================
# TWELVE DATA
# 1-MINUTE MARKET DATA
# ============================================================

def fetch_1m_candles(
    symbol,
    api_key
):

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
# SIGNAL INTERPRETATION
# ============================================================

def get_strength_interpretation(
    score
):

    if score >= 90:

        return (
            "🔥 VERY STRONG ALIGNMENT — "
            "multiple momentum and trend conditions agree."
        )

    if score >= 80:

        return (
            "🟢 STRONG ALIGNMENT — "
            "trend, momentum and entry conditions are strongly aligned."
        )

    if score >= 70:

        return (
            "🟡 GOOD ALIGNMENT — "
            "early setup with several confirming conditions."
        )

    if score >= 60:

        return (
            "🔵 EARLY SETUP — "
            "momentum is developing, but confirmation is weaker."
        )

    return (
        "⚪ DEVELOPING SETUP — "
        "early directional evidence is present."
    )


# ============================================================
# STRATEGY
# EARLY ENTRY SCORING ENGINE
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
    previous2 = candles[-3]

    current_price = (
        current["close"]
    )

    previous_price = (
        previous["close"]
    )

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

    previous_ema9 = calculate_ema(
        closes[:-1],
        9
    )

    previous_ema26 = calculate_ema(
        closes[:-1],
        26
    )

    # ========================================================
    # RSI
    # ========================================================

    rsi = calculate_rsi(
        closes,
        14
    )

    previous_rsi = calculate_rsi(
        closes[:-1],
        14
    )

    # ========================================================
    # MACD
    # ========================================================

    macd_data = calculate_macd_series(
        closes
    )

    if macd_data is None:

        return None

    curr_macd = macd_data["macd"]

    prev_macd = macd_data["previous_macd"]

    curr_signal = macd_data["signal"]

    prev_signal = macd_data["previous_signal"]

    macd_values = (
        macd_data["macd_values"]
    )

    signal_values = (
        macd_data["signal_values"]
    )

    # ========================================================
    # MACD CONDITIONS
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

    recent_bullish_cross = (
        recent_bullish_macd_cross(
            macd_values,
            signal_values,
            3
        )
    )

    recent_bearish_cross = (
        recent_bearish_macd_cross(
            macd_values,
            signal_values,
            3
        )
    )

    bullish_macd = (
        curr_macd > curr_signal
    )

    bearish_macd = (
        curr_macd < curr_signal
    )

    macd_rising = (
        curr_macd > prev_macd
    )

    macd_falling = (
        curr_macd < prev_macd
    )

    # ========================================================
    # PRICE MOMENTUM
    # ========================================================

    bullish_candle = (
        current["close"]
        > current["open"]
    )

    bearish_candle = (
        current["close"]
        < current["open"]
    )

    recent_price_rising = (
        current_price
        > previous_price
        > previous2["close"]
    )

    recent_price_falling = (
        current_price
        < previous_price
        < previous2["close"]
    )

    # ========================================================
    # CANDLE STRUCTURE
    # ========================================================

    higher_high = (
        current["high"]
        > previous["high"]
    )

    higher_low = (
        current["low"]
        > previous["low"]
    )

    lower_high = (
        current["high"]
        < previous["high"]
    )

    lower_low = (
        current["low"]
        < previous["low"]
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
    # EMA DIRECTION
    # ========================================================

    ema_bullish = (
        ema9 > ema26
    )

    ema_bearish = (
        ema9 < ema26
    )

    ema_bullish_crossing = (

        previous_ema9
        <= previous_ema26

        and

        ema9 > ema26
    )

    ema_bearish_crossing = (

        previous_ema9
        >= previous_ema26

        and

        ema9 < ema26
    )

    price_above_ema9 = (
        current_price > ema9
    )

    price_below_ema9 = (
        current_price < ema9
    )

    # ========================================================
    # RSI DIRECTION
    # ========================================================

    rsi_rising = (
        rsi > previous_rsi
    )

    rsi_falling = (
        rsi < previous_rsi
    )

    # Avoid buying an extremely overextended RSI.
    buy_rsi_zone = (
        30 < rsi < 75
    )

    sell_rsi_zone = (
        25 < rsi < 70
    )

    # ========================================================
    # EARLY BUY SCORE
    # ========================================================

    buy_score = 0

    buy_reasons = []

    # EMA trend/alignment
    if ema_bullish:

        buy_score += 15

        buy_reasons.append(
            "EMA9 > EMA26"
        )

    if price_above_ema9:

        buy_score += 10

        buy_reasons.append(
            "Price above EMA9"
        )

    if ema_bullish_crossing:

        buy_score += 8

        buy_reasons.append(
            "EMA bullish crossover"
        )

    # MACD
    if bullish_macd:

        buy_score += 15

        buy_reasons.append(
            "MACD bullish"
        )

    if macd_rising:

        buy_score += 10

        buy_reasons.append(
            "MACD rising"
        )

    if bullish_cross:

        buy_score += 15

        buy_reasons.append(
            "Fresh MACD crossover"
        )

    elif recent_bullish_cross:

        buy_score += 12

        buy_reasons.append(
            "Recent MACD crossover"
        )

    # RSI
    if buy_rsi_zone:

        buy_score += 8

        buy_reasons.append(
            "RSI buy zone"
        )

    if rsi_rising:

        buy_score += 5

        buy_reasons.append(
            "RSI rising"
        )

    # Price momentum
    if bullish_candle:

        buy_score += 5

        buy_reasons.append(
            "Bullish candle"
        )

    if recent_price_rising:

        buy_score += 5

        buy_reasons.append(
            "Short-term price momentum"
        )

    # Structure
    if higher_structure:

        buy_score += 4

        buy_reasons.append(
            "Higher High + Higher Low"
        )

    # ========================================================
    # EARLY SELL SCORE
    # ========================================================

    sell_score = 0

    sell_reasons = []

    # EMA trend/alignment
    if ema_bearish:

        sell_score += 15

        sell_reasons.append(
            "EMA9 < EMA26"
        )

    if price_below_ema9:

        sell_score += 10

        sell_reasons.append(
            "Price below EMA9"
        )

    if ema_bearish_crossing:

        sell_score += 8

        sell_reasons.append(
            "EMA bearish crossover"
        )

    # MACD
    if bearish_macd:

        sell_score += 15

        sell_reasons.append(
            "MACD bearish"
        )

    if macd_falling:

        sell_score += 10

        sell_reasons.append(
            "MACD falling"
        )

    if bearish_cross:

        sell_score += 15

        sell_reasons.append(
            "Fresh MACD crossover"
        )

    elif recent_bearish_cross:

        sell_score += 12

        sell_reasons.append(
            "Recent MACD crossover"
        )

    # RSI
    if sell_rsi_zone:

        sell_score += 8

        sell_reasons.append(
            "RSI sell zone"
        )

    if rsi_falling:

        sell_score += 5

        sell_reasons.append(
            "RSI falling"
        )

    # Price momentum
    if bearish_candle:

        sell_score += 5

        sell_reasons.append(
            "Bearish candle"
        )

    if recent_price_falling:

        sell_score += 5

        sell_reasons.append(
            "Short-term price momentum"
        )

    # Structure
    if lower_structure:

        sell_score += 4

        sell_reasons.append(
            "Lower High + Lower Low"
        )

    # ========================================================
    # CHOOSE DIRECTION
    # ========================================================

    if (
        buy_score >= sell_score
        and buy_score >= 55
    ):

        signal_type = "BUY"

        score = min(
            100,
            buy_score
        )

        reasons = buy_reasons

    elif (
        sell_score > buy_score
        and sell_score >= 55
    ):

        signal_type = "SELL"

        score = min(
            100,
            sell_score
        )

        reasons = sell_reasons

    else:

        return None

    # ========================================================
    # ADD INTERPRETATION
    # ========================================================

    interpretation = (
        get_strength_interpretation(
            score
        )
    )

    # ========================================================
    # ENTRY
    # ========================================================

    entry = current_price

    # ========================================================
    # STOP LOSS
    #
    # Use recent swing area.
    # ========================================================

    recent_lows = [
        c["low"]
        for c in candles[-6:-1]
    ]

    recent_highs = [
        c["high"]
        for c in candles[-6:-1]
    ]

    if signal_type == "BUY":

        direction = "🟢 BUY / LONG"

        swing_low = min(
            recent_lows
        )

        stop_loss = swing_low

        risk = (
            entry
            - stop_loss
        )

        if risk <= 0:

            return None

        take_profit = (
            entry
            + (risk * 2)
        )

    else:

        direction = "🔴 SELL / SHORT"

        swing_high = max(
            recent_highs
        )

        stop_loss = swing_high

        risk = (
            stop_loss
            - entry
        )

        if risk <= 0:

            return None

        take_profit = (
            entry
            - (risk * 2)
        )

    # ========================================================
    # EXPECTED PRICE MOVE
    # ========================================================

    if signal_type == "BUY":

        price_move = (
            take_profit
            - entry
        )

    else:

        price_move = (
            entry
            - take_profit
        )

    price_move_percent = (

        price_move
        / entry
        * 100
    )

    # ========================================================
    # ESTIMATED TRADE DURATION
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
            take_profit
            - entry
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
                estimated_minutes
                * 0.7
            )
        )

        upper_time = max(
            lower_time + 1,
            int(
                estimated_minutes
                * 1.3
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
        f"{signal_type}_"
        f"{candle_id}"
    )

    # ========================================================
    # DUPLICATE PROTECTION
    # ========================================================

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

    now_eat = get_eat_time()

    timestamp = (
        now_eat.strftime(
            "%Y-%m-%d %H:%M:%S EAT"
        )
    )

    # ========================================================
    # MACD STATUS
    # ========================================================

    if bullish_cross:

        macd_status = (
            "🔥 Fresh bullish crossover"
        )

    elif bearish_cross:

        macd_status = (
            "🔥 Fresh bearish crossover"
        )

    elif (
        signal_type == "BUY"
        and recent_bullish_cross
    ):

        macd_status = (
            "⚡ Recent bullish crossover"
        )

    elif (
        signal_type == "SELL"
        and recent_bearish_cross
    ):

        macd_status = (
            "⚡ Recent bearish crossover"
        )

    elif (
        signal_type == "BUY"
        and bullish_macd
    ):

        macd_status = (
            "📈 Bullish MACD momentum"
        )

    elif (
        signal_type == "SELL"
        and bearish_macd
    ):

        macd_status = (
            "📉 Bearish MACD momentum"
        )

    else:

        macd_status = (
            "Developing MACD setup"
        )

    # ========================================================
    # SIGNAL MESSAGE
    # ========================================================

    message = (

        f"🤖 *EARLY ENTRY SIGNAL — "
        f"{asset_name}*\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"📈 *Direction:* "
        f"{direction}\n"

        f"💯 *Signal Strength:* "
        f"{score}%\n"

        f"🧠 *Interpretation:* "
        f"{interpretation}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"📍 *Market Price:* "
        f"${entry:,.2f}\n"

        f"🎯 *Take Profit:* "
        f"${take_profit:,.2f}\n"

        f"🛑 *Stop Loss:* "
        f"${stop_loss:,.2f}\n"

        f"📊 *Expected Price Move:* "
        f"${price_move:,.2f} "
        f"({price_move_percent:.2f}%)\n"

        f"⏱️ *Estimated Duration:* "
        f"{duration_text}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"📊 *1-MIN EARLY ENTRY CHECK*\n"

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

        f"├ MACD Status: "
        f"{macd_status}\n"

        f"└ Structure: "
        f"{'Higher High + Higher Low' if signal_type == 'BUY' else 'Lower High + Lower Low'}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"🔎 *Conditions Detected:*\n"

        + "\n".join(
            f"• {reason}"
            for reason in reasons
        )

        +

        f"\n━━━━━━━━━━━━━━━━━━\n"

        f"⏰ *Time:* "
        f"{timestamp}\n"

        f"⚠️ *Signal strength is a "
        f"strategy-alignment score, "
        f"not a guaranteed win probability.*"
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
        "🔄 Scan interval: 2 minutes"
    )

    print(
        "⏰ Trading hours: "
        "06:00 AM - 06:00 PM EAT"
    )

    print(
        "📅 Weekdays: BTC + GOLD"
    )

    print(
        "📅 Saturday/Sunday: BTC ONLY"
    )

    print(
        "📈 Indicators: "
        "EMA 9 / EMA 26 + RSI + ONE MACD"
    )

    print(
        "⚡ Early-entry scoring: ENABLED"
    )

    print(
        "💯 Signal strength: 0-100%"
    )

    print(
        "📡 Qualifying signals: ALL SENT"
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

        "🔄 Scan interval: 2 minutes\n"

        "⏰ Trading hours: "
        "06:00 AM - 06:00 PM EAT\n"

        "💰 Monday-Friday: GOLD + BTC\n"

        "₿ Saturday-Sunday: BTC ONLY\n"

        "📈 EMA 9 / EMA 26\n"

        "📊 RSI(14)\n"

        "📉 ONE MACD 12/26/9\n"

        "⚡ Early-entry engine ON\n"

        "💯 Signal-strength scoring ON\n"

        "📡 All qualifying signals "
        "will be sent.\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "ℹ️ Signal strength represents "
        "strategy alignment, not a "
        "guaranteed win probability."
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

            now_eat = get_eat_time()

            # =================================================
            # TRADING HOURS
            # =================================================

            if not trading_hours_open():

                print(
                    f"⏰ Outside trading hours: "
                    f"{now_eat.strftime('%H:%M:%S')} EAT"
                )

                time.sleep(120)

                continue

            # =================================================
            # MARKETS
            # =================================================

            markets = get_markets()

            day_name = now_eat.strftime(
                "%A"
            )

            print(
                f"📅 {day_name} | "
                f"{now_eat.strftime('%H:%M:%S')} EAT"
            )

            if day_name in [
                "Saturday",
                "Sunday"
            ]:

                print(
                    "₿ Weekend mode: BTC ONLY"
                )

            else:

                print(
                    "📊 Weekday mode: BTC + GOLD"
                )

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
                # SIGNAL
                # =============================================

                if signal:

                    print(
                        f"🎯 EARLY ENTRY "
                        f"{asset} SIGNAL!"
                    )

                    send_telegram(
                        telegram_token,
                        telegram_chat_id,
                        signal
                    )

                    telegram_updates.append(

                        f"🎯 *{asset}: "
                        f"EARLY SIGNAL SENT*\n"

                        f"📍 Market Price: "
                        f"${price:,.2f}\n"

                        f"📡 Full signal "
                        f"sent above."
                    )

                # =============================================
                # NO SIGNAL
                # =============================================

                else:

                    print(
                        f"ℹ️ {asset}: "
                        f"No qualifying setup."
                    )

                    telegram_updates.append(

                        f"ℹ️ *{asset}: "
                        f"NO QUALIFYING SIGNAL*\n"

                        f"📍 Market Price: "
                        f"${price:,.2f}\n"

                        f"📊 Candles: "
                        f"{len(candles)}\n"

                        f"⏳ Monitoring early momentum."
                    )

            # =================================================
            # CURRENT TIME
            # =================================================

            now_eat = get_eat_time()

            timestamp = (
                now_eat.strftime(
                    "%Y-%m-%d %H:%M:%S EAT"
                )
            )

            # =================================================
            # 2-MINUTE TELEGRAM UPDATE
            # =================================================

            update_message = (

                "📡 *2-MINUTE "
                "MARKET UPDATE*\n"

                "━━━━━━━━━━━━━━━━━━\n"

                + "\n\n".join(
                    telegram_updates
                )

                + "\n━━━━━━━━━━━━━━━━━━\n"

                f"⏰ {timestamp}\n"

                "⚡ Early-entry detection: ON\n"

                "💯 Strength scoring: ON\n"

                "🔄 Next scan: ~2 minutes"
            )

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

            error_message = (

                "⚠️ *MATRIX BOT ERROR*\n"

                "━━━━━━━━━━━━━━━━━━\n"

                f"`{str(e)[:500]}`\n"

                "━━━━━━━━━━━━━━━━━━\n"

                "🔄 Bot will continue trying."
            )

            send_telegram(
                telegram_token,
                telegram_chat_id,
                error_message
            )

        # ====================================================
        # MAINTAIN 2-MINUTE SCAN INTERVAL
        # ====================================================

        elapsed = (
            time.time()
            - cycle_start
        )

        sleep_time = max(
            1,
            120 - elapsed
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
