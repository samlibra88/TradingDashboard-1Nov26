# signal_candle.py - Signal candle detection and technical analysis

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import ta
import config

logger = logging.getLogger(__name__)


class SignalCandle:
    """Represents a signal candle with its high, low, and timestamp"""
    def __init__(self, timestamp, open_price, high, low, close, rsi, ema):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.rsi = rsi
        self.ema = ema
        self.touched = False  # Track if price crossed above high

    def __repr__(self):
        return f"SignalCandle(time={self.timestamp}, high={self.high}, RSI={self.rsi:.2f}, EMA={self.ema:.2f})"


class TechnicalAnalyzer:
    """Calculate technical indicators on candle data"""
    
    @staticmethod
    def calculate_rsi(data, period=config.SIGNAL_CANDLE_RSI_PERIOD):
        """Calculate RSI (Relative Strength Index)"""
        try:
            series = pd.Series(data)
            indicator = ta.momentum.RSIIndicator(close=series, window=period)
            rsi = indicator.rsi()
            return rsi.iloc[-1] if len(rsi) > 0 else None
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            return None

    @staticmethod
    def calculate_ema(data, period=config.SIGNAL_CANDLE_EMA_PERIOD):
        """Calculate EMA (Exponential Moving Average)"""
        try:
            series = pd.Series(data)
            indicator = ta.trend.EMAIndicator(close=series, window=period)
            ema = indicator.ema_indicator()
            return ema.iloc[-1] if len(ema) > 0 else None
        except Exception as e:
            logger.warning(f"Error calculating EMA: {e}")
            return None

    @staticmethod
    def is_candle_below_ema(candle_high, candle_low, ema_value):
        """Check if entire candle is below 5EMA"""
        if ema_value is None:
            return False
        # Entire candle below EMA means the highest point of candle < EMA
        return candle_high < ema_value

    @staticmethod
    def is_signal_candle(rsi, candle_high, candle_low, ema_value):
        """
        Determine if a candle is a signal candle
        Conditions:
        - RSI(10) < 30
        - Entire candle below 5EMA
        """
        if rsi is None or ema_value is None:
            return False
        
        rsi_condition = rsi < config.SIGNAL_CANDLE_RSI_THRESHOLD
        ema_condition = TechnicalAnalyzer.is_candle_below_ema(candle_high, candle_low, ema_value)
        
        is_signal = rsi_condition and ema_condition
        
        if is_signal:
            logger.info(f"Signal Candle Detected: RSI={rsi:.2f} (< {config.SIGNAL_CANDLE_RSI_THRESHOLD}), "
                       f"High={candle_high} < EMA={ema_value:.2f}")
        
        return is_signal


