from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import config
from signal_candle import CandleDataManager


def get_nifty_token(kite):
    instruments = kite.instruments('NSE')
    for instr in instruments:
        tradingsymbol = instr.get('tradingsymbol', '')
        name = instr.get('name', '')
        if 'NIFTY' in tradingsymbol and '50' in tradingsymbol:
            return instr.get('instrument_token'), tradingsymbol
        if 'NIFTY' in name and '50' in name:
            return instr.get('instrument_token'), tradingsymbol
    raise ValueError('NIFTY 50 instrument token not found in NSE instruments')


def normalize_expiry_code(raw_expiry):
    raw = str(raw_expiry).strip()
    for fmt in ("%d%b%Y", "%d%b%y", "%y%m%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%y%m%d")
        except Exception:
            continue
    return raw.replace(" ", "").upper()


def get_nifty_option_instruments(kite):
    instruments = kite.instruments('NFO')
    matching = []
    expiry_code = normalize_expiry_code(config.EXPIRY_DATE)
    for instr in instruments:
        tradingsymbol = instr.get('tradingsymbol', '')
        normalized_name = tradingsymbol.replace(' ', '').upper()
        if config.SYMBOL.replace(' ', '').upper() in normalized_name and expiry_code in normalized_name:
            matching.append(instr)
    return matching


def get_available_strikes(option_instruments):
    strikes = sorted({instr.get('strike', 0) for instr in option_instruments if instr.get('strike', 0)})
    return strikes


def build_option_symbol(option_instruments, option_type, strike):
    option_letter = 'C' if option_type == 'CE' else 'P'
    expiry_code = normalize_expiry_code(config.EXPIRY_DATE)
    expected = f"{config.SYMBOL.replace(' ', '')}{expiry_code}{option_letter}{strike}"
    for instr in option_instruments:
        tradingsymbol = instr.get('tradingsymbol', '')
        if tradingsymbol.replace(' ', '') == expected:
            symbol = f"NFO:{tradingsymbol}"
            print(f"Built option symbol from instrument list: {symbol}")
            return symbol
    fallback = f"NFO:{expected}"
    print(f"Built fallback option symbol: {fallback}")
    return fallback


def get_instrument_token(symbol, option_instruments):
    normalized = symbol.replace('NFO:', '').replace('NSE:', '')
    for instr in option_instruments:
        if instr.get('tradingsymbol') == normalized:
            return instr.get('instrument_token')
    return None


def fetch_candles(kite, token, from_date, to_date):
    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_date,
        to_date=to_date,
        interval=config.SIGNAL_CANDLE_TIMEFRAME
    )
    return candles or []


def get_strikes_for_pcr_calculation(current_price, strikes):
    if not strikes:
        return None, None

    atm_index = min(range(len(strikes)), key=lambda i: abs(strikes[i] - current_price))
    ce_strikes = strikes[max(0, atm_index - config.LOOKBACK_STRIKES):atm_index + 1]
    pe_strikes = strikes[atm_index + 1: min(len(strikes), atm_index + 1 + config.LOOKBACK_STRIKES)]
    return pe_strikes, ce_strikes


def fetch_oi_data(kite, option_instruments, strikes, option_type):
    oi_data = {}
    for strike in strikes:
        symbol = build_option_symbol(option_instruments, option_type, strike)
        try:
            quote = kite.quote(symbol)
            oi_data[strike] = quote.get(symbol, {}).get('oi', 0)
        except Exception:
            oi_data[strike] = 0
    return oi_data


def calculate_pcr(pe_oi_data, ce_oi_data):
    total_pe = sum(pe_oi_data.values())
    total_ce = sum(ce_oi_data.values())
    if total_ce == 0:
        return None
    return total_pe / total_ce


