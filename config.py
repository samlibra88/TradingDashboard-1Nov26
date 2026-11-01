# config.py - Zerodha KiteConnect Configuration
API_KEY = "fyuzsvjnqvnx2ble"
API_SECRET = "cs3l13awkilwzei6jgqmkq2yrz9gyup9"
ACCESS_TOKEN = "jyHYt4A5Maqvo4P246FwvCViMwdbHLRx"  # You will update this daily

# Trading Parameters
SYMBOL = "NIFTY"  # Base symbol
EXPIRY_DATE = "02JUN2026"  # Update to current expiry (e.g., "26JUN2025")
PCR_INTERVAL = 3  # Calculate PCR every 3 minutes
LOOKBACK_STRIKES = 6  # 6 higher PEs and 6 lower CEs

# OI Data - Strike prices to monitor
# These will be set dynamically based on current price
STRIKE_DIFFERENCE = 100  # Nifty strike difference

# Trading Logic - PCR Thresholds
PCR_BEARISH_THRESHOLD = 1.0  # PCR < 1.0 = Bearish (Buy PE)
PCR_BULLISH_THRESHOLD = 1.0  # PCR > 1.0 = Bullish (Buy CE)

# Order Parameters
ORDER_QUANTITY = 1  # Quantity per trade
ORDER_TYPE = "regular"  # "regular" or "amo"
PRODUCT_TYPE = "MIS"  # MIS for intraday

# Paper trading mode
PAPER_TRADING = True  # Run as paper trading system only
PAPER_TRADE_SL_POINTS = 20  # SL in points for paper trades
PAPER_TRADE_TARGET_POINTS = 40  # Target in points for paper trades

# Signal Candle Parameters (on 3-min chart)
SIGNAL_CANDLE_RSI_PERIOD = 10
SIGNAL_CANDLE_RSI_THRESHOLD = 30  # RSI < 30
SIGNAL_CANDLE_EMA_PERIOD = 5
SIGNAL_CANDLE_TIMEFRAME = "3minute"  # 3-minute chart

# ITM Requirements
MIN_ITM_POINTS = 100  # Minimum 100 points ITM from NIFTY strike price

# Logging
LOG_FILE = "trading_strategy.log"
DEBUG = True