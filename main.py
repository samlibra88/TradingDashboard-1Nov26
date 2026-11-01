from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import pandas as pd
import time
import logging
import config
from signal_candle import CandleDataManager, TechnicalAnalyzer, SignalCandle

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SignalCandleTradingStrategy:
    def __init__(self, api_key, api_secret, access_token):
        """Initialize the trading strategy with signal candle detection"""
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
        self.current_price = None
        self.available_strikes = []
        self.available_instruments = []
        self.last_pcr_time = None
        self.candle_manager = CandleDataManager()
        self.pending_trade = None
        self.trade_history = []
        logger.info("Signal Candle Trading Strategy initialized")

    def get_current_nifty_price(self):
        """Fetch current NIFTY price"""
        try:
            quote = self.kite.quote("NSE:NIFTY 50")["NSE:NIFTY 50"]
            self.current_price = quote["last_price"]
            logger.info(f"Current NIFTY price: {self.current_price}")
            return self.current_price
        except Exception as e:
            logger.error(f"Error fetching NIFTY price: {e}")
            return None

    def get_available_strikes(self):
        """Get all available strikes for current expiry"""
        try:
            instruments = self.kite.instruments("NFO")
            search_keys = [config.SYMBOL, config.SYMBOL.replace(" ", "")]
            expiry_code = self._normalized_expiry_code()
            nifty_options = []
            for instr in instruments:
                tradingsymbol = instr.get("tradingsymbol", "")
                normalized_name = tradingsymbol.replace(" ", "").upper()

                if any(key.replace(" ", "").upper() in normalized_name for key in search_keys) and expiry_code in normalized_name:
                    nifty_options.append(instr)

            strikes = sorted(list(set([instr.get("strike", 0) for instr in nifty_options if instr.get("strike", 0) != 0])))
            self.available_strikes = strikes
            self.available_instruments = nifty_options
            logger.info(f"Available strikes: {len(strikes)} strikes found")
            if nifty_options:
                logger.debug("Sample matching NIFTY instruments:")
                for instr in nifty_options[:10]:
                    expiry_value = instr.get("expiry") or instr.get("expiry_date") or ""
                    logger.debug(
                        f"  {instr.get('tradingsymbol')} | {instr.get('name')} | expiry={expiry_value} | strike={instr.get('strike')}"
                    )
            if len(strikes) == 0:
                logger.warning("No NIFTY option strikes found for the configured symbol/expiry. Check config.SYMBOL and config.EXPIRY_DATE.")
            return strikes
        except Exception as e:
            logger.error(f"Error fetching available strikes: {e}")
            return []

    def _normalized_expiry_code(self):
        raw = config.EXPIRY_DATE.strip()
        for fmt in ("%d%b%Y", "%d%b%y", "%y%m%d", "%Y%m%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%y%m%d")
            except Exception:
                continue
        return raw.replace(" ", "").upper()

    def build_option_symbol(self, option_type, strike):
        """Build the exact option symbol using available instrument metadata."""
        option_letter = "C" if option_type == "CE" else "P"
        expiry_code = self._normalized_expiry_code()
        expected = f"{config.SYMBOL.replace(' ', '')}{expiry_code}{option_letter}{strike}"

        for instr in self.available_instruments:
            tradingsymbol = instr.get("tradingsymbol", "")
            if tradingsymbol.replace(" ", "") == expected:
                symbol = f"NSE:{tradingsymbol}"
                logger.debug(f"build_option_symbol matched instrument: {symbol}")
                return symbol

        fallback_symbol = f"NSE:{expected}"
        logger.debug(f"build_option_symbol fallback symbol: {fallback_symbol}")
        return fallback_symbol

    def get_strikes_for_pcr_calculation(self):
        """Get 6 PE strikes above ATM and 6 CE strikes below ATM for PCR"""
        if not self.current_price or not self.available_strikes:
            logger.warning("Current price or strikes not available")
            return None, None

        strikes = sorted(self.available_strikes)
        if not strikes:
            logger.warning("No available strikes for PCR calculation")
            return None, None

        # Find the strike closest to current NIFTY price
        current_strike_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - self.current_price))

        # CE strikes are the strikes at or below current price
        ce_start = max(0, current_strike_idx - config.LOOKBACK_STRIKES)
        ce_strikes = strikes[ce_start:current_strike_idx + 1]

        # PE strikes are the strikes above current price
        pe_end = min(len(strikes), current_strike_idx + 1 + config.LOOKBACK_STRIKES)
        pe_strikes = strikes[current_strike_idx + 1:pe_end]

        logger.info(f"PCR CE strikes (at/below ATM): {ce_strikes}")
        logger.info(f"PCR PE strikes (above ATM): {pe_strikes}")
        return pe_strikes, ce_strikes

    def select_itm_option(self, option_type, is_bullish):
        """Select an ITM PE or CE option contract for trading."""
        try:
            strikes = sorted(self.available_strikes)
            if not strikes:
                logger.warning("No available strikes for ITM option selection")
                return None, None

            if option_type == "CE":
                # ITM CE means a call strike below current NIFTY price
                candidates = [s for s in strikes if s <= self.current_price - config.MIN_ITM_POINTS]
                if not candidates:
                    candidates = [s for s in strikes if s < self.current_price]
                selected_strike = max(candidates) if candidates else strikes[0]
            else:
                # ITM PE means a put strike above current NIFTY price
                candidates = [s for s in strikes if s >= self.current_price + config.MIN_ITM_POINTS]
                if not candidates:
                    candidates = [s for s in strikes if s > self.current_price]
                selected_strike = min(candidates) if candidates else strikes[-1]

            symbol = self.build_option_symbol(option_type, selected_strike)
            itm_distance = abs(self.current_price - selected_strike)
            logger.info(
                f"Selected ITM {option_type} strike {selected_strike} "
                f"(distance {itm_distance:.2f} from NIFTY {self.current_price})"
            )
            logger.info(f"Generated option symbol: {symbol}")
            return symbol, selected_strike
        except Exception as e:
            logger.error(f"Error selecting ITM option: {e}")
            return None, None

    def fetch_oi_data(self, strike_list, option_type):
        """Fetch Open Interest data for given strikes and option type"""
        try:
            oi_data = {}
            for strike in strike_list:
                symbol = self.build_option_symbol(option_type, strike)
                if symbol is None:
                    logger.warning(f"Unable to build symbol for {option_type} {strike}")
                    oi_data[strike] = 0
                    continue
                try:
                    quote = self.kite.quote(symbol)
                    if symbol in quote:
                        oi_data[strike] = quote[symbol].get("oi", 0)
                    else:
                        logger.warning(f"Symbol {symbol} not found in quote")
                        oi_data[strike] = 0
                except Exception as e:
                    logger.warning(f"Error fetching OI for {symbol}: {e}")
                    oi_data[strike] = 0
            
            return oi_data
        except Exception as e:
            logger.error(f"Error in fetch_oi_data: {e}")
            return {}

    def calculate_pcr(self, pe_oi_data, ce_oi_data):
        """Calculate Put-Call Ratio (PCR) = Total PE OI / Total CE OI"""
        try:
            total_pe_oi = sum(pe_oi_data.values())
            total_ce_oi = sum(ce_oi_data.values())
            
            if total_ce_oi == 0:
                logger.warning("Total CE OI is 0, cannot calculate PCR")
                return None
            
            pcr = total_pe_oi / total_ce_oi
            
            logger.info(f"PCR Calculation:")
            logger.info(f"  Total PE OI: {total_pe_oi}")
            logger.info(f"  Total CE OI: {total_ce_oi}")
            logger.info(f"  PCR Value: {pcr:.4f}")
            
            return pcr
        except Exception as e:
            logger.error(f"Error calculating PCR: {e}")
            return None

    def fetch_candle_data(self, symbol, from_date=None, to_date=None):
        """Fetch 3-minute candle data for a symbol"""
        try:
            if from_date is None:
                from_date = datetime.now() - timedelta(hours=2)  # Last 2 hours
            if to_date is None:
                to_date = datetime.now()
            
            logger.debug(f"Fetching candles for {symbol} from {from_date} to {to_date}")
            
            candles = self.kite.historical_data(
                instrument_token=self.get_instrument_token(symbol),
                from_date=from_date,
                to_date=to_date,
                interval=config.SIGNAL_CANDLE_TIMEFRAME
            )
            
            if not candles:
                logger.warning(f"No candle data received for {symbol}")
                return []
            
            logger.info(f"Fetched {len(candles)} candles for {symbol}")
            return candles
        except Exception as e:
            logger.error(f"Error fetching candle data for {symbol}: {e}")
            return []

    def get_instrument_token(self, symbol):
        """Get instrument token for a symbol from instruments data"""
        try:
            instruments = self.kite.instruments("NFO")
            for instr in instruments:
                if instr["tradingsymbol"] == symbol.replace("NFO:", ""):
                    return instr["instrument_token"]
            logger.warning(f"Instrument token not found for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None

    def get_option_quote(self, symbol):
        """Fetch quote data for a given option symbol"""
        try:
            quote = self.kite.quote(symbol)
            if symbol in quote:
                return quote[symbol]
            logger.warning(f"Quote not returned for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_current_option_price(self, symbol):
        """Get current LTP for an option symbol"""
        option_quote = self.get_option_quote(symbol)
        if option_quote is None:
            return None
        return option_quote.get("last_price") or option_quote.get("last_traded_price")

    def calculate_paper_trade_levels(self, entry_price):
        """Calculate target and stop loss for paper trade"""
        sl = max(entry_price - config.PAPER_TRADE_SL_POINTS, 0)
        target = entry_price + config.PAPER_TRADE_TARGET_POINTS
        return sl, target

    def log_paper_trade_signal(self, pending_trade):
        """Log the paper trade signal details neatly"""
        logger.info("\n" + "=" * 70)
        logger.info("PAPER TRADE SIGNAL")
        logger.info(f"Signal Candle Time : {pending_trade['signal_time']}")
        logger.info(f"PCR Value          : {pending_trade['pcr']:.4f}")
        logger.info(f"Signal RSI(10)     : {pending_trade['signal_rsi']:.2f}")
        logger.info(f"Supposed Buy       : {pending_trade['symbol']} at ₹{pending_trade['entry_price']:.2f}")
        logger.info(f"Suggested SL       : ₹{pending_trade['sl_price']:.2f}")
        logger.info(f"Suggested Target   : ₹{pending_trade['target_price']:.2f}")
        logger.info(f"Trade Type         : {pending_trade['direction']}")
        logger.info("=" * 70)

    def log_paper_trade_execution(self, trade, executed_price):
        """Log when a paper trade is executed"""
        logger.info("\n" + "=" * 70)
        logger.info(f"Bought {trade['symbol']} at ₹{executed_price:.2f} with ₹{trade['sl_price']:.2f} as SL and ₹{trade['target_price']:.2f} as target")
        logger.info("=" * 70)

    def set_pending_trade(self, symbol, strike, option_type, entry_price, pcr_value, signal_time, signal_rsi, direction):
        sl, target = self.calculate_paper_trade_levels(entry_price)
        signal_time_str = signal_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(signal_time, "strftime") else str(signal_time)
        self.pending_trade = {
            "symbol": symbol,
            "strike": strike,
            "option_type": option_type,
            "entry_price": entry_price,
            "pcr": pcr_value,
            "signal_time": signal_time_str,
            "signal_rsi": signal_rsi,
            "direction": direction,
            "sl_price": sl,
            "target_price": target,
            "status": "PENDING"
        }
        self.trade_history.append(self.pending_trade)
        self.log_paper_trade_signal(self.pending_trade)

    def place_order(self, symbol, transaction_type, quantity=config.ORDER_QUANTITY, price=None):
        """Place a trading order or simulate it in paper trading mode"""
        if config.PAPER_TRADING:
            logger.info(f"PAPER TRADE | {transaction_type} {symbol} quantity {quantity} at simulated market price")
            return {
                "symbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "status": "SIMULATED"
            }

        try:
            order = self.kite.place_order(
                tradingsymbol=symbol.replace("NFO:", ""),
                exchange="NFO",
                transaction_type=transaction_type,
                quantity=quantity,
                order_type="MARKET",
                product=config.PRODUCT_TYPE
            )
            logger.info(f"✓ Order placed successfully: Order ID {order}")
            return order
        except Exception as e:
            logger.error(f"✗ Error placing order: {e}")
            return None

    def monitor_signal_candles(self, pcr_value):
        """Monitor signal candles and execute trades when conditions are met"""
        try:
            if self.pending_trade is not None:
                logger.info("A paper trade is already pending; skipping new trade setup until execution completes")
                return

            logger.info(f"\n{'='*60}")
            logger.info(f"Signal Candle Monitoring - PCR Value: {pcr_value:.4f}")
            logger.info(f"{'='*60}")

            if pcr_value == config.PCR_BULLISH_THRESHOLD:
                logger.info("PCR is neutral; no directional trade signal at this time")
                return

            is_bullish = pcr_value > config.PCR_BULLISH_THRESHOLD
            option_type = "CE" if is_bullish else "PE"
            direction = "BUY CE" if is_bullish else "BUY PE"

            logger.info(f"PCR Analysis: {'Bullish' if is_bullish else 'Bearish'} market bias, selecting {option_type} ITM option")

            symbol, strike = self.select_itm_option(option_type, is_bullish)
            if not symbol:
                logger.warning("Failed to select ITM option")
                return

            # Fetch historical candles for the selected ITM option
            candles = self.fetch_candle_data(symbol)
            if not candles:
                logger.warning(f"No candle data available for {symbol}")
                return

            self.candle_manager.add_candles(symbol, candles)
            logger.info(self.candle_manager.get_candle_summary(symbol))

            entry_price = self.candle_manager.get_entry_price(symbol)
            signal_candle = self.candle_manager.get_current_signal_candle(symbol)
            if entry_price and signal_candle:
                logger.info(f"📍 Signal candle found on {symbol}. Entry Level (High): ₹{entry_price:.2f}")
                self.set_pending_trade(
                    symbol=symbol,
                    strike=strike,
                    option_type=option_type,
                    entry_price=entry_price,
                    pcr_value=pcr_value,
                    signal_time=signal_candle.timestamp,
                    signal_rsi=signal_candle.rsi,
                    direction=direction
                )
                logger.info(f"Waiting for {symbol} LTP to cross above ₹{entry_price:.2f} to execute trade")
            else:
                logger.warning(f"No signal candle detected yet for selected ITM option {symbol}. Waiting for a valid signal...")

        except Exception as e:
            logger.error(f"Error in monitor_signal_candles: {e}")

    def check_and_execute_trades(self):
        """Check if signal candle highs have been crossed and execute trades"""
        try:
            self.get_current_nifty_price()
            if self.pending_trade is None:
                return

            symbol = self.pending_trade["symbol"]
            entry_price = self.pending_trade["entry_price"]
            option_price = self.get_current_option_price(symbol)
            if option_price is None:
                return

            logger.debug(f"Current LTP for {symbol}: ₹{option_price:.2f}")
            if option_price >= entry_price:
                logger.info(f"\n{'='*60}")
                logger.info(f"✓ PAPER TRADE EXECUTION TRIGGERED")
                logger.info(f"Option {symbol} LTP ₹{option_price:.2f} >= entry ₹{entry_price:.2f}")
                logger.info(f"{'='*60}")
                self.place_order(symbol, "BUY")
                self.log_paper_trade_execution(self.pending_trade, option_price)
                self.pending_trade["status"] = "EXECUTED"
                self.pending_trade = None

        except Exception as e:
            logger.error(f"Error checking signals: {e}")

    def get_pcr_interval_boundary(self, dt):
        """Return the most recent PCR time boundary for the configured interval."""
        interval = config.PCR_INTERVAL
        boundary_minute = (dt.minute // interval) * interval
        return dt.replace(minute=boundary_minute, second=0, microsecond=0)

    def run(self):
        """Main strategy loop"""
        logger.info("Starting Signal Candle Trading Strategy")
        
        # Initial setup
        self.get_current_nifty_price()
        self.get_available_strikes()
        
        try:
            while True:
                now = datetime.now()
                current_boundary = self.get_pcr_interval_boundary(now)

                if self.last_pcr_time is None:
                    self.last_pcr_time = current_boundary - timedelta(minutes=config.PCR_INTERVAL)

                if current_boundary > self.last_pcr_time:
                    logger.info(f"\n{'='*70}")
                    logger.info(f"PCR CALCULATION CYCLE - aligned to {current_boundary}")
                    logger.info(f"{'='*70}")
                    
                    # Fetch current data
                    self.get_current_nifty_price()
                    pe_strikes, ce_strikes = self.get_strikes_for_pcr_calculation()
                    
                    if pe_strikes is not None and ce_strikes is not None:
                        # Fetch OI data
                        pe_oi = self.fetch_oi_data(pe_strikes, "PE")
                        ce_oi = self.fetch_oi_data(ce_strikes, "CE")
                        
                        # Calculate PCR
                        pcr_value = self.calculate_pcr(pe_oi, ce_oi)
                        
                        # Log aligned PCR with ITM option prices
                        if pcr_value is not None:
                            ce_symbol, _ = self.select_itm_option("CE", True)
                            pe_symbol, _ = self.select_itm_option("PE", False)
                            ce_price = self.get_current_option_price(ce_symbol) if ce_symbol else None
                            pe_price = self.get_current_option_price(pe_symbol) if pe_symbol else None
                            ce_price_str = f"₹{ce_price:.2f}" if ce_price is not None else "N/A"
                            pe_price_str = f"₹{pe_price:.2f}" if pe_price is not None else "N/A"
                            logger.info(f"Aligned PCR {current_boundary}: PCR={pcr_value:.4f}, ITM CE={ce_symbol} {ce_price_str}, ITM PE={pe_symbol} {pe_price_str}")
                            self.monitor_signal_candles(pcr_value)
                    
                    self.last_pcr_time = current_boundary
                
                # Check for signal candle touches every 10 seconds
                self.check_and_execute_trades()
                
                # Sleep before next check
                time.sleep(10)
        
        except KeyboardInterrupt:
            logger.info("Strategy stopped by user")
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}")


def main():
    """Main function to start the trading bot"""
    logger.info("Initializing Trading Bot")
    
    try:
        # Initialize strategy
        strategy = SignalCandleTradingStrategy(
            api_key=config.API_KEY,
            api_secret=config.API_SECRET,
            access_token=config.ACCESS_TOKEN
        )
        
        # Run the strategy
        strategy.run()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()