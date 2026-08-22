import os
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import pandas as pd
import numpy as np
from fastapi import FastAPI
import uvicorn
from telegram import Bot

# ============================================================
# CONFIGURATION
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Optional real gold-data provider
GOLD_API_KEY = os.environ.get("GOLD_API_KEY")

BTC_SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"

# Number of candles needed for calculations
CANDLE_LIMIT = 250

# Prevent repeated alerts on the same candle
last_alert = {
    "BTC": None,
    "GOLD": None
}

# ============================================================
# APP
# ============================================================

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.warning("Telegram credentials are not configured.")
        return

    try:
        bot = Bot(token=TELEGRAM_TOKEN)

        async with bot:
            await bot.send_message(
                chat_id=str(CHAT_ID).strip(),
                text=message
            )

    except Exception as e:
        logger.error(f"Telegram error: {e}")


# ============================================================
# BTC LIVE DATA
# ============================================================

async def get_btc_candles():
    """
    Gets real BTC/USDT 1-minute candles from Binance.
    """

    url = "https://data-api.binance.vision/api/v3/klines"

    params = {
        "symbol": BTC_SYMBOL,
        "interval": TIMEFRAME,
        "limit": CANDLE_LIMIT
    }

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:

                if response.status != 200:
                    raise Exception(
                        f"Binance HTTP {response.status}"
                    )

                data = await response.json()

        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "buy_volume",
            "buy_quote_volume",
            "ignore"
        ]

        df = pd.DataFrame(data, columns=columns)

        for column in ["open", "high", "low", "close", "volume"]:
            df[column] = pd.to_numeric(df[column])

        df["open_time"] = pd.to_datetime(
            df["open_time"],
            unit="ms",
            utc=True
        )

        return df

    except Exception as e:
        logger.error(f"BTC data error: {e}")
        return None


# ============================================================
# GOLD LIVE DATA
# ============================================================

async def get_gold_price():
    """
    Real gold feed.

    GOLD_API_KEY must be supplied through Render environment
    variables.

    Expected provider:
        https://www.goldapi.io/

    If the key is missing, NO fake gold price is generated.
    """

    if not GOLD_API_KEY:
        return None

    url = "https://www.goldapi.io/api/XAU/USD"

    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:

            async with session.get(
                url,
                headers=headers
            ) as response:

                if response.status != 200:
                    logger.error(
                        f"Gold API HTTP {response.status}"
                    )
                    return None

                data = await response.json()

        price = data.get("price")

        if price is None:
            return None

        return float(price)

    except Exception as e:
        logger.error(f"Gold data error: {e}")
        return None


# ============================================================
# INDICATORS
# ============================================================

def ema(series, period):
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    average_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    average_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = average_gain / average_loss.replace(
        0,
        np.nan
    )

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


def calculate_macd(series, multiplier=1):

    fast_period = 12 * multiplier
    slow_period = 26 * multiplier
    signal_period = 9 * multiplier

    fast = ema(series, fast_period)
    slow = ema(series, slow_period)

    macd_line = fast - slow

    signal_line = ema(
        macd_line,
        signal_period
    )

    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


# ============================================================
# SWING DETECTION
# ============================================================

def find_previous_swing_low(df, lookback=20):

    lows = df["low"].iloc[-lookback:-1]

    if len(lows) == 0:
        return None

    return float(lows.min())


def find_previous_swing_high(df, lookback=20):

    highs = df["high"].iloc[-lookback:-1]

    if len(highs) == 0:
        return None

    return float(highs.max())


def find_higher_low(df):

    if len(df) < 10:
        return False

    recent = df.iloc[-6:-1]

    previous_low = float(
        recent["low"].iloc[:2].min()
    )

    latest_low = float(
        recent["low"].iloc[-2:].min()
    )

    return latest_low > previous_low


def find_lower_high(df):

    if len(df) < 10:
        return False

    recent = df.iloc[-6:-1]

    previous_high = float(
        recent["high"].iloc[:2].max()
    )

    latest_high = float(
        recent["high"].iloc[-2:].max()
    )

    return latest_high < previous_high


# ============================================================
# STRATEGY ENGINE
# ============================================================

