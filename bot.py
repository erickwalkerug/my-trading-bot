import os
import time
import datetime
import math
from threading import Thread, Lock

from flask import Flask, jsonify, request
import requests


# ============================================================
# KETS STRATEGY ENGINE
# ADVANCED EARLY ENTRY VERSION
#
# TIMEFRAME: 1 MINUTE
# SCAN: EVERY 1 MINUTE
#
# TELEGRAM:
# 1. BOT = FULL TECHNICAL / INTELLIGENCE MESSAGE
# 2. CHANNEL = CLEAN PUBLIC SIGNAL
#
# WEBSITE:
# SECURE SIGNAL API
#
# CORE RULES:
# EMA 9 / EMA 26
# RSI 14
# ONE MACD 12 / 26 / 9
# CANDLE STRUCTURE
# EARLY ENTRY SCORING
#
# ADVANCED INTELLIGENCE:
# ADX / TREND STRENGTH
# ATR / VOLATILITY
# 5-MIN CONTEXT
# 15-MIN CONTEXT
# SUPPORT / RESISTANCE
# MOMENTUM ACCELERATION
# CANDLE QUALITY
# VWAP WHEN VOLUME IS AVAILABLE
# MARKET REGIME
# DATA QUALITY
# CHASING / OVEREXTENSION PROTECTION
# SIGNAL CLASSIFICATION
#
# SIGNAL STRENGTH:
# STRATEGY-ALIGNMENT SCORE
# NOT WIN PROBABILITY
#
# WEBSITE API:
# GET /api/health
# GET /api/signals
# GET /api/signals/<asset>
#
# API RETENTION:
# MOST RECENT 7 DAYS
# ============================================================


# ============================================================
# RENDER WEB SERVER
# ============================================================

app = Flask(__name__)


# ============================================================
# KETS SECURE SIGNAL API
# ============================================================

API_KEY = os.environ.get("KETS_API_KEY")

# ============================================================
# KETS WEBSITE SIGNAL BRIDGE
# Sends every newly generated signal directly to the KETS
# website/API. Configure these in Render environment variables.
# ============================================================
KETS_SIGNAL_SOURCE_URL = os.environ.get(
    "KETS_SIGNAL_SOURCE_URL",
    "https://kets.onrender.com/api/signals"
)
KETS_SIGNAL_SOURCE_KEY = os.environ.get(
    "KETS_SIGNAL_SOURCE_KEY",
    API_KEY
).strip()

def send_signal_to_kets_website(api_signal):
    """POST a generated signal to the KETS website."""
    if not KETS_SIGNAL_SOURCE_URL:
        print("⚠️ KETS website URL is missing; signal not sent.")
        return False

    if not KETS_SIGNAL_SOURCE_KEY:
        print("⚠️ KETS website API key is missing; signal not sent.")
        return False

    try:
        response = requests.post(
            KETS_SIGNAL_SOURCE_URL,
            json=api_signal,
            headers={
                "X-KETS-API-KEY": KETS_SIGNAL_SOURCE_KEY.strip(),
                "Content-Type": "application/json",
            },
            timeout=15,
        )

        if 200 <= response.status_code < 300:
            print(
                f"✅ KETS website received signal "
                f"{api_signal.get('id')} "
                f"(HTTP {response.status_code})"
            )
            return True

        print(
            f"❌ KETS website rejected signal "
            f"{api_signal.get('id')}: "
            f"HTTP {response.status_code} "
            f"{response.text[:300]}"
        )
        return False

    except requests.RequestException as exc:
        print(
            f"❌ KETS website signal delivery failed: "
            f"{exc}"
        )
        return False


signal_history = []
engine_history = []
signal_lock = Lock()
engine_history_lock = Lock()

SIGNAL_RETENTION_DAYS = 7
ENGINE_HISTORY_RETENTION_DAYS = 7
ENGINE_HISTORY_MAX_ITEMS = 2000


def clean_old_signals():

    cutoff = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(
            days=SIGNAL_RETENTION_DAYS
        )
    )

    with signal_lock:

        kept = []

        for signal in signal_history:

            try:

                signal_time = datetime.datetime.fromisoformat(
                    signal["timestamp_utc"]
                )

                if signal_time >= cutoff:

                    kept.append(signal)

            except Exception:

                continue

        signal_history.clear()
        signal_history.extend(kept)



def clean_old_engine_history():

    cutoff = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=ENGINE_HISTORY_RETENTION_DAYS)
    )

    with engine_history_lock:
        kept = []
        for item in engine_history:
            try:
                item_time = datetime.datetime.fromisoformat(
                    item["timestamp_utc"]
                )
                if item_time >= cutoff:
                    kept.append(item)
            except Exception:
                continue

        if len(kept) > ENGINE_HISTORY_MAX_ITEMS:
            kept = kept[-ENGINE_HISTORY_MAX_ITEMS:]

        engine_history.clear()
        engine_history.extend(kept)


