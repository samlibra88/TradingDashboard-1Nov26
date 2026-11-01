# README.md - Signal Candle PCR Trading Strategy Bot

## Overview
This is an advanced automated trading bot that combines Put-Call Ratio (PCR) analysis with signal candle detection for precise entry points on NIFTY options.

### Strategy Logic

#### Step 1: PCR Calculation (Every 3 minutes)
- Fetches Open Interest (OI) data for 6 higher strike Put Options (PE) and 6 lower strike Call Options (CE)
- **PCR Formula**: PCR = Total PE OI / Total CE OI
- Determines market bias: Bullish (PCR > 1.0) or Bearish (PCR ≤ 1.0)

#### Step 2: Signal Candle Detection (on 3-minute chart)
A **signal candle** is formed when BOTH conditions are met:
1. **RSI(10) < 30** - Relative Strength Index below 30 indicates oversold/reversal potential
2. **Entire candle below 5EMA** - The highest point of the candle is below the 5-period EMA
   - EMA acts as resistance/support level

#### Step 3: Trade Execution
**If PCR < 1.0 (Bearish Signal):**
- Look for signal candle on **PE side**
- **Entry**: Buy above the HIGH of the signal candle
- Select a PE that is **minimum 100 points ITM** from NIFTY strike price

**If PCR > 1.0 (Bullish Signal):**
- Look for signal candle on **CE side**
- **Entry**: Buy above the HIGH of the signal candle
- Select a CE that is **minimum 100 points ITM** from NIFTY strike price

#### Step 4: Signal Candle Management
- **If high is not crossed**: Current signal candle remains valid for entry
- **If another signal candle forms** (before the previous one is touched): The new signal candle becomes the active entry level
- This prevents false breakouts and ensures optimal entries

## Requirements
- Python 3.7+
- Zerodha KiteConnect API access
- Active intraday trading account with Zerodha
- Internet connection for real-time data

## Installation

1. Navigate to the project directory:
```bash
cd "d:\TradingBot v1"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Update `config.py` with your credentials and parameters:

```python
# Broker Credentials
API_KEY = "YOUR_API_KEY"              # From Zerodha Developer Console
API_SECRET = "YOUR_API_SECRET"        # From Zerodha Developer Console
ACCESS_TOKEN = ""                      # Generated daily

# Trading Parameters
SYMBOL = "NIFTY"                       # Base trading symbol
EXPIRY_DATE = "26JUN2025"             # Current options expiry date
PCR_INTERVAL = 3                       # Calculate PCR every 3 minutes

# Signal Candle Parameters
SIGNAL_CANDLE_RSI_PERIOD = 10         # RSI period
SIGNAL_CANDLE_RSI_THRESHOLD = 30      # RSI threshold (< 30 = signal)
SIGNAL_CANDLE_EMA_PERIOD = 5          # 5-period EMA
SIGNAL_CANDLE_TIMEFRAME = "3minute"   # Use 3-minute charts

# Order Parameters
ORDER_QUANTITY = 1                     # Contracts per trade
PRODUCT_TYPE = "MIS"                   # MIS for intraday

# Entry Requirements
MIN_ITM_POINTS = 100                   # Minimum 100 points ITM from NIFTY price
STRIKE_DIFFERENCE = 100                # NIFTY strike difference
```

## Getting Access Token

To generate an access token:

1. Visit: https://kite.zerodha.com/
2. Login with your Zerodha credentials
3. Get request token from the browser console
4. Run the token generator:

```bash
python access_token_generator.py
```

Follow the prompts and it will generate your ACCESS_TOKEN. Copy it to `config.py`.

## Usage

### Run the Strategy

```bash
python main.py
```

The bot will:
1. Calculate PCR every 3 minutes
2. Monitor 3-minute candles of selected options
3. Identify signal candles (RSI < 30 + below 5EMA)
4. Wait for price to cross above signal candle high
5. Execute market order when conditions are met

### Logs
- Real-time console output with strategy actions
- Detailed file logging in `trading_strategy.log`

### Example Output
```
2025-06-26 09:30:15 - INFO - Current NIFTY price: 18500.45
2025-06-26 09:30:20 - INFO - PCR Calculation:
2025-06-26 09:30:20 - INFO -   Total PE OI: 1,250,500
2025-06-26 09:30:20 - INFO -   Total CE OI: 1,200,000
2025-06-26 09:30:20 - INFO -   PCR Value: 1.0420 (Bullish - Buy CE)