def select_itm_option(current_price, strikes, option_type):
    if not strikes:
        return None, None

    if option_type == 'CE':
        candidates = [s for s in strikes if s <= current_price - config.MIN_ITM_POINTS]
        if not candidates:
            candidates = [s for s in strikes if s < current_price]
        selected = max(candidates) if candidates else strikes[0]
    else:
        candidates = [s for s in strikes if s >= current_price + config.MIN_ITM_POINTS]
        if not candidates:
            candidates = [s for s in strikes if s > current_price]
        selected = min(candidates) if candidates else strikes[-1]

    return selected


def get_option_symbol(option_instruments, strike, option_type):
    return build_option_symbol(option_instruments, option_type, strike)


def get_last_option_candle(option_candles):
    return option_candles[-1] if option_candles else None


def replay_today(date=None):
    if date is None:
        date = datetime.now()
    trading_start = datetime(date.year, date.month, date.day, 9, 15)
    trading_end = datetime(date.year, date.month, date.day, 15, 30)
    if datetime.now() < trading_end:
        trading_end = datetime.now()

    kite = KiteConnect(api_key=config.API_KEY)
    kite.set_access_token(config.ACCESS_TOKEN)

    print(f'Replaying NIFTY 3-minute candles from {trading_start} to {trading_end}')
    nifty_token, nifty_symbol = get_nifty_token(kite)
    print(f'NIFTY symbol: {nifty_symbol}')
    nifty_candles = fetch_candles(kite, nifty_token, trading_start, trading_end)

    if not nifty_candles:
        print('No candle data fetched. Check your access token, API credentials, or market timing.')
        return

    option_instruments = get_nifty_option_instruments(kite)
    print(f'Found {len(option_instruments)} matching NIFTY option instruments')
    for instr in option_instruments:
        print(f"  {instr.get('tradingsymbol', '')} | strike={instr.get('strike')} | expiry={instr.get('expiry') or instr.get('expiry_date')}")

    strikes = get_available_strikes(option_instruments)
    if not strikes:
        print('No NIFTY option strikes found. Check SYMBOL and EXPIRY_DATE in config.')
        return

    nifty_manager = CandleDataManager()
    active_trade = None
    trades = []
    trade_number = 0
    last_pcr_boundary = None

    for candle in nifty_candles:
        candle_time = candle.get('date') or candle.get('timestamp')
        candle_data = {
            'timestamp': candle_time,
            'open': candle.get('open'),
            'high': candle.get('high'),
            'low': candle.get('low'),
            'close': candle.get('close')
        }

        nifty_manager.update_with_new_candle('NIFTY', candle_data)
        current_price = candle_data['close']
        current_boundary = candle_time.replace(minute=(candle_time.minute // config.PCR_INTERVAL) * config.PCR_INTERVAL, second=0, microsecond=0)

        if last_pcr_boundary is None or current_boundary > last_pcr_boundary:
            last_pcr_boundary = current_boundary
            pe_strikes, ce_strikes = get_strikes_for_pcr_calculation(current_price, strikes)
            if pe_strikes is None or ce_strikes is None:
                continue

            pe_oi = fetch_oi_data(kite, option_instruments, pe_strikes, 'PE')
            ce_oi = fetch_oi_data(kite, option_instruments, ce_strikes, 'CE')
            pcr_value = calculate_pcr(pe_oi, ce_oi)

            print(f"\nPCR boundary {current_boundary} - PE strikes {pe_strikes}, CE strikes {ce_strikes}")
            print(f"  PCR value: {pcr_value if pcr_value is not None else 'N/A'}")

            if pcr_value is None:
                continue

            option_type = 'CE' if pcr_value > config.PCR_BULLISH_THRESHOLD else 'PE'
            trade_direction = 'BUY CE' if option_type == 'CE' else 'BUY PE'
            selected_strike = select_itm_option(current_price, strikes, option_type)
            option_symbol = get_option_symbol(option_instruments, selected_strike, option_type)
            print(f"Selected option symbol for assumed trade: {option_symbol}")

            option_token = get_instrument_token(option_symbol, option_instruments)
            option_candles = fetch_candles(kite, option_token, trading_start, candle_time)
            option_manager = CandleDataManager()
            option_manager.add_candles(option_symbol, option_candles)
            signal = option_manager.get_current_signal_candle(option_symbol)

            if signal and active_trade is None:
                trade_number += 1
                active_trade = {
                    'trade_id': trade_number,
                    'symbol': option_symbol,
                    'strike': selected_strike,
                    'option_type': option_type,
                    'direction': trade_direction,
                    'signal_time': signal.timestamp,
                    'entry_level': signal.high,
                    'sl': max(signal.high - config.PAPER_TRADE_SL_POINTS, 0),
                    'target': signal.high + config.PAPER_TRADE_TARGET_POINTS,
                    'status': 'PENDING',
                    'executed_price': None,
                    'exit': None,
                    'exit_price': None,
                    'exit_time': None,
                    'pcr': pcr_value,
                    'signal_rsi': signal.rsi,
                    'signal_ema': signal.ema
                }
                print(f"\nTRADE {trade_number} SIGNAL ({trade_direction}):")
                print(f"  Option Symbol: {option_symbol}")
                print(f"  Signal Time : {signal.timestamp}")
                print(f"  Entry Level : {signal.high:.2f}")
                print(f"  SL          : {active_trade['sl']:.2f}")
                print(f"  Target      : {active_trade['target']:.2f}")
                print(f"  PCR         : {pcr_value:.4f}")
                print(f"  RSI(10)     : {signal.rsi:.2f}")
                print(f"  EMA(5)      : {signal.ema:.2f}")

        if active_trade is not None:
            option_token = get_instrument_token(active_trade['symbol'], option_instruments)
            option_candles = fetch_candles(kite, option_token, trading_start, candle_time)
            option_latest = get_last_option_candle(option_candles)
            if option_latest is None:
                continue

            if active_trade['status'] == 'PENDING' and option_latest['close'] >= active_trade['entry_level']:
                active_trade['status'] = 'OPEN'
                active_trade['executed_price'] = option_latest['close']
                active_trade['executed_time'] = option_latest['date'] or option_latest['timestamp']
                print(f"\nTRADE {active_trade['trade_id']} BUY EXECUTED:")
                print(f"  Symbol       : {active_trade['symbol']}")
                print(f"  Executed at  : {active_trade['executed_price']:.2f}")
                print(f"  Status       : Open, monitoring SL/Target")

            if active_trade['status'] == 'OPEN':
                hit_target = option_latest['high'] >= active_trade['target']
                hit_sl = option_latest['low'] <= active_trade['sl']
                if hit_target:
                    active_trade['status'] = 'CLOSED'
                    active_trade['exit'] = 'TARGET'
                    active_trade['exit_price'] = active_trade['target']
                    active_trade['exit_time'] = option_latest['date'] or option_latest['timestamp']
                    trades.append(active_trade)
                    print(f"\nTRADE {active_trade['trade_id']} CLOSED: TARGET HIT")
                    print(f"  Exit Price  : {active_trade['exit_price']:.2f}")
                    print(f"  Exit Time   : {active_trade['exit_time']}")
                    active_trade = None
                elif hit_sl:
                    active_trade['status'] = 'CLOSED'
                    active_trade['exit'] = 'SL'
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['exit_time'] = option_latest['date'] or option_latest['timestamp']
                    trades.append(active_trade)
                    print(f"\nTRADE {active_trade['trade_id']} CLOSED: SL HIT")
                    print(f"  Exit Price  : {active_trade['exit_price']:.2f}")
                    print(f"  Exit Time   : {active_trade['exit_time']}")
                    active_trade = None

    print('\nBACKTEST SUMMARY:')
    print(f'  Total candles replayed : {len(nifty_candles)}')
    print(f'  PCR trade setups      : {trade_number}')
    print(f'  Trades closed         : {len(trades)}')
    for trade in trades:
        print(f"  Trade {trade['trade_id']}: {trade['direction']} {trade['symbol']} entry {trade['entry_level']:.2f}, executed {trade['executed_price']:.2f}, exit {trade['exit']} at {trade['exit_price']:.2f}")


if __name__ == '__main__':
    replay_today()