def save_engine_history(
    asset,
    symbol,
    price,
    candles_count,
    result,
    signal=None
):
    """Record every completed KETS market scan for the website.

    A rejected setup is history only; it is never promoted to a signal.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    timestamp_eat = get_eat_time().strftime("%Y-%m-%d %H:%M:%S EAT")

    item = {
        "id": f"SCAN-{asset}-{int(now_utc.timestamp() * 1000)}",
        "asset": asset,
        "symbol": symbol,
        "market_price": price,
        "candles": candles_count,
        "result": result,
        "status": "NO_QUALIFYING_SETUP" if result == "NO QUALIFYING SETUP" else "SIGNAL",
        "timestamp": timestamp_eat,
        "timestamp_utc": now_utc.isoformat(),
    }

    if signal:
        item.update({
            "direction": signal.get("direction"),
            "score": signal.get("score"),
            "classification": signal.get("classification"),
            "interpretation": signal.get("interpretation"),
            "entry": signal.get("entry"),
            "price": signal.get("entry"),
            "current_price": signal.get("entry"),
            "take_profit": signal.get("take_profit"),
            "stop_loss": signal.get("stop_loss"),
            "price_move": signal.get("price_move"),
            "price_move_pct": signal.get("price_move_percent"),
            "market_move": signal.get("price_move"),
            "market_move_pct": signal.get("price_move_percent"),
            "expected_price_move": signal.get("price_move"),
            "expected_price_move_percent": signal.get("price_move_percent"),
            "expected_move": signal.get("price_move"),
            "expected_move_pct": signal.get("price_move_percent"),
            "estimated_duration": signal.get("duration_text"),
        })

    with engine_history_lock:
        engine_history.append(item)

    clean_old_engine_history()
    return item



def save_signal_for_api(
    asset,
    signal
):

    now_utc = datetime.datetime.now(
        datetime.timezone.utc
    )

    api_signal = {

        "id": (
            f"{asset}-"
            f"{signal['direction']}-"
            f"{int(now_utc.timestamp())}"
        ),

        "asset":
            asset,

        "direction":
            signal["direction"],

        "score":
            signal["score"],

        "market_price":
            signal["entry"],

        "take_profit":
            signal["take_profit"],

        "stop_loss":
            signal["stop_loss"],

        # Send both the original strategy names and the dashboard aliases.
        # This prevents the website from losing fields when its renderer uses
        # a different but equivalent field name.
        "expected_price_move":
            signal["price_move"],

        "expected_price_move_percent":
            signal["price_move_percent"],

        "price_move":
            signal["price_move"],

        "price_move_pct":
            signal["price_move_percent"],

        "market_move":
            signal["price_move"],

        "market_move_pct":
            signal["price_move_percent"],

        "expected_move":
            signal["price_move"],

        "expected_move_pct":
            signal["price_move_percent"],

        "current_price":
            signal["entry"],

        "price":
            signal["entry"],

        "entry":
            signal["entry"],

        "estimated_duration":
            signal["duration_text"],

        "classification":
            signal["classification"],

        "interpretation":
            signal["interpretation"],

        "timestamp":
            now_utc.isoformat(),

        "source_timestamp_eat":
            signal["timestamp"],

        "timestamp_utc":
            now_utc.isoformat(),

        "status":
            "ACTIVE"
    }

    with signal_lock:

        signal_history.append(
            api_signal
        )

    clean_old_signals()

    return api_signal


def check_api_key():

    if not API_KEY:

        return False

    supplied_key = request.headers.get(
        "X-KETS-API-KEY"
    )

    return supplied_key == API_KEY


@app.route("/api/health")
def api_health():

    return jsonify({

        "status":
            "online",

        "service":
            "KETS Strategy Engine",

        "strategy":
            "KETS original strategy",

        "scan_interval_seconds":
            60,

        "api":
            "online",

        "engine_history":
            "online"

    })



@app.route("/api/signals", methods=["POST"])
def api_receive_signal():
    """Receive a signal pushed from the external trading bot."""
    if not check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON payload"}), 400

    required = [
        "id", "asset", "direction", "score",
        "market_price", "take_profit", "stop_loss"
    ]
    missing = [key for key in required if key not in payload]
    if missing:
        return jsonify({
            "error": "Missing required fields",
            "missing": missing
        }), 400

    with signal_lock:
        # Avoid duplicate delivery of the same signal.
        existing_ids = {
            item.get("id") for item in signal_history
        }
        if payload.get("id") not in existing_ids:
            signal_history.append(payload)

    clean_old_signals()

    print(
        f"📥 WEBSITE SIGNAL RECEIVED: "
        f"{payload.get('asset')} "
        f"{payload.get('direction')} "
        f"{payload.get('id')}"
    )

    return jsonify({
        "status": "success",
        "message": "Signal received",
        "id": payload.get("id")
    }), 201

@app.route("/api/signals")
def api_signals():

    if not check_api_key():

        return jsonify({
            "error":
                "Unauthorized"
        }), 401

    clean_old_signals()

    limit = request.args.get(
        "limit",
        default=50,
        type=int
    )

    limit = max(
        1,
        min(limit, 200)
    )

    asset = request.args.get(
        "asset"
    )

    with signal_lock:

        signals = list(
            signal_history
        )

    if asset:

        signals = [

            signal

            for signal in signals

            if signal["asset"].upper()
            == asset.upper()

        ]

    signals = list(
        reversed(signals)
    )[:limit]

    return jsonify({

        "status":
            "success",

        "count":
            len(signals),

        "signals":
            signals

    })



@app.route("/api/engine-history")
def api_engine_history():
    """Return every recent KETS scan, including rejected setups."""
    if not check_api_key():
        return jsonify({"error": "Unauthorized"}), 401

    clean_old_engine_history()

    limit = request.args.get("limit", default=200, type=int)
    limit = max(1, min(limit, 500))
    asset = request.args.get("asset")

    with engine_history_lock:
        history = list(engine_history)

    if asset:
        history = [
            item for item in history
            if item.get("asset", "").upper() == asset.upper()
        ]

    history = list(reversed(history))[:limit]

    return jsonify({
        "status": "success",
        "count": len(history),
        "retention_days": ENGINE_HISTORY_RETENTION_DAYS,
        "history": history,
    })

@app.route("/api/signals/<asset>")
def api_asset_signals(asset):

    if not check_api_key():

        return jsonify({
            "error":
                "Unauthorized"
        }), 401

    clean_old_signals()

    with signal_lock:

        signals = [

            signal

            for signal in signal_history

            if signal["asset"].upper()
            == asset.upper()

        ]

    return jsonify({

        "status":
            "success",

        "asset":
            asset.upper(),

        "count":
            len(signals),

        "signals":
            list(
                reversed(signals)
            )

    })


@app.route("/")
def home():

    return "KETS Strategy Engine Online"


def keep_web_server_alive():

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# TELEGRAM
#
# BOT AND CHANNEL RECEIVE DIFFERENT MESSAGES
# ============================================================

def send_message(
    token,
    destination_id,
    message,
    destination_name
):

    if not token:

        print(
            "❌ TELEGRAM_BOT_TOKEN is missing."
        )

        return False

    if not destination_id:

        print(
            f"⚠️ {destination_name} "
            f"destination is missing."
        )

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    payload = {

        "chat_id":
            destination_id,

        "text":
            message,

        "parse_mode":
            "Markdown"

    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        print(
            f"Telegram {destination_name}:",
            response.status_code,
            response.text[:250]
        )

        return response.status_code == 200

    except Exception as e:

        print(
            f"❌ Telegram error "
            f"({destination_name}): {e}"
        )

        return False


def send_to_bot_and_channel(
    token,
    bot_chat_id,
    channel_id,
    bot_message,
    channel_message
):

    bot_ok = send_message(
        token,
        bot_chat_id,
        bot_message,
        "BOT"
    )

    channel_ok = send_message(
        token,
        channel_id,
        channel_message,
        "CHANNEL"
    )

    return bot_ok or channel_ok


# ============================================================
# EAST AFRICAN TIME
# UTC + 3
# ============================================================

def get_eat_time():

    now_utc = datetime.datetime.now(
        datetime.timezone.utc
    )

    return (
        now_utc
        + datetime.timedelta(hours=3)
    )


# ============================================================
# TRADING HOURS
# 06:00 AM - 06:00 PM EAT
# ============================================================

def trading_hours_open():

    current_time = (
        get_eat_time().time()
    )

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

    weekday = (
        get_eat_time().weekday()
    )

    if weekday >= 5:

        # Saturday-Sunday: Bitcoin only
        return {
            "BTC": "BTC/USD"
        }

    # Monday-Friday: Gold only
    return {
        "GOLD": "XAU/USD"
    }


# ============================================================
# EMA
# ============================================================

def calculate_ema(
    prices,
    period
):

    if not prices:

        return 0.0

    if len(prices) < period:

        return (
            sum(prices)
            / len(prices)
        )

    multiplier = (
        2 / (period + 1)
    )

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
            losses.append(0.0)

        else:

            gains.append(0.0)
            losses.append(
                abs(change)
            )

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
# MACD
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

    if len(signal_values) < 2:

        return None

    return {

        "macd":
            macd_values[-1],

        "previous_macd":
            macd_values[-2],

        "signal":
            signal_values[-1],

        "previous_signal":
            signal_values[-2],

        "macd_values":
            macd_values,

        "signal_values":
            signal_values

    }


# ============================================================
# RECENT MACD CROSS
# ============================================================

def recent_macd_cross(
    macd_values,
    signal_values,
    bullish=True,
    lookback=3
):

    usable = min(
        lookback,
        len(macd_values) - 1,
        len(signal_values) - 1
    )

    if usable <= 0:

        return False

    signal_offset = (
        len(macd_values)
        - len(signal_values)
    )

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

        current_signal_index = (
            current_index
            - signal_offset
        )

        previous_signal_index = (
            previous_index
            - signal_offset
        )

        if (
            current_signal_index < 0
            or previous_signal_index < 0
            or current_signal_index >= len(signal_values)
            or previous_signal_index >= len(signal_values)
        ):

            continue

        cm = macd_values[
            current_index
        ]

        pm = macd_values[
            previous_index
        ]

        cs = signal_values[
            current_signal_index
        ]

        ps = signal_values[
            previous_signal_index
        ]

        if bullish:

            if (
                pm <= ps
                and cm > cs
            ):

                return True

        else:

            if (
                pm >= ps
                and cm < cs
            ):

                return True

    return False


# ============================================================
# ATR
# ============================================================

def calculate_atr(
    candles,
    period=14
):

    if len(candles) < period + 1:

        return 0.0

    true_ranges = []

    for i in range(
        1,
        len(candles)
    ):

        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[
            i - 1
        ]["close"]

        tr = max(

            high - low,

            abs(
                high - prev_close
            ),

            abs(
                low - prev_close
            )

        )

        true_ranges.append(tr)

    if len(true_ranges) < period:

        return 0.0

    atr = (
        sum(
            true_ranges[:period]
        )
        / period
    )

    for tr in true_ranges[period:]:

        atr = (
            (
                atr
                * (period - 1)
            )
            + tr
        ) / period

    return atr


# ============================================================
# ADX / DI
# ============================================================

def calculate_adx(
    candles,
    period=14
):

    if len(candles) < (
        period * 2 + 1
    ):

        return {

            "adx":
                0.0,

            "plus_di":
                0.0,

            "minus_di":
                0.0

        }

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(
        1,
        len(candles)
    ):

        current = candles[i]
        previous = candles[i - 1]

        up_move = (
            current["high"]
            - previous["high"]
        )

        down_move = (
            previous["low"]
            - current["low"]
        )

        if (
            up_move > down_move
            and up_move > 0
        ):

            pdm = up_move

        else:

            pdm = 0.0

        if (
            down_move > up_move
            and down_move > 0
        ):

            mdm = down_move

        else:

            mdm = 0.0

        tr = max(

            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
            )

        )

        trs.append(tr)
        plus_dm.append(pdm)
        minus_dm.append(mdm)

    if len(trs) < period:

        return {

            "adx":
                0.0,

            "plus_di":
                0.0,

            "minus_di":
                0.0

        }

    atr = (
        sum(trs[:period])
        / period
    )

    plus = (
        sum(plus_dm[:period])
        / period
    )

    minus = (
        sum(minus_dm[:period])
        / period
    )

    dx_values = []

    for i in range(
        period,
        len(trs)
    ):

        atr = (
            (
                atr
                * (period - 1)
            )
            + trs[i]
        ) / period

        plus = (
            (
                plus
                * (period - 1)
            )
            + plus_dm[i]
        ) / period

        minus = (
            (
                minus
                * (period - 1)
            )
            + minus_dm[i]
        ) / period

        if atr == 0:

            continue

        plus_di = (
            100 * plus / atr
        )

        minus_di = (
            100 * minus / atr
        )

        denominator = (
            plus_di
            + minus_di
        )

        if denominator == 0:

            dx = 0.0

        else:

            dx = (
                100
                * abs(
                    plus_di
                    - minus_di
                )
                / denominator
            )

        dx_values.append(dx)

    if not dx_values:

        return {

            "adx":
                0.0,

            "plus_di":
                0.0,

            "minus_di":
                0.0

        }

    if len(dx_values) < period:

        adx = (
            sum(dx_values)
            / len(dx_values)
        )

    else:

        adx = (
            sum(
                dx_values[:period]
            )
            / period
        )

        for dx in dx_values[period:]:

            adx = (
                (
                    adx
                    * (period - 1)
                )
                + dx
            ) / period

    if atr == 0:

        plus_di = 0.0
        minus_di = 0.0

    else:

        plus_di = (
            100 * plus / atr
        )

        minus_di = (
            100 * minus / atr
        )

    return {

        "adx":
            adx,

        "plus_di":
            plus_di,

        "minus_di":
            minus_di

    }


# ============================================================
# AGGREGATE 1-MIN CANDLES INTO HIGHER TIMEFRAMES
# ============================================================

def aggregate_candles(
    candles,
    minutes
):

    if not candles:

        return []

    grouped = {}

    for candle in candles:

        try:

            dt = datetime.datetime.strptime(
                candle["datetime"],
                "%Y-%m-%d %H:%M:%S"
            )

        except ValueError:

            try:

                dt = datetime.datetime.fromisoformat(
                    candle["datetime"]
                )

            except Exception:

                continue

        minute_bucket = (
            dt.minute
            // minutes
        ) * minutes

        bucket = dt.replace(
            minute=minute_bucket,
            second=0
        )

        key = bucket.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        if key not in grouped:

            grouped[key] = {

                "datetime":
                    key,

                "open":
                    candle["open"],

                "high":
                    candle["high"],

                "low":
                    candle["low"],

                "close":
                    candle["close"]

            }

        else:

            grouped[key]["high"] = max(
                grouped[key]["high"],
                candle["high"]
            )

            grouped[key]["low"] = min(
                grouped[key]["low"],
                candle["low"]
            )

            grouped[key]["close"] = (
                candle["close"]
            )

    return list(
        grouped.values()
    )


# ============================================================
# TIMEFRAME DIRECTION
# ============================================================

def timeframe_direction(
    candles
):

    if len(candles) < 3:

        return "NEUTRAL"

    closes = [
        c["close"]
        for c in candles
    ]

    recent = closes[-1]
    middle = closes[-2]
    older = closes[-3]

    if (
        recent > middle > older
    ):

        return "BULLISH"

    if (
        recent < middle < older
    ):

        return "BEARISH"

    fast = calculate_ema(
        closes,
        min(5, len(closes))
    )

    slow = sum(closes) / len(closes)

    if fast > slow:

        return "BULLISH"

    if fast < slow:

        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# CANDLE QUALITY
# ============================================================

def candle_quality(candle):

    candle_range = (
        candle["high"]
        - candle["low"]
    )

    if candle_range <= 0:

        return {

            "quality":
                "INVALID",

            "direction":
                "NEUTRAL",

            "strength":
                0

        }

    body = abs(
        candle["close"]
        - candle["open"]
    )

    body_ratio = (
        body
        / candle_range
    )

    upper_wick = (
        candle["high"]
        - max(
            candle["open"],
            candle["close"]
        )
    )

    lower_wick = (
        min(
            candle["open"],
            candle["close"]
        )
        - candle["low"]
    )

    if candle["close"] > candle["open"]:

        direction = "BULLISH"

        if body_ratio >= 0.70:

            quality = "STRONG BULLISH"

        elif body_ratio >= 0.45:

            quality = "GOOD BULLISH"

        else:

            quality = "WEAK BULLISH"

    elif candle["close"] < candle["open"]:

        direction = "BEARISH"

        if body_ratio >= 0.70:

            quality = "STRONG BEARISH"

        elif body_ratio >= 0.45:

            quality = "GOOD BEARISH"

        else:

            quality = "WEAK BEARISH"

    else:

        direction = "NEUTRAL"

        quality = "INDECISION"

    if body_ratio < 0.25:

        quality = "INDECISION / WEAK"

    return {

        "quality":
            quality,

        "direction":
            direction,

        "strength":
            round(
                body_ratio * 100,
                1
            ),

        "upper_wick":
            upper_wick,

        "lower_wick":
            lower_wick

    }


# ============================================================
# MOMENTUM ANALYSIS
# ============================================================

def momentum_analysis(
    candles
):

    if len(candles) < 6:

        return {

            "direction":
                "NEUTRAL",

            "state":
                "UNKNOWN",

            "change":
                0.0

        }

    closes = [
        c["close"]
        for c in candles
    ]

    recent_change = (
        closes[-1]
        - closes[-3]
    )

    previous_change = (
        closes[-3]
        - closes[-5]
    )

    if recent_change > 0:

        direction = "BULLISH"

    elif recent_change < 0:

        direction = "BEARISH"

    else:

        direction = "NEUTRAL"

    if (
        abs(recent_change)
        > abs(previous_change)
    ):

        state = "ACCELERATING"

    elif (
        abs(recent_change)
        < abs(previous_change)
    ):

        state = "WEAKENING"

    else:

        state = "STABLE"

    return {

        "direction":
            direction,

        "state":
            state,

        "change":
            recent_change

    }


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def find_levels(
    candles,
    lookback=20
):

    sample = candles[
        -lookback:
    ]

    highs = [
        c["high"]
        for c in sample
    ]

    lows = [
        c["low"]
        for c in sample
    ]

    return {

        "support":
            min(lows),

        "resistance":
            max(highs)

    }


# ============================================================
# VWAP
# ============================================================

def calculate_vwap(
    candles
):

    volume_available = all(
        (
            c.get("volume")
            is not None
        )
        for c in candles
    )

    if not volume_available:

        return None

    total_volume = 0.0
    total_value = 0.0

    for candle in candles:

        volume = candle.get(
            "volume",
            0.0
        )

        if volume <= 0:

            continue

        typical_price = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3

        total_value += (
            typical_price
            * volume
        )

        total_volume += volume

    if total_volume <= 0:

        return None

    return (
        total_value
        / total_volume
    )


# ============================================================
# MARKET REGIME
# ============================================================

def detect_market_regime(
    adx_value,
    atr,
    candles
):

    if len(candles) < 20:

        return "UNKNOWN"

    ranges = [
        c["high"] - c["low"]
        for c in candles[-20:]
    ]

    avg_range = (
        sum(ranges)
        / len(ranges)
    )

    if avg_range <= 0:

        return "UNKNOWN"

    if adx_value >= 25:

        if atr > avg_range * 1.20:

            return (
                "TRENDING / "
                "HIGH VOLATILITY"
            )

        return "TRENDING"

    if atr < avg_range * 0.75:

        return (
            "LOW VOLATILITY / "
            "RANGE"
        )

    return "RANGE / TRANSITION"


# ============================================================
# DATA QUALITY
# ============================================================

def check_data_quality(
    candles
):

    if len(candles) < 40:

        return (
            False,
            "Insufficient candles"
        )

    for candle in candles[-40:]:

        values = [

            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"]

        ]

        if not all(
            math.isfinite(v)
            for v in values
        ):

            return (
                False,
                "Invalid price data"
            )

        if (
            candle["high"]
            < candle["low"]
        ):

            return (
                False,
                "Invalid candle range"
            )

    return (
        True,
        "GOOD"
    )


# ============================================================
# CHASING / OVEREXTENSION
# ============================================================

def check_overextension(
    price,
    ema9,
    atr
):

    if atr <= 0:

        return {

            "extended":
                False,

            "distance":
                0.0

        }

    distance = abs(
        price - ema9
    )

    ratio = (
        distance
        / atr
    )

    return {

        "extended":
            ratio >= 1.50,

        "distance":
            distance,

        "ratio":
            ratio

    }




# ============================================================
# ENTRY QUALITY LAYER
#
# ADDITIVE SAFETY FILTER:
# The existing strategy score is preserved. This layer evaluates
# whether the CURRENT ENTRY is high quality enough to accompany
# a 90+ strategy-alignment score.
#
# It does not replace the existing indicators or scoring.
# ============================================================

def calculate_entry_quality(
    candles,
    signal_type,
    current_price,
    ema9,
    atr,
    adx,
    plus_di,
    minus_di,
    direction_5m,
    direction_15m,
    momentum,
    candle_info,
    vwap,
    extension
):
    """Return an additive 0-100 entry-quality assessment.

    The score measures entry conditions, not win probability.
    Missing volume/VWAP data is treated as unavailable rather than
    automatically failing the setup.
    """

    points = 0.0
    maximum = 0.0
    reasons = []

    # --------------------------------------------------------
    # HIGHER-TIMEFRAME ALIGNMENT
    # --------------------------------------------------------
    for timeframe, direction in (
        ("5M", direction_5m),
        ("15M", direction_15m)
    ):
        maximum += 10.0

        aligned = (
            signal_type == "BUY"
            and direction == "BULLISH"
        ) or (
            signal_type == "SELL"
            and direction == "BEARISH"
        )

        if aligned:
            points += 10.0
            reasons.append(
                f"{timeframe} trend aligned"
            )
        else:
            reasons.append(
                f"{timeframe} trend not aligned"
            )

    # --------------------------------------------------------
    # EMA ENTRY STRUCTURE
    #
    # EMA200 is intentionally not approximated. The current bot
    # requests 100 candles, so only EMA20/EMA50 are used here.
    # --------------------------------------------------------
    closes = [
        c["close"]
        for c in candles
    ]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    maximum += 15.0

    ema_structure = (
        signal_type == "BUY"
        and current_price > ema20 > ema50
    ) or (
        signal_type == "SELL"
        and current_price < ema20 < ema50
    )

    if ema_structure:
        points += 15.0
        reasons.append(
            "EMA20/EMA50 entry structure aligned"
        )
    else:
        reasons.append(
            "EMA20/EMA50 entry structure not aligned"
        )

    # --------------------------------------------------------
    # ADX + DI + ADX DIRECTION
    # --------------------------------------------------------
    maximum += 15.0

    previous_adx = None

    if len(candles) >= 41:
        previous_adx_data = calculate_adx(
            candles[:-1],
            14
        )
        previous_adx = previous_adx_data.get(
            "adx"
        )

    trend_direction_ok = (
        signal_type == "BUY"
        and plus_di > minus_di
    ) or (
        signal_type == "SELL"
        and minus_di > plus_di
    )

    adx_rising = (
        previous_adx is not None
        and adx > previous_adx
    )

    if (
        adx >= 25
        and trend_direction_ok
        and (
            adx_rising
            or previous_adx is None
        )
    ):
        points += 15.0
        reasons.append(
            "ADX strong and trend direction confirmed"
        )
    elif (
        adx >= 25
        and trend_direction_ok
    ):
        points += 10.0
        reasons.append(
            "ADX strong and trend direction confirmed"
        )
    else:
        reasons.append(
            "ADX/DI entry confirmation incomplete"
        )

    # --------------------------------------------------------
    # VOLUME EXPANSION
    # --------------------------------------------------------
    volumes = [
        c.get("volume")
        for c in candles
    ]

    valid_volumes = [
        v for v in volumes
        if isinstance(v, (int, float))
        and math.isfinite(v)
        and v > 0
    ]

    if len(valid_volumes) >= 21:
        current_volume = candles[-1].get(
            "volume"
        )

        previous_volumes = [
            c.get("volume")
            for c in candles[-21:-1]
            if isinstance(c.get("volume"), (int, float))
            and math.isfinite(c.get("volume"))
            and c.get("volume") > 0
        ]

        if (
            current_volume is not None
            and previous_volumes
        ):
            average_volume = (
                sum(previous_volumes)
                / len(previous_volumes)
            )

            volume_ratio = (
                current_volume
                / average_volume
                if average_volume > 0
                else 0
            )

            maximum += 15.0

            if volume_ratio >= 1.50:
                points += 15.0
                reasons.append(
                    f"Volume expansion confirmed ({volume_ratio:.2f}x)"
                )
            elif volume_ratio >= 1.00:
                points += 7.0
                reasons.append(
                    f"Volume present but not expanded ({volume_ratio:.2f}x)"
                )
            else:
                reasons.append(
                    f"Volume below recent average ({volume_ratio:.2f}x)"
                )
        else:
            reasons.append(
                "Volume unavailable for confirmation"
            )
    else:
        reasons.append(
            "Volume unavailable for confirmation"
        )

    # --------------------------------------------------------
    # STRONG CLOSE / BREAKOUT CONFIRMATION
    # --------------------------------------------------------
    maximum += 10.0

    full_range = (
        candles[-1]["high"]
        - candles[-1]["low"]
    )

    if full_range > 0:
        close_position = (
            candles[-1]["close"]
            - candles[-1]["low"]
        ) / full_range

        strong_buy_close = (
            signal_type == "BUY"
            and close_position >= 0.65
            and candles[-1]["close"] > candles[-1]["open"]
        )

        strong_sell_close = (
            signal_type == "SELL"
            and close_position <= 0.35
            and candles[-1]["close"] < candles[-1]["open"]
        )

        breakout_close = (
            signal_type == "BUY"
            and candles[-1]["close"] > candles[-2]["high"]
        ) or (
            signal_type == "SELL"
            and candles[-1]["close"] < candles[-2]["low"]
        )

        if breakout_close:
            points += 10.0
            reasons.append(
                "Breakout candle closed beyond prior range"
            )
        elif (
            (strong_buy_close or strong_sell_close)
            and candle_info.get("strength", 0) >= 55
        ):
            points += 7.0
            reasons.append(
                "Strong directional candle close"
            )
        else:
            reasons.append(
                "Candle close confirmation weak"
            )
    else:
        reasons.append(
            "Candle range unavailable"
        )

    # --------------------------------------------------------
    # MOMENTUM CONFIRMATION
    # --------------------------------------------------------
    maximum += 10.0

    momentum_aligned = (
        signal_type == "BUY"
        and momentum.get("direction") == "BULLISH"
    ) or (
        signal_type == "SELL"
        and momentum.get("direction") == "BEARISH"
    )

    if momentum_aligned:
        points += 10.0

        if momentum.get("state") == "ACCELERATING":
            reasons.append(
                "Momentum aligned and accelerating"
            )
        elif momentum.get("state") == "STABLE":
            reasons.append(
                "Momentum aligned and stable"
            )
        else:
            reasons.append(
                "Momentum aligned but weakening"
            )
    else:
        reasons.append(
            "Momentum direction conflict"
        )

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------
    if vwap is not None:
        maximum += 10.0

        vwap_aligned = (
            signal_type == "BUY"
            and current_price > vwap
        ) or (
            signal_type == "SELL"
            and current_price < vwap
        )

        if vwap_aligned:
            points += 10.0
            reasons.append(
                "VWAP aligned"
            )
        else:
            reasons.append(
                "VWAP conflict"
            )
    else:
        reasons.append(
            "VWAP unavailable"
        )

    # --------------------------------------------------------
    # EXTENSION / CHASING PROTECTION
    # --------------------------------------------------------
    maximum += 10.0

    if not extension.get("extended", False):
        points += 10.0
        reasons.append(
            "Price not excessively extended"
        )
    else:
        reasons.append(
            "Price excessively extended from EMA9"
        )

    # --------------------------------------------------------
    # BREAKOUT-RETEST QUALITY BONUS
    #
    # This is a quality bonus only. It is not required for every
    # valid trend continuation because many entries occur without
    # a clean retest.
    # --------------------------------------------------------
    maximum += 5.0

    if len(candles) >= 3:
        previous_candle = candles[-2]
        previous2_candle = candles[-3]

        buy_retest = (
            signal_type == "BUY"
            and previous_candle["close"]
            > previous2_candle["high"]
            and candles[-1]["low"]
            <= previous_candle["high"]
            and candles[-1]["close"]
            > previous_candle["high"]
        )

        sell_retest = (
            signal_type == "SELL"
            and previous_candle["close"]
            < previous2_candle["low"]
            and candles[-1]["high"]
            >= previous_candle["low"]
            and candles[-1]["close"]
            < previous_candle["low"]
        )

        if buy_retest or sell_retest:
            points += 5.0
            reasons.append(
                "Breakout retest held"
            )
        else:
            reasons.append(
                "No clean breakout retest"
            )

    # --------------------------------------------------------
    # CLEAR REVERSAL DETECTION
    #
    # This is separate from the numeric score because a clear
    # reversal should be able to veto a 90+ setup.
    # --------------------------------------------------------
    opposite_candle = (
        signal_type == "BUY"
        and candle_info.get("direction") == "BEARISH"
    ) or (
        signal_type == "SELL"
        and candle_info.get("direction") == "BULLISH"
    )

    opposite_momentum = (
        signal_type == "BUY"
        and momentum.get("direction") == "BEARISH"
    ) or (
        signal_type == "SELL"
        and momentum.get("direction") == "BULLISH"
    )

    clear_reversal = (
        opposite_candle
        and opposite_momentum
        and candle_info.get("strength", 0) >= 55
    )

    # A weakening trend alone is not called a reversal. It becomes
    # a warning and reduces quality only through the normal score.
    if clear_reversal:
        reasons.append(
            "CLEAR REVERSAL WARNING — entry veto"
        )

    if maximum > 0:
        quality_score = round(
            max(
                0.0,
                min(
                    100.0,
                    (points / maximum) * 100.0
                )
            )
        )
    else:
        quality_score = 0

    if clear_reversal:
        status = "REJECT — REVERSAL"
    elif extension.get("extended", False):
        status = "CAUTION — EXTENDED"
    elif quality_score >= 80:
        status = "HIGH QUALITY ENTRY"
    elif quality_score >= 65:
        status = "ACCEPTABLE ENTRY"
    else:
        status = "LOW QUALITY ENTRY"

    return {
        "score": quality_score,
        "status": status,
        "clear_reversal": clear_reversal,
        "ema20": ema20,
        "ema50": ema50,
        "adx_rising": adx_rising,
        "previous_adx": previous_adx,
        "reasons": reasons
    }


# ============================================================
# SIGNAL CLASSIFICATION
# ============================================================

def classify_setup(
    score,
    extended
):

    if extended:

        return (
            "⚠️ EXTENDED — "
            "move may already be stretched."
        )

    if score >= 90:

        return (
            "🔥 CONFIRMED ALIGNMENT"
        )

    if score >= 80:

        return (
            "🟢 STRONG DEVELOPING SETUP"
        )

    if score >= 70:

        return (
            "🟡 GOOD DEVELOPING SETUP"
        )

    if score >= 60:

        return (
            "🔵 EARLY SETUP"
        )

    return (
        "⚪ DEVELOPING SETUP"
    )


# ============================================================
# INTERPRETATION
# ============================================================

def get_strength_interpretation(
    score,
    extended
):

    if extended:

        return (
            "⚠️ Setup is aligned, "
            "but price is extended."
        )

    if score >= 90:

        return (
            "🔥 VERY STRONG ALIGNMENT — "
            "multiple independent factors agree."
        )

    if score >= 80:

        return (
            "🟢 STRONG ALIGNMENT — "
            "trend, momentum and context agree."
        )

    if score >= 70:

        return (
            "🟡 GOOD ALIGNMENT — "
            "early setup has several confirmations."
        )

    if score >= 60:

        return (
            "🔵 EARLY SETUP — "
            "momentum is developing."
        )

    return (
        "⚪ DEVELOPING SETUP — "
        "early directional evidence is present."
    )


# ============================================================
# TWELVE DATA
# ============================================================

def fetch_1m_candles(
    symbol,
    api_key
):

    if not api_key:

        print(
            "❌ TWELVE_DATA_API_KEY "
            "is missing."
        )

        return []

    url = (
        "https://api.twelvedata.com/"
        "time_series"
    )

    params = {

        "symbol":
            symbol,

        "interval":
            "1min",

        "outputsize":
            100,

        "timezone":
            "UTC",

        "order":
            "asc",

        "apikey":
            api_key

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

        for item in values:

            try:

                candle = {

                    "datetime":
                        item["datetime"],

                    "open":
                        float(item["open"]),

                    "high":
                        float(item["high"]),

                    "low":
                        float(item["low"]),

                    "close":
                        float(item["close"])

                }

                if "volume" in item:

                    try:

                        candle["volume"] = float(
                            item["volume"]
                        )

                    except (
                        ValueError,
                        TypeError
                    ):

                        candle["volume"] = None

                else:

                    candle["volume"] = None

                candles.append(
                    candle
                )

            except (
                KeyError,
                ValueError,
                TypeError
            ):

                continue

        return candles

    except Exception as e:

        print(
            f"Market data connection "
            f"error for {symbol}: {e}"
        )

        return []


# ============================================================
# DUPLICATE SIGNAL PROTECTION
# ============================================================

last_signal = {}


# ============================================================
# ANALYZE MARKET
# ============================================================

def analyze_market(
    asset_name,
    symbol,
    candles
):

    if len(candles) < 40:

        return None

    # ========================================================
    # DATA QUALITY
    # ========================================================

    data_ok, data_status = (
        check_data_quality(candles)
    )

    if not data_ok:

        print(
            f"⚠️ {asset_name}: "
            f"{data_status}"
        )

        return None

    closes = [
        c["close"]
        for c in candles
    ]

    current = candles[-1]
    previous = candles[-2]
    previous2 = candles[-3]

    current_price = current["close"]

    # ========================================================
    # CORE EMA
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
    # CORE RSI
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
    # CORE MACD
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
    # MACD
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
        recent_macd_cross(
            macd_values,
            signal_values,
            True,
            3
        )
    )

    recent_bearish_cross = (
        recent_macd_cross(
            macd_values,
            signal_values,
            False,
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
    # CANDLE / PRICE
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
        > previous["close"]
        > previous2["close"]
    )

    recent_price_falling = (
        current_price
        < previous["close"]
        < previous2["close"]
    )

    # ========================================================
    # STRUCTURE
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
        previous_ema9 <= previous_ema26
        and
        ema9 > ema26
    )

    ema_bearish_crossing = (
        previous_ema9 >= previous_ema26
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
    # RSI
    # ========================================================

    rsi_rising = (
        rsi > previous_rsi
    )

    rsi_falling = (
        rsi < previous_rsi
    )

    buy_rsi_zone = (
        30 < rsi < 75
    )

    sell_rsi_zone = (
        25 < rsi < 70
    )

    # ========================================================
    # CORE BUY SCORE
    # ========================================================

    buy_score = 0
    buy_reasons = []

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

    if higher_structure:

        buy_score += 4
        buy_reasons.append(
            "Higher High + Higher Low"
        )

    # ========================================================
    # CORE SELL SCORE
    # ========================================================

    sell_score = 0
    sell_reasons = []

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

    if lower_structure:

        sell_score += 4
        sell_reasons.append(
            "Lower High + Lower Low"
        )

    # ========================================================
    # CURRENT CORE DIRECTION
    #
    # EXISTING THRESHOLD PRESERVED:
    # MINIMUM 55 CORE POINTS.
    # ========================================================

    if (
        buy_score >= sell_score
        and buy_score >= 55
    ):

        signal_type = "BUY"
        core_score = buy_score
        reasons = buy_reasons

    elif (
        sell_score > buy_score
        and sell_score >= 55
    ):

        signal_type = "SELL"
        core_score = sell_score
        reasons = sell_reasons

    else:

        return None

    # ========================================================
    # ADVANCED INTELLIGENCE
    # ========================================================

    atr = calculate_atr(
        candles,
        14
    )

    adx_data = calculate_adx(
        candles,
        14
    )

    adx = adx_data["adx"]
    plus_di = adx_data["plus_di"]
    minus_di = adx_data["minus_di"]

    candle_info = candle_quality(
        current
    )

    momentum = momentum_analysis(
        candles
    )

    levels = find_levels(
        candles,
        20
    )

    vwap = calculate_vwap(
        candles
    )

    # ========================================================
    # HIGHER TIMEFRAME CONTEXT
    # ========================================================

    candles_5m = aggregate_candles(
        candles,
        5
    )

    candles_15m = aggregate_candles(
        candles,
        15
    )

    direction_5m = (
        timeframe_direction(
            candles_5m
        )
    )

    direction_15m = (
        timeframe_direction(
            candles_15m
        )
    )

    # ========================================================
    # MARKET REGIME
    # ========================================================

    regime = detect_market_regime(
        adx,
        atr,
        candles
    )

    # ========================================================
    # OVEREXTENSION
    # ========================================================

    extension = check_overextension(
        current_price,
        ema9,
        atr
    )

    extended = extension[
        "extended"
    ]

    # ========================================================
    # ENTRY QUALITY
    #
    # ADDITIVE SAFETY LAYER:
    # Existing strategy score remains unchanged. For 90+ setups,
    # the current entry must also pass this quality layer.
    # ========================================================

    entry_quality = calculate_entry_quality(
        candles,
        signal_type,
        current_price,
        ema9,
        atr,
        adx,
        plus_di,
        minus_di,
        direction_5m,
        direction_15m,
        momentum,
        candle_info,
        vwap,
        extension
    )

    entry_quality_score = entry_quality[
        "score"
    ]

    entry_quality_status = entry_quality[
        "status"
    ]

    entry_quality_reasons = entry_quality[
        "reasons"
    ]

    # ========================================================
    # ADVANCED BONUS SCORE
    # ========================================================

    advanced_bonus = 0

    advanced_reasons = []

    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    if adx >= 25:

        if signal_type == "BUY":

            if plus_di > minus_di:

                advanced_bonus += 6

                advanced_reasons.append(
                    "ADX trend + DI bullish"
                )

            else:

                advanced_bonus -= 3

                advanced_reasons.append(
                    "ADX trend but DI conflict"
                )

        else:

            if minus_di > plus_di:

                advanced_bonus += 6

                advanced_reasons.append(
                    "ADX trend + DI bearish"
                )

            else:

                advanced_bonus -= 3

                advanced_reasons.append(
                    "ADX trend but DI conflict"
                )

    elif adx >= 18:

        advanced_bonus += 2

        advanced_reasons.append(
            "Developing trend strength"
        )

    else:

        advanced_reasons.append(
            "Weak trend / ranging environment"
        )

    # --------------------------------------------------------
    # 5-MINUTE CONTEXT
    # --------------------------------------------------------

    if (
        signal_type == "BUY"
        and direction_5m == "BULLISH"
    ):

        advanced_bonus += 5

        advanced_reasons.append(
            "5M direction aligned"
        )

    elif (
        signal_type == "SELL"
        and direction_5m == "BEARISH"
    ):

        advanced_bonus += 5

        advanced_reasons.append(
            "5M direction aligned"
        )

    elif direction_5m != "NEUTRAL":

        advanced_bonus -= 2

        advanced_reasons.append(
            "5M direction conflict"
        )

    # --------------------------------------------------------
    # 15-MINUTE CONTEXT
    # --------------------------------------------------------

    if (
        signal_type == "BUY"
        and direction_15m == "BULLISH"
    ):

        advanced_bonus += 5

        advanced_reasons.append(
            "15M direction aligned"
        )

    elif (
        signal_type == "SELL"
        and direction_15m == "BEARISH"
    ):

        advanced_bonus += 5

        advanced_reasons.append(
            "15M direction aligned"
        )

    elif direction_15m != "NEUTRAL":

        advanced_bonus -= 2

        advanced_reasons.append(
            "15M direction conflict"
        )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if (
        signal_type == "BUY"
        and momentum["direction"] == "BULLISH"
    ):

        advanced_bonus += 3

        advanced_reasons.append(
            "Bullish momentum"
        )

        if momentum["state"] == "ACCELERATING":

            advanced_bonus += 3

            advanced_reasons.append(
                "Bullish momentum accelerating"
            )

        elif momentum["state"] == "WEAKENING":

            advanced_bonus -= 2

            advanced_reasons.append(
                "Bullish momentum weakening"
            )

    elif (
        signal_type == "SELL"
        and momentum["direction"] == "BEARISH"
    ):

        advanced_bonus += 3

        advanced_reasons.append(
            "Bearish momentum"
        )

        if momentum["state"] == "ACCELERATING":

            advanced_bonus += 3

            advanced_reasons.append(
                "Bearish momentum accelerating"
            )

        elif momentum["state"] == "WEAKENING":

            advanced_bonus -= 2

            advanced_reasons.append(
                "Bearish momentum weakening"
            )

    # --------------------------------------------------------
    # CANDLE QUALITY
    # --------------------------------------------------------

    if (
        signal_type == "BUY"
        and candle_info["direction"] == "BULLISH"
    ):

        if candle_info["strength"] >= 45:

            advanced_bonus += 3

            advanced_reasons.append(
                "Good bullish candle quality"
            )

    elif (
        signal_type == "SELL"
        and candle_info["direction"] == "BEARISH"
    ):

        if candle_info["strength"] >= 45:

            advanced_bonus += 3

            advanced_reasons.append(
                "Good bearish candle quality"
            )

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------

    if vwap is not None:

        if (
            signal_type == "BUY"
            and current_price > vwap
        ):

            advanced_bonus += 3

            advanced_reasons.append(
                "Price above VWAP"
            )

        elif (
            signal_type == "SELL"
            and current_price < vwap
        ):

            advanced_bonus += 3

            advanced_reasons.append(
                "Price below VWAP"
            )

        else:

            advanced_bonus -= 1

            advanced_reasons.append(
                "VWAP conflict"
            )

    # --------------------------------------------------------
    # SUPPORT / RESISTANCE
    # --------------------------------------------------------

    support = levels["support"]
    resistance = levels["resistance"]

    if atr > 0:

        if signal_type == "BUY":

            distance_to_resistance = (
                resistance
                - current_price
            )

            if (
                distance_to_resistance
                > atr * 1.0
            ):

                advanced_bonus += 3

                advanced_reasons.append(
                    "Room toward resistance"
                )

            else:

                advanced_bonus -= 3

                advanced_reasons.append(
                    "Resistance nearby"
                )

        else:

            distance_to_support = (
                current_price
                - support
            )

            if (
                distance_to_support
                > atr * 1.0
            ):

                advanced_bonus += 3

                advanced_reasons.append(
                    "Room toward support"
                )

            else:

                advanced_bonus -= 3

                advanced_reasons.append(
                    "Support nearby"
                )

    # --------------------------------------------------------
    # REGIME
    # --------------------------------------------------------

    if regime.startswith(
        "TRENDING"
    ):

        advanced_bonus += 3

        advanced_reasons.append(
            "Trend-friendly regime"
        )

    elif regime.startswith(
        "LOW VOLATILITY"
    ):

        advanced_reasons.append(
            "Low-volatility regime"
        )

    # --------------------------------------------------------
    # OVEREXTENSION
    # --------------------------------------------------------

    if extended:

        advanced_bonus -= 6

        advanced_reasons.append(
            "Price overextended from EMA9"
        )

    # ========================================================
    # FINAL SCORE
    # ========================================================

    score = max(
        0,
        min(
            100,
            core_score
            + advanced_bonus
        )
    )

    # A 90+ final strategy score is NOT enough by itself.
    # Clear reversal or excessive extension vetoes a 90+ entry.
    if (
        score >= 90
        and (
            entry_quality_score < 80
            or entry_quality["clear_reversal"]
            or extended
        )
    ):
        print(
            f"⚠️ {asset_name}: "
            f"90+ setup rejected by entry-quality filter "
            f"({entry_quality_score}/100, "
            f"{entry_quality_status})"
        )
        return None

    # ========================================================
    # SETUP CLASSIFICATION
    # ========================================================

    classification = (
        classify_setup(
            score,
            extended
        )
    )

    interpretation = (
        get_strength_interpretation(
            score,
            extended
        )
    )

    # ========================================================
    # ENTRY
    # ========================================================

    entry = current_price

    # ========================================================
    # STOP LOSS / TAKE PROFIT
    #
    # EXISTING 2:1 LOGIC PRESERVED.
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

        direction = (
            "🟢 BUY / LONG"
        )

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
            + risk * 2
        )

    else:

        direction = (
            "🔴 SELL / SHORT"
        )

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
            - risk * 2
        )

    # ========================================================
    # EXPECTED MOVE
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
    # TRADE DURATION
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
    # STRUCTURE
    # ========================================================

    structure_text = (
        "Higher High + Higher Low"
        if signal_type == "BUY"
        else
        "Lower High + Lower Low"
    )

    # ========================================================
    # LEVEL DISTANCES
    # ========================================================

    distance_to_support = (
        entry - support
    )

    distance_to_resistance = (
        resistance - entry
    )

    # ========================================================
    # TIME
    # ========================================================

    timestamp = (
        get_eat_time().strftime(
            "%Y-%m-%d %H:%M:%S EAT"
        )
    )

    # ========================================================
    # DUPLICATE PROTECTION
    # ========================================================

    candle_id = current[
        "datetime"
    ]

    signal_key = (
        f"{asset_name}_"
        f"{signal_type}_"
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
    # BOT MESSAGE
    #
    # FULL INFORMATION
    # ========================================================

    bot_message = (

        f"🤖 *KETS — "
        f"EARLY ENTRY SIGNAL — "
        f"{asset_name}*\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"📈 *Direction:* "
        f"{direction}\n"

        f"💯 *Signal Strength:* "
        f"{score}%\n"

        f"🧠 *Interpretation:* "
        f"{interpretation}\n"

        f"🏷️ *Setup:* "
        f"{classification}\n"

        f"🛡️ *Entry Quality:* "
        f"{entry_quality_score}/100 — "
        f"{entry_quality_status}\n"

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
        f"{structure_text}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"🧠 *MARKET INTELLIGENCE*\n"

        f"├ Market Regime: "
        f"{regime}\n"

        f"├ ADX: "
        f"{adx:.2f}\n"

        f"├ DI+: "
        f"{plus_di:.2f}\n"

        f"├ DI-: "
        f"{minus_di:.2f}\n"

        f"├ ATR(14): "
        f"${atr:,.2f}\n"

        f"├ Momentum: "
        f"{momentum['direction']} / "
        f"{momentum['state']}\n"

        f"├ Candle Quality: "
        f"{candle_info['quality']}\n"

        f"├ 5-MIN Direction: "
        f"{direction_5m}\n"

        f"├ 15-MIN Direction: "
        f"{direction_15m}\n"

        f"└ VWAP: "
        f"{'${:,.2f}'.format(vwap) if vwap is not None else 'Unavailable'}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"🛡️ *ENTRY QUALITY CHECKS:*\n"

        + "\n".join(
            f"• {reason}"
            for reason in entry_quality_reasons
        )

        +

        f"\n━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *LEVEL ANALYSIS*\n"

        f"├ Support: "
        f"${support:,.2f}\n"

        f"├ Resistance: "
        f"${resistance:,.2f}\n"

        f"├ Distance to Support: "
        f"${distance_to_support:,.2f}\n"

        f"└ Distance to Resistance: "
        f"${distance_to_resistance:,.2f}\n"

        f"━━━━━━━━━━━━━━━━━━\n"

        f"🔎 *CORE CONDITIONS DETECTED:*\n"

        + "\n".join(
            f"• {reason}"
            for reason in reasons
        )

        +

        f"\n━━━━━━━━━━━━━━━━━━\n"

        f"🧠 *ADVANCED INTELLIGENCE:*\n"

        + "\n".join(
            f"• {reason}"
            for reason in advanced_reasons
        )

        +

        f"\n━━━━━━━━━━━━━━━━━━\n"

        f"⏰ *Time:* "
        f"{timestamp}\n"

        f"⚠️ *Signal strength is a "
        f"strategy-alignment score, "
        f"not a guaranteed win probability.*"
    )

    # ========================================================
    # CHANNEL MESSAGE
    #
    # CLEAN PUBLIC VERSION
    # NO TOOLS / INDICATORS / CONDITIONS
    # ========================================================

    channel_message = (

        f"🤖 *KETS — "
        f"EARLY ENTRY SIGNAL — "
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

        f"⏰ *Time:* "
        f"{timestamp}\n"

        f"⚠️ *Signal strength is a "
        f"strategy-alignment score, "
        f"not a guaranteed win probability.*"
    )

    # ========================================================
    # RETURN SIGNAL
    #
    # API REQUIRES THE PUBLIC SIGNAL FIELDS BELOW.
    # ========================================================

    return {

        "bot":
            bot_message,

        "channel":
            channel_message,

        "direction":
            signal_type,

        "score":
            score,

        "entry":
            entry,

        "take_profit":
            take_profit,

        "stop_loss":
            stop_loss,

        "price_move":
            price_move,

        "price_move_percent":
            price_move_percent,

        "duration_text":
            duration_text,

        "classification":
            classification,

        "interpretation":
            interpretation,

        # Additive entry-quality fields.
        # Existing signal fields above remain unchanged.
        "entry_quality_score":
            entry_quality_score,

        "entry_quality_status":
            entry_quality_status,

        "entry_quality_reversal":
            entry_quality["clear_reversal"],

        "entry_quality_reasons": entry_quality_reasons,

        "entry_quality_required": bool(score >= 90),

        "entry_quality_passed": bool(entry_quality_score >= 80),

        "entry_quality_score": entry_quality_score,

        "entry_quality_status": entry_quality_status,
        "timestamp":
            timestamp

    }


# ============================================================
# STARTUP MESSAGES
# ============================================================

def build_startup_messages():

    bot_message = (

        "🤖 *KETS STRATEGY ENGINE ONLINE*\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "✅ Telegram bot connected\n"

        "✅ Telegram channel connected\n"

        "✅ Render service running\n"

        "🌐 Secure website API enabled\n"

        "📊 Timeframe: 1 minute\n"

        "🔄 Scan interval: 1 minute\n"

        "⏰ Trading hours: "
        "06:00 AM - 06:00 PM EAT\n"

        "💰 Monday-Friday: GOLD + BTC\n"

        "₿ Saturday-Sunday: BTC ONLY\n"

        "📈 EMA 9 / EMA 26\n"

        "📊 RSI(14)\n"

        "📉 ONE MACD 12/26/9\n"

        "🧠 ADX trend intelligence\n"

        "🌊 ATR volatility intelligence\n"

        "🕐 5M + 15M context\n"

        "🎯 Support/resistance analysis\n"

        "⚡ Momentum analysis\n"

        "🕯️ Candle-quality analysis\n"

        "📊 VWAP when volume is available\n"

        "🧠 Market-regime detection\n"

        "🛡️ Data-quality protection\n"

        "⚡ Early-entry engine ON\n"

        "💯 Advanced scoring ON\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "ℹ️ Signal strength represents "
        "strategy alignment, not a "
        "guaranteed win probability."
    )

    channel_message = (

        "🤖 *KETS STRATEGY ENGINE ONLINE*\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "✅ Signal system online\n"

        "📊 1-minute market monitoring\n"

        "🔄 New analysis every 1 minute\n"

        "⏰ Active: 06:00-18:00 EAT\n"

        "💰 Monday-Friday: GOLD + BTC\n"

        "₿ Saturday-Sunday: BTC ONLY\n"

        "⚡ Early-entry detection ON\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "📡 KETS is monitoring the market."
    )

    return (
        bot_message,
        channel_message
    )


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

    telegram_channel_id = os.environ.get(
        "TELEGRAM_CHANNEL_ID"
    )

    twelve_key = os.environ.get(
        "TWELVE_DATA_API_KEY"
    )

    # ========================================================
    # VARIABLES
    # ========================================================

    if not telegram_token:

        print(
            "❌ TELEGRAM_BOT_TOKEN missing."
        )

    if not telegram_chat_id:

        print(
            "⚠️ TELEGRAM_CHAT_ID missing."
        )

    if not telegram_channel_id:

        print(
            "⚠️ TELEGRAM_CHANNEL_ID missing."
        )

    if not twelve_key:

        print(
            "❌ TWELVE_DATA_API_KEY missing."
        )

    if not API_KEY:

        print(
            "⚠️ KETS_API_KEY missing. "
            "Website signal endpoints will "
            "return Unauthorized."
        )

    else:

        print(
            "🔐 KETS secure API key loaded."
        )

    print(
        "🚀 KETS Strategy Engine started."
    )

    print(
        "📊 Timeframe: 1 minute"
    )

    print(
        "🔄 Scan interval: 1 minute"
    )

    print(
        "⏰ Trading hours: "
        "06:00 AM - 06:00 PM EAT"
    )

    print(
        "📅 Weekdays: BTC + GOLD"
    )

    print(
        "📅 Weekend: BTC ONLY"
    )

    print(
        "🧠 Advanced intelligence ENABLED"
    )

    print(
        "📡 Bot = FULL / Channel = CLEAN"
    )

    print(
        "🌐 Website API = ENABLED"
    )

    print(
        f"🔗 KETS signal destination: "
        f"{KETS_SIGNAL_SOURCE_URL}"
    )

    print(
        "🗂️ API retention = 7 days"
    )

    # ========================================================
    # STARTUP TEST
    # ========================================================

    startup_bot, startup_channel = (
        build_startup_messages()
    )

    send_to_bot_and_channel(
        telegram_token,
        telegram_chat_id,
        telegram_channel_id,
        startup_bot,
        startup_channel
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

                time.sleep(60)

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
                    "🥇 Weekday mode: GOLD ONLY"
                )

            bot_updates = []
            channel_updates = []

            # =================================================
            # SCAN MARKETS
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
                # NO DATA
                # =============================================

                if not candles:

                    print(
                        f"⚠️ No market data "
                        f"for {asset}"
                    )

                    bot_updates.append(

                        f"❌ *{asset}*\n"
                        f"Market data unavailable."

                    )

                    channel_updates.append(

                        f"❌ *{asset}*\n"
                        f"Market data unavailable."

                    )

                    continue

                # =============================================
                # PRICE
                # =============================================

                price = candles[-1]["close"]

                print(
                    f"💵 {asset}: "
                    f"${price:,.2f} "
                    f"| Candles: "
                    f"{len(candles)}"
                )

                # =============================================
                # ANALYSIS
                # =============================================

                signal = analyze_market(
                    asset,
                    symbol,
                    candles
                )

                # Record EVERY completed scan for the website.
                # A rejected setup remains history only and does not
                # enter signal_history or get pushed as a trade signal.
                if signal:
                    save_engine_history(
                        asset,
                        symbol,
                        price,
                        len(candles),
                        "QUALIFYING SIGNAL",
                        signal
                    )
                else:
                    save_engine_history(
                        asset,
                        symbol,
                        price,
                        len(candles),
                        "NO QUALIFYING SETUP"
                    )

                # =============================================
                # SIGNAL
                # =============================================

                if signal:

                    print(
                        f"🎯 KETS {asset} "
                        f"{signal['direction']} "
                        f"SIGNAL — "
                        f"{signal['score']}%"
                    )

                    # =========================================
                    # SAVE SIGNAL FOR WEBSITE API
                    # =========================================

                    api_signal = (
                        save_signal_for_api(
                            asset,
                            signal
                        )
                    )

                    print(
                        f"🌐 API signal stored: "
                        f"{api_signal['id']}"
                    )

                    # =========================================
                    # SEND SIGNAL DIRECTLY TO KETS WEBSITE
                    # =========================================
                    send_signal_to_kets_website(
                        api_signal
                    )

                    # =========================================
                    # TELEGRAM
                    # =========================================

                    send_to_bot_and_channel(
                        telegram_token,
                        telegram_chat_id,
                        telegram_channel_id,
                        signal["bot"],
                        signal["channel"]
                    )

                    bot_updates.append(

                        f"🎯 *KETS {asset}: "
                        f"SIGNAL SENT*\n"

                        f"📈 Direction: "
                        f"{signal['direction']}\n"

                        f"💯 Strength: "
                        f"{signal['score']}%\n"

                        f"📍 Price: "
                        f"${price:,.2f}"

                    )

                    channel_updates.append(

                        f"🎯 *KETS {asset}: "
                        f"SIGNAL SENT*\n"

                        f"📍 Price: "
                        f"${price:,.2f}"

                    )

                # =============================================
                # NO SIGNAL
                # =============================================

                else:

                    print(
                        f"ℹ️ {asset}: "
                        f"No qualifying setup."
                    )

                    bot_updates.append(

                        f"ℹ️ *{asset}: "
                        f"NO QUALIFYING SIGNAL*\n"

                        f"📍 Market Price: "
                        f"${price:,.2f}\n"

                        f"📊 Candles: "
                        f"{len(candles)}\n"

                        f"⏳ Monitoring early momentum."

                    )

                    channel_updates.append(

                        f"ℹ️ *{asset}: "
                        f"NO SIGNAL*\n"

                        f"📍 Price: "
                        f"${price:,.2f}\n"

                        f"⏳ Monitoring."

                    )

            # =================================================
            # TIME
            # =================================================

            timestamp = (
                get_eat_time().strftime(
                    "%Y-%m-%d %H:%M:%S EAT"
                )
            )

            # =================================================
            # NO PERIODIC MARKET UPDATE MESSAGES
            # =================================================
            # KETS sends Telegram messages only for actual
            # qualifying signals. "NO QUALIFYING SETUP" remains
            # available in website engine history.
        except Exception as e:

            print(
                f"⚠️ KETS engine error: {e}"
            )

            error_bot = (

                "⚠️ *KETS STRATEGY "
                "ENGINE ERROR*\n"

                "━━━━━━━━━━━━━━━━━━\n"

                f"`{str(e)[:500]}`\n"

                "━━━━━━━━━━━━━━━━━━\n"

                "🔄 Engine will continue trying."

            )

            error_channel = (

                "⚠️ *KETS SYSTEM NOTICE*\n"

                "━━━━━━━━━━━━━━━━━━\n"

                "A temporary system issue "
                "was detected.\n"

                "🔄 Monitoring will continue."

            )

            send_to_bot_and_channel(
                telegram_token,
                telegram_chat_id,
                telegram_channel_id,
                error_bot,
                error_channel
            )

        # ====================================================
        # MAINTAIN 1-MINUTE SCAN
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