2025-06-26 09:30:21 - INFO - Selected CE strike: 18400 (ITM Distance: 100.45 points)
2025-06-26 09:30:22 - INFO - Signal Candle Detected: RSI=28.5 (< 30), High=380.25 < EMA=385.50
2025-06-26 09:30:23 - INFO - 📍 Entry Level (Signal Candle High): ₹380.25

2025-06-26 09:33:15 - INFO - ✓ SIGNAL TRIGGERED!
2025-06-26 09:33:15 - INFO - Price 381.50 > Entry 380.25
2025-06-26 09:33:16 - INFO - ✓ Order placed successfully: Order ID xxxxx
```

## Files

| File | Purpose |
|------|---------|
| `main.py` | Core strategy engine with PCR & signal candle logic |
| `config.py` | Configuration parameters & API credentials |
| `signal_candle.py` | Signal candle detection & technical analysis |
| `utilities.py` | Helper functions for calculations & logging |
| `access_token_generator.py` | Token generation utility |
| `requirements.txt` | Python dependencies |

## Key Features

✅ **PCR Analysis** - Identifies market bias every 3 minutes  
✅ **Signal Candle Detection** - RSI(10) < 30 + Below 5EMA  
✅ **Smart Entry Points** - Buys above signal candle high for better risk/reward  
✅ **ITM Selection** - Automatically selects options 100+ points ITM  
✅ **Dynamic Signal Updates** - Replaces signal if not touched  
✅ **Real-time Monitoring** - Continuous price monitoring every 10 seconds  
✅ **Comprehensive Logging** - Detailed console + file logs  
✅ **Error Handling** - Robust error recovery  

## Risk Management

**Important Considerations:**
- This bot is for **experienced traders** with proper risk management
- Always test on **paper trading** first
- Monitor market conditions and volatility
- Set stop-losses manually based on your risk tolerance
- Validate all configuration parameters before live trading
- Start with minimum quantity (ORDER_QUANTITY = 1)
- Monitor logs for any anomalies

### Recommended Risk Management:
- Risk only 1-2% of capital per trade
- Use 2x ATR (Average True Range) as stop loss
- Scale out of profitable trades
- Avoid trading during low liquidity hours (last 15 mins)

## Troubleshooting

### "Symbol not found" errors
- Verify expiry date is correct (e.g., "26JUN2025")
- Ensure it's within trading hours (9:15 AM - 3:30 PM IST)
- Check if options are active for the selected symbol

### "No candle data" errors
- Ensure market is open
- Check internet connection
- Verify symbol exists in NSE:NFO
- Increase historical lookback period

### "Access token expired"
- Generate a new token daily
- Update `config.py` with new ACCESS_TOKEN

### No signal candles detected
- Verify RSI and EMA calculations
- Check if current market is in consolidation (few reversals)
- Adjust RSI_THRESHOLD if market is consistently overbought/oversold

## Performance Optimization

- Adjust PCR_INTERVAL based on your trading style (shorter = more trades)
- Modify SIGNAL_CANDLE_RSI_THRESHOLD for different market conditions
  - More aggressive: threshold = 35-40
  - More conservative: threshold = 20-25
- Adjust MIN_ITM_POINTS based on premium and volatility

## Disclaimer

This bot is provided **as-is** for educational purposes. 

**IMPORTANT:**
- Past performance does not guarantee future results
- Use at your own risk with proper risk management
- Validate all trades manually before going live
- Monitor the bot during trading hours
- Be prepared to stop the bot immediately if market conditions change drastically
- This strategy may incur losses

---

**For Support:**
- KiteConnect Docs: https://kite.trade/docs/
- Zerodha Support: support@zerodha.com
- Trading Concepts: Consult a financial advisor

