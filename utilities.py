# utilities.py - Helper functions for trading bot

import logging
from datetime import datetime, time as dt_time

logger = logging.getLogger(__name__)


def is_market_open():
    """Check if NSE market is currently open (9:15 AM to 3:30 PM IST)"""
    now = datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    
    return market_open <= now <= market_close


def format_currency(value):
    """Format value as currency"""
    return f"₹{value:,.2f}"


def get_nearest_strike(current_price, strikes, direction="up"):
    """Get nearest strike in given direction"""
    try:
        if direction == "up":
            return next(s for s in sorted(strikes) if s >= current_price)
        else:
            return next(s for s in sorted(strikes, reverse=True) if s <= current_price)
    except StopIteration:
        logger.warning(f"No strike found in {direction} direction from {current_price}")
        return None


def calculate_pnl(entry_price, current_price, quantity, transaction_type="BUY"):
    """Calculate P&L for a position"""
    if transaction_type == "BUY":
        pnl = (current_price - entry_price) * quantity
    else:
        pnl = (entry_price - current_price) * quantity
    
    pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price != 0 else 0
    return pnl, pnl_percent


def log_trade_details(symbol, transaction_type, quantity, price, pcr_value=None):
    """Log trade execution details"""
    logger.info(f"""
    ╔═══════════════════════════════════╗
    ║       TRADE EXECUTED              ║
    ╠═══════════════════════════════════╣
    ║ Symbol: {symbol:25}  ║
    ║ Type: {transaction_type:28}  ║
    ║ Quantity: {quantity:23}  ║
    ║ Price: ₹{price:24.2f}║
    {'║ PCR: ' + f'{pcr_value:.4f}' + ':' + ' ' * 24 + '║' if pcr_value else ''}
    ╚═══════════════════════════════════╝
    """)
