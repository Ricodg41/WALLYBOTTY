"""
Data Fetcher Module
===================
Fetches market data from CoinGecko (free) and exchange APIs.
"""

import time
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

try:
    import ccxt
except ImportError:
    ccxt = None

from config import settings

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches market data from multiple sources."""
    
    def __init__(self, exchange_name: str = None):
        self.exchange_name = exchange_name or settings.DEFAULT_EXCHANGE
        self.exchange = None
        self._init_exchange()
        
        # CoinGecko coin ID mappings
        self.coingecko_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'SOL': 'solana',
            'XRP': 'ripple',
            'DOGE': 'dogecoin',
            'ADA': 'cardano',
            'AVAX': 'avalanche-2',
            'MATIC': 'matic-network',
            'DOT': 'polkadot',
            'LINK': 'chainlink',
            'SHIB': 'shiba-inu',
            'LTC': 'litecoin',
        }
        
        # Cache for rate limiting
        self._price_cache = {}
        self._cache_timestamp = 0
        self._cache_duration = 10  # seconds
    
    def _init_exchange(self):
        """Initialize the exchange connection."""
        if ccxt is None:
            logger.warning("CCXT not installed. Exchange features disabled.")
            return
            
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            self.exchange = exchange_class({
                'apiKey': settings.EXCHANGE_API_KEY,
                'secret': settings.EXCHANGE_SECRET,
                'password': settings.EXCHANGE_PASSWORD,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                }
            })
            
            # Enable sandbox/testnet if available and in paper mode
            if settings.PAPER_TRADING and hasattr(self.exchange, 'set_sandbox_mode'):
                try:
                    self.exchange.set_sandbox_mode(True)
                except:
                    pass
                    
            logger.info(f"Initialized {self.exchange_name} exchange")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            self.exchange = None
    
    def get_current_prices(self, symbols: List[str] = None) -> Dict[str, float]:
        """
        Get current prices for specified symbols.
        
        Args:
            symbols: List of symbols like ['BTC/USDT', 'ETH/USDT']
            
        Returns:
            Dict mapping symbol to current price
        """
        symbols = symbols or settings.DEFAULT_COINS
        
        # Check cache
        if time.time() - self._cache_timestamp < self._cache_duration:
            return self._price_cache
        
        prices = {}
        
        # Try exchange first (more accurate for trading)
        if self.exchange:
            try:
                tickers = self.exchange.fetch_tickers(symbols)
                for symbol, ticker in tickers.items():
                    prices[symbol] = ticker['last']
                self._price_cache = prices
                self._cache_timestamp = time.time()
                return prices
            except Exception as e:
                logger.warning(f"Exchange fetch failed, falling back to CoinGecko: {e}")
        
        # Fallback to CoinGecko
        prices = self._fetch_coingecko_prices(symbols)
        self._price_cache = prices
        self._cache_timestamp = time.time()
        return prices
    
    def _fetch_coingecko_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch prices from CoinGecko API."""
        prices = {}
        
        # Extract coin names from symbols
        coin_ids = []
        symbol_to_id = {}
        
        for symbol in symbols:
            base = symbol.split('/')[0]
            if base in self.coingecko_ids:
                coin_id = self.coingecko_ids[base]
                coin_ids.append(coin_id)
                symbol_to_id[coin_id] = symbol
        
        if not coin_ids:
            return prices
        
        try:
            url = f"{settings.COINGECKO_API_URL}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true',
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for coin_id, price_data in data.items():
                symbol = symbol_to_id.get(coin_id)
                if symbol:
                    prices[symbol] = price_data.get('usd', 0)
                    
        except Exception as e:
            logger.error(f"CoinGecko API error: {e}")
        
        return prices
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """
        Get OHLCV (candlestick) data for a symbol.
        
        Args:
            symbol: Trading pair like 'BTC/USDT'
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if self.exchange:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except Exception as e:
                logger.warning(f"Failed to fetch OHLCV from exchange: {e}")
        
        # Fallback to CoinGecko market chart
        return self._fetch_coingecko_ohlcv(symbol, limit)
    
    def _fetch_coingecko_ohlcv(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV-like data from CoinGecko."""
        base = symbol.split('/')[0]
        coin_id = self.coingecko_ids.get(base)
        
        if not coin_id:
            return pd.DataFrame()
        
        try:
            # CoinGecko provides market_chart data
            days = min(limit // 24 + 1, 30)  # Approximate days needed
            url = f"{settings.COINGECKO_API_URL}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Convert to OHLCV-like format
            prices = data.get('prices', [])
            volumes = data.get('total_volumes', [])
            
            if not prices:
                return pd.DataFrame()
            
            # CoinGecko gives us prices, we'll simulate OHLCV
            df = pd.DataFrame(prices, columns=['timestamp', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['high'] = df[['open', 'close']].max(axis=1)
            df['low'] = df[['open', 'close']].min(axis=1)
            
            if volumes:
                vol_df = pd.DataFrame(volumes, columns=['ts', 'volume'])
                df['volume'] = vol_df['volume'].values[:len(df)]
            else:
                df['volume'] = 0
            
            return df.tail(limit)
            
        except Exception as e:
            logger.error(f"CoinGecko OHLCV error: {e}")
            return pd.DataFrame()
    
    def get_24h_stats(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """
        Get 24-hour statistics for symbols.
        
        Returns:
            Dict with high, low, volume, change_percent for each symbol
        """
        symbols = symbols or settings.DEFAULT_COINS
        stats = {}
        
        if self.exchange:
            try:
                tickers = self.exchange.fetch_tickers(symbols)
                for symbol, ticker in tickers.items():
                    stats[symbol] = {
                        'high': ticker.get('high', 0),
                        'low': ticker.get('low', 0),
                        'volume': ticker.get('baseVolume', 0),
                        'change_percent': ticker.get('percentage', 0),
                        'last': ticker.get('last', 0),
                    }
                return stats
            except Exception as e:
                logger.warning(f"Exchange stats failed: {e}")
        
        # Fallback to CoinGecko
        return self._fetch_coingecko_stats(symbols)
    
    def _fetch_coingecko_stats(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch 24h stats from CoinGecko."""
        stats = {}
        
        coin_ids = []
        symbol_to_id = {}
        
        for symbol in symbols:
            base = symbol.split('/')[0]
            if base in self.coingecko_ids:
                coin_id = self.coingecko_ids[base]
                coin_ids.append(coin_id)
                symbol_to_id[coin_id] = symbol
        
        try:
            url = f"{settings.COINGECKO_API_URL}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ','.join(coin_ids),
                'sparkline': 'false',
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for coin in data:
                coin_id = coin.get('id')
                symbol = symbol_to_id.get(coin_id)
                if symbol:
                    stats[symbol] = {
                        'high': coin.get('high_24h', 0),
                        'low': coin.get('low_24h', 0),
                        'volume': coin.get('total_volume', 0),
                        'change_percent': coin.get('price_change_percentage_24h', 0),
                        'last': coin.get('current_price', 0),
                    }
                    
        except Exception as e:
            logger.error(f"CoinGecko stats error: {e}")
        
        return stats
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """Get order book for a symbol."""
        if not self.exchange:
            return {'bids': [], 'asks': []}
        
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit)
            return {
                'bids': order_book['bids'][:limit],
                'asks': order_book['asks'][:limit],
            }
        except Exception as e:
            logger.error(f"Order book fetch error: {e}")
            return {'bids': [], 'asks': []}

    def get_top_100_coins(self) -> List[Dict]:
        """
        Get top 100 coins by market cap from CoinGecko.
        Cached for 60 seconds to respect rate limits.
        """
        # Check cache (separate from price cache)
        if hasattr(self, '_top_100_cache') and \
           hasattr(self, '_top_100_timestamp') and \
           time.time() - self._top_100_timestamp < 60:
            return self._top_100_cache
            
        try:
            url = f"{settings.COINGECKO_API_URL}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 100,
                'page': 1,
                'sparkline': 'false',
                'price_change_percentage': '24h',
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Formatted data
            top_100 = []
            for coin in data:
                top_100.append({
                    'rank': coin.get('market_cap_rank'),
                    'symbol': coin.get('symbol', '').upper(),
                    'name': coin.get('name'),
                    'price': coin.get('current_price', 0),
                    'change_24h': coin.get('price_change_percentage_24h', 0),
                    'volume': coin.get('total_volume', 0),
                    'market_cap': coin.get('market_cap', 0),
                    'image': coin.get('image'),
                })
            
            self._top_100_cache = top_100
            self._top_100_timestamp = time.time()
            return top_100
            
        except Exception as e:
            logger.error(f"Top 100 fetch error: {e}")
            return getattr(self, '_top_100_cache', [])


# Singleton instance
_data_fetcher = None

def get_data_fetcher() -> DataFetcher:
    """Get or create the data fetcher singleton."""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher()
    return _data_fetcher
