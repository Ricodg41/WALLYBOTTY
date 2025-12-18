"""
Crypto Trading Bot Configuration
================================
Configure your exchange API keys, trading parameters, and default settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# =============================================================================
# EXCHANGE CONFIGURATION
# =============================================================================

# Supported exchanges (using CCXT)
SUPPORTED_EXCHANGES = ['mexc', 'kucoin', 'coinex', 'bybit', 'binance']

# Default exchange (MEXC recommended - 0% maker fees, no KYC)
DEFAULT_EXCHANGE = os.getenv('DEFAULT_EXCHANGE', 'mexc')

# Exchange API credentials (set in .env file)
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')
EXCHANGE_SECRET = os.getenv('EXCHANGE_SECRET', '')
EXCHANGE_PASSWORD = os.getenv('EXCHANGE_PASSWORD', '')  # Some exchanges require this


# =============================================================================
# TRADING PAIRS
# =============================================================================

# Default coins to monitor (Tier 1 & 2 cryptos)
DEFAULT_COINS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'XRP/USDT',
    'DOGE/USDT',
    'ADA/USDT',
    'AVAX/USDT',
    'MATIC/USDT',
]


# =============================================================================
# DEFAULT TRADING TRIGGERS
# =============================================================================

# Buy triggers (all conditions must be met)
DEFAULT_BUY_TRIGGERS = {
    'rsi_below': 30,           # Buy when RSI drops below this value
    'dip_percent': 5.0,        # Buy when price dips X% from recent high
    'volume_spike': 1.5,       # Buy when volume is X times average
    'enabled': True,           # Whether buy triggers are active
}

# Sell triggers (any condition triggers sell)
DEFAULT_SELL_TRIGGERS = {
    'rsi_above': 70,           # Sell when RSI rises above this value
    'rise_percent': 10.0,      # Sell when price rises X% from entry
    'stop_loss': 5.0,          # Sell when price drops X% from entry (stop loss)
    'take_profit': 15.0,       # Sell when profit reaches X% (take profit)
    'enabled': True,           # Whether sell triggers are active
}


# =============================================================================
# INDICATOR SETTINGS
# =============================================================================

# RSI settings
RSI_PERIOD = 14              # Standard RSI period
RSI_OVERBOUGHT = 70          # Overbought threshold
RSI_OVERSOLD = 30            # Oversold threshold

# Price tracking
PRICE_LOOKBACK_HOURS = 24    # Hours to look back for high/low calculations
VOLUME_LOOKBACK_HOURS = 24   # Hours to calculate average volume


# =============================================================================
# TRADING SETTINGS
# =============================================================================

# Paper trading mode (recommended for testing!)
PAPER_TRADING = True

# Trade amount settings
DEFAULT_TRADE_AMOUNT_USDT = 100.0  # Default trade size in USDT
MAX_TRADE_AMOUNT_USDT = 1000.0     # Maximum trade size in USDT
MIN_TRADE_AMOUNT_USDT = 10.0       # Minimum trade size in USDT

# Maximum positions
MAX_OPEN_POSITIONS = 5             # Maximum number of open positions at once
MAX_POSITION_PER_COIN = 1          # Maximum positions per coin


# =============================================================================
# DATA SETTINGS
# =============================================================================

# CoinGecko API (free tier - 30 calls/min)
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3'

# Data refresh intervals (in seconds)
PRICE_UPDATE_INTERVAL = 30         # How often to fetch new prices
INDICATOR_UPDATE_INTERVAL = 60     # How often to recalculate indicators
STRATEGY_CHECK_INTERVAL = 10       # How often to check for trade signals


# =============================================================================
# WEB DASHBOARD
# =============================================================================

WEB_HOST = '0.0.0.0'
WEB_PORT = 5000
DEBUG_MODE = True


# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = 'INFO'
LOG_FILE = 'logs/trading_bot.log'
TRADE_LOG_FILE = 'logs/trades.log'