class CandleDataManager:
    """Manage candle data and signal candle tracking"""
    
    def __init__(self):
        self.candle_history = {}  # symbol -> list of candles
        self.signal_candle = {}  # symbol -> current SignalCandle object
        self.last_signal_candle_touched = {}  # Track if last signal candle was touched
        
    def add_candles(self, symbol, candles_data):
        """
        Add historical candle data
        candles_data: list of dicts with keys: timestamp, open, high, low, close
        """
        try:
            if symbol not in self.candle_history:
                self.candle_history[symbol] = []
            
            closes = []
            for candle in candles_data:
                closes.append(candle.get('close', 0))
            
            # Calculate indicators on historical data
            closes_series = pd.Series(closes)
            rsi_values = ta.momentum.RSIIndicator(close=closes_series, window=config.SIGNAL_CANDLE_RSI_PERIOD).rsi()
            ema_values = ta.trend.EMAIndicator(close=closes_series, window=config.SIGNAL_CANDLE_EMA_PERIOD).ema_indicator()
            
            # Store candles with calculated indicators
            self.candle_history[symbol] = []
            for idx, candle in enumerate(candles_data):
                signal_obj = SignalCandle(
                    timestamp=candle.get('timestamp'),
                    open_price=candle.get('open', 0),
                    high=candle.get('high', 0),
                    low=candle.get('low', 0),
                    close=candle.get('close', 0),
                    rsi=rsi_values.iloc[idx] if idx < len(rsi_values) else None,
                    ema=ema_values.iloc[idx] if idx < len(ema_values) else None
                )
                self.candle_history[symbol].append(signal_obj)
                
                # Check if this is a signal candle
                if TechnicalAnalyzer.is_signal_candle(signal_obj.rsi, signal_obj.high, signal_obj.low, signal_obj.ema):
                    self.signal_candle[symbol] = signal_obj
                    self.last_signal_candle_touched[symbol] = False
                    
        except Exception as e:
            logger.error(f"Error adding candles for {symbol}: {e}")

    def check_signal_candle_touched(self, symbol, current_price):
        """Check if current price crossed above signal candle high"""
        if symbol not in self.signal_candle:
            return False
        
        signal = self.signal_candle[symbol]
        if current_price > signal.high and not signal.touched:
            signal.touched = True
            logger.info(f"Signal Candle HIGH TOUCHED! Price {current_price} > Signal High {signal.high}")
            return True
        
        return False

    def update_with_new_candle(self, symbol, candle_data):
        """Update candle data with a new 3-minute candle"""
        try:
            if symbol not in self.candle_history:
                self.candle_history[symbol] = []
            
            # Get last 10 closes for RSI calculation (need at least 10)
            recent_closes = []
            for candle in self.candle_history[symbol][-9:]:  # Last 9 + new one = 10
                recent_closes.append(candle.close)
            recent_closes.append(candle_data.get('close', 0))
            
            # Calculate indicators
            closes_series = pd.Series(recent_closes)
            rsi_values = ta.momentum.RSIIndicator(close=closes_series, window=config.SIGNAL_CANDLE_RSI_PERIOD).rsi()
            ema_values = ta.trend.EMAIndicator(close=closes_series, window=config.SIGNAL_CANDLE_EMA_PERIOD).ema_indicator()
            
            rsi = rsi_values.iloc[-1] if len(rsi_values) > 0 else None
            ema = ema_values.iloc[-1] if len(ema_values) > 0 else None
            
            # Create signal candle object
            signal_obj = SignalCandle(
                timestamp=candle_data.get('timestamp'),
                open_price=candle_data.get('open', 0),
                high=candle_data.get('high', 0),
                low=candle_data.get('low', 0),
                close=candle_data.get('close', 0),
                rsi=rsi,
                ema=ema
            )
            
            self.candle_history[symbol].append(signal_obj)
            
            # Keep only last 100 candles in history
            if len(self.candle_history[symbol]) > 100:
                self.candle_history[symbol] = self.candle_history[symbol][-100:]
            
            # Check if new signal candle formed
            if TechnicalAnalyzer.is_signal_candle(signal_obj.rsi, signal_obj.high, signal_obj.low, signal_obj.ema):
                # If previous signal candle wasn't touched, replace it with new one
                if symbol in self.signal_candle and not self.signal_candle[symbol].touched:
                    logger.info(f"Previous signal candle not touched. New signal candle formed: {signal_obj}")
                
                self.signal_candle[symbol] = signal_obj
                self.last_signal_candle_touched[symbol] = False
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating candle for {symbol}: {e}")
            return False

    def get_current_signal_candle(self, symbol):
        """Get current signal candle high for a symbol"""
        return self.signal_candle.get(symbol, None)

    def get_entry_price(self, symbol):
        """Get entry price (high of signal candle) for a symbol"""
        signal = self.get_current_signal_candle(symbol)
        if signal:
            return signal.high
        return None

    def get_candle_summary(self, symbol):
        """Get formatted summary of current candle analysis"""
        if symbol not in self.candle_history:
            return "No data available"
        
        latest = self.candle_history[symbol][-1]
        signal = self.signal_candle.get(symbol)
        
        summary = f"""
        ╔═══════════════════════════════════╗
        ║  3-MIN CANDLE ANALYSIS: {symbol:15}║
        ╠═══════════════════════════════════╣
        ║ Latest Candle:                    ║
        ║   High: ₹{latest.high:25.2f}║
        ║   Low: ₹{latest.low:26.2f}║
        ║   Close: ₹{latest.close:24.2f}║
        ║   RSI(10): {latest.rsi:27.2f}║
        ║   5EMA: ₹{latest.ema:27.2f}║
        ║                                   ║
        """
        
        if signal:
            summary += f"""║ Signal Candle (Entry Level):       ║
        ║   High: ₹{signal.high:25.2f}║
        ║   RSI: {signal.rsi:31.2f}║
        ║   5EMA: ₹{signal.ema:27.2f}║
        ║   Status: {'TOUCHED' if signal.touched else 'PENDING':26}║"""
        else:
            summary += f"║ No Signal Candle Yet              ║"
        
        summary += f"""
        ╚═══════════════════════════════════╝
        """
        return summary