def analyze_market(df):

    if df is None or len(df) < 100:
        return {
            "signal": "WAIT",
            "reason": "Not enough live candles"
        }

    df = df.copy()

    # --------------------------------------------------------
    # EMA 9 / EMA 26
    # --------------------------------------------------------

    df["ema9"] = ema(df["close"], 9)
    df["ema26"] = ema(df["close"], 26)

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    df["rsi"] = calculate_rsi(
        df["close"],
        14
    )

    # --------------------------------------------------------
    # FIVE MACD LEVELS
    #
    # MACD 1 = normal
    # MACD 2 = x5
    # MACD 3 = x4
    # MACD 4 = x3
    # MACD 5 = x2
    # --------------------------------------------------------

    macd_settings = {
        1: 1,
        2: 5,
        3: 4,
        4: 3,
        5: 2
    }

    macds = {}

    for number, multiplier in macd_settings.items():

        macd_line, signal_line, histogram = calculate_macd(
            df["close"],
            multiplier
        )

        macds[number] = {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    # --------------------------------------------------------
    # CURRENT / PREVIOUS VALUES
    # --------------------------------------------------------

    current = df.iloc[-1]
    previous = df.iloc[-2]

    price = float(current["close"])

    ema9_now = float(current["ema9"])
    ema26_now = float(current["ema26"])

    rsi_now = float(current["rsi"])

    # --------------------------------------------------------
    # EMA DIRECTION
    # --------------------------------------------------------

    bullish_direction = (
        ema9_now > ema26_now
    )

    bearish_direction = (
        ema9_now < ema26_now
    )

    # --------------------------------------------------------
    # PRICE MUST PREVAIL ON ONE EMA
    #
    # Touching both EMAs = SKIP
    # --------------------------------------------------------

    tolerance = price * 0.00015

    touching_ema9 = abs(price - ema9_now) <= tolerance
    touching_ema26 = abs(price - ema26_now) <= tolerance

    touching_both = (
        touching_ema9 and touching_ema26
    )

    if touching_both:

        return {
            "signal": "SKIP",
            "reason": "Price touching both EMAs",
            "price": price
        }

    # --------------------------------------------------------
    # MACD 1
    # ENTRY ALERT
    # --------------------------------------------------------

    m1_now = macds[1]["macd"].iloc[-1]
    m1_prev = macds[1]["macd"].iloc[-2]

    s1_now = macds[1]["signal"].iloc[-1]
    s1_prev = macds[1]["signal"].iloc[-2]

    bullish_macd1_cross = (
        m1_prev <= s1_prev
        and m1_now > s1_now
    )

    bearish_macd1_cross = (
        m1_prev >= s1_prev
        and m1_now < s1_now
    )

    # --------------------------------------------------------
    # MACD 5
    # EXECUTION CONFIRMATION
    # --------------------------------------------------------

    m5_now = macds[5]["macd"].iloc[-1]
    m5_prev = macds[5]["macd"].iloc[-2]

    s5_now = macds[5]["signal"].iloc[-1]
    s5_prev = macds[5]["signal"].iloc[-2]

    bullish_macd5_cross = (
        m5_prev <= s5_prev
        and m5_now > s5_now
    )

    bearish_macd5_cross = (
        m5_prev >= s5_prev
        and m5_now < s5_now
    )

    # --------------------------------------------------------
    # PREVIOUS HIGH / LOW
    # --------------------------------------------------------

    previous_swing_low = find_previous_swing_low(df)
    previous_swing_high = find_previous_swing_high(df)

    higher_low = find_higher_low(df)
    lower_high = find_lower_high(df)

    # ========================================================
    # BUY CONDITIONS
    # ========================================================

    buy_conditions = [
        bullish_direction,
        price > ema9_now,
        not touching_both,
        rsi_now > 30,
        bullish_macd1_cross,
        bullish_macd5_cross,
        higher_low
    ]

    # ========================================================
    # SELL CONDITIONS
    # ========================================================

    sell_conditions = [
        bearish_direction,
        price < ema9_now,
        not touching_both,
        rsi_now < 70,
        bearish_macd1_cross,
        bearish_macd5_cross,
        lower_high
    ]

    # ========================================================
    # BUY SIGNAL
    # ========================================================

    if all(buy_conditions):

        stop_loss = previous_swing_low

        return {
            "signal": "BUY",
            "price": price,
            "stop_loss": stop_loss,
            "rsi": rsi_now,
            "ema9": ema9_now,
            "ema26": ema26_now,
            "reason": "All BUY conditions confirmed"
        }

    # ========================================================
    # SELL SIGNAL
    # ========================================================

    if all(sell_conditions):

        stop_loss = previous_swing_high

        return {
            "signal": "SELL",
            "price": price,
            "stop_loss": stop_loss,
            "rsi": rsi_now,
            "ema9": ema9_now,
            "ema26": ema26_now,
            "reason": "All SELL conditions confirmed"
        }

    # ========================================================
    # WAIT
    # ========================================================

    return {
        "signal": "WAIT",
        "price": price,
        "rsi": rsi_now,
        "ema9": ema9_now,
        "ema26": ema26_now,
        "reason": "Conditions not fully confirmed"
    }


# ============================================================
# TELEGRAM MESSAGE
# ============================================================

def build_message(symbol, result):

    signal = result.get("signal")

    price = result.get("price")

    rsi = result.get("rsi")

    ema9_value = result.get("ema9")

    ema26_value = result.get("ema26")

    stop_loss = result.get("stop_loss")

    reason = result.get("reason")

    now = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    if signal == "BUY":

        return (
            "🟢 BUY SIGNAL\n\n"
            f"📊 {symbol}\n"
            "⏱ Timeframe: 1 MIN\n\n"
            f"💰 Price: {price:,.2f}\n"
            f"🛑 Stop Loss: {stop_loss:,.2f}\n\n"
            f"EMA 9: {ema9_value:,.2f}\n"
            f"EMA 26: {ema26_value:,.2f}\n"
            f"RSI: {rsi:.2f}\n\n"
            "MACD 1: ENTRY ALERT ✅\n"
            "MACD 5: EXECUTION CONFIRMATION ✅\n\n"
            f"📌 {reason}\n"
            f"🕐 {now}"
        )

    if signal == "SELL":

        return (
            "🔴 SELL SIGNAL\n\n"
            f"📊 {symbol}\n"
            "⏱ Timeframe: 1 MIN\n\n"
            f"💰 Price: {price:,.2f}\n"
            f"🛑 Stop Loss: {stop_loss:,.2f}\n\n"
            f"EMA 9: {ema9_value:,.2f}\n"
            f"EMA 26: {ema26_value:,.2f}\n"
            f"RSI: {rsi:.2f}\n\n"
            "MACD 1: ENTRY ALERT ✅\n"
            "MACD 5: EXECUTION CONFIRMATION ✅\n\n"
            f"📌 {reason}\n"
            f"🕐 {now}"
        )

    return None


# ============================================================
# BTC TRADING LOOP
# ============================================================

async def btc_loop():

    logger.info("BTC live strategy started.")

    await send_telegram(
        "✅ LIVE TRADING MATRIX ONLINE\n\n"
        "🪙 BTC/USDT\n"
        "⏱ 1-minute candles\n"
        "📡 Real market data\n"
        "🤖 Strategy engine active\n"
        "📲 Telegram alerts active\n\n"
        "No simulated prices are being used."
    )

    while True:

        try:

            df = await get_btc_candles()

            if df is None:
                await asyncio.sleep(10)
                continue

            result = analyze_market(df)

            signal = result.get("signal")

            # Only alert BUY/SELL.
            # WAIT is not spammed every minute.

            if signal in ["BUY", "SELL"]:

                candle_time = str(
                    df["open_time"].iloc[-1]
                )

                if last_alert["BTC"] != candle_time:

                    message = build_message(
                        "BTC/USDT",
                        result
                    )

                    if message:

                        await send_telegram(
                            message
                        )

                        last_alert["BTC"] = candle_time

                        logger.info(
                            f"BTC {signal} alert sent."
                        )

        except Exception as e:

            logger.error(
                f"Trading loop error: {e}"
            )

        # Check roughly every 15 seconds.
        # The strategy itself uses completed 1-minute candles.
        await asyncio.sleep(15)


# ============================================================
# GOLD LOOP
# ============================================================

async def gold_loop():

    logger.info("Gold monitoring started.")

    while True:

        try:

            gold_price = await get_gold_price()

            if gold_price is not None:

                logger.info(
                    f"Live XAU/USD: {gold_price:,.2f}"
                )

            else:

                logger.warning(
                    "Gold live feed is not configured."
                )

        except Exception as e:

            logger.error(
                f"Gold loop error: {e}"
            )

        await asyncio.sleep(60)


# ============================================================
# WEB SERVER
# ============================================================

@app.get("/")
async def home():

    return {
        "status": "online",
        "system": "live_1m_trading_matrix",
        "btc": "live",
        "gold": (
            "live"
            if GOLD_API_KEY
            else "not_configured"
        ),
        "timeframe": "1m"
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    asyncio.create_task(
        btc_loop()
    )

    asyncio.create_task(
        gold_loop()
    )

    logger.info(
        "Trading system started."
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
