"""
Technical Indicators Module
===========================
Calculate RSI, dip percentage, volume metrics, and other indicators.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging

try:
    import pandas_ta as ta
except ImportError:
    ta = None

from config import settings

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """Calculate technical indicators for trading signals."""
    
    def __init__(self):
        self.rsi_period = settings.RSI_PERIOD
        
    def calculate_rsi(self, df: pd.DataFrame, period: int = None) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            df: DataFrame with 'close' column
            period: RSI period (default from settings)
            
        Returns:
            Series with RSI values (0-100)
        """
        period = period or self.rsi_period
        
        if df.empty or 'close' not in df.columns:
            return pd.Series(dtype=float)
        
        # Use pandas-ta if available
        if ta is not None:
            try:
                rsi = ta.rsi(df['close'], length=period)
                return rsi
            except Exception as e:
                logger.warning(f"pandas-ta RSI failed, using manual: {e}")
        
        # Manual RSI calculation
        return self._calculate_rsi_manual(df['close'], period)
    
    def _calculate_rsi_manual(self, prices: pd.Series, period: int) -> pd.Series:
        """Manual RSI calculation without pandas-ta."""
        delta = prices.diff()
        
        gains = delta.where(delta > 0, 0)
        losses = (-delta).where(delta < 0, 0)
        
        avg_gains = gains.rolling(window=period, min_periods=1).mean()
        avg_losses = losses.rolling(window=period, min_periods=1).mean()
        
        rs = avg_gains / avg_losses.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50)  # Default to neutral
    
    def calculate_dip_percent(self, current_price: float, high_price: float) -> float:
        """
        Calculate how much price has dipped from the high.
        
        Args:
            current_price: Current price
            high_price: Recent high price
            
        Returns:
            Dip percentage (positive means price is below high)
        """
        if high_price <= 0:
            return 0.0
        
        dip = ((high_price - current_price) / high_price) * 100
        return max(0, dip)  # Only return positive dips
    
    def calculate_rise_percent(self, current_price: float, low_price: float) -> float:
        """
        Calculate how much price has risen from the low.
        
        Args:
            current_price: Current price
            low_price: Recent low price
            
        Returns:
            Rise percentage (positive means price is above low)
        """
        if low_price <= 0:
            return 0.0
        
        rise = ((current_price - low_price) / low_price) * 100
        return max(0, rise)  # Only return positive rises
    
    def calculate_rise_from_entry(self, current_price: float, entry_price: float) -> float:
        """
        Calculate profit/loss percentage from entry price.
        
        Args:
            current_price: Current price
            entry_price: Entry/buy price
            
        Returns:
            Percentage change (positive = profit, negative = loss)
        """
        if entry_price <= 0:
            return 0.0
        
        return ((current_price - entry_price) / entry_price) * 100
    
    def calculate_volume_spike(self, current_volume: float, avg_volume: float) -> float:
        """
        Calculate volume spike multiplier.
        
        Args:
            current_volume: Current period volume
            avg_volume: Average volume
            
        Returns:
            Volume multiplier (e.g., 2.0 means 2x average)
        """
        if avg_volume <= 0:
            return 1.0
        
        return current_volume / avg_volume
    
    def calculate_average_volume(self, df: pd.DataFrame, periods: int = 24) -> float:
        """
        Calculate average volume over specified periods.
        
        Args:
            df: DataFrame with 'volume' column
            periods: Number of periods to average
            
        Returns:
            Average volume
        """
        if df.empty or 'volume' not in df.columns:
            return 0.0
        
        return df['volume'].tail(periods).mean()
    
    def calculate_moving_average(self, df: pd.DataFrame, period: int = 20, ma_type: str = 'sma') -> pd.Series:
        """
        Calculate moving average.
        
        Args:
            df: DataFrame with 'close' column
            period: MA period
            ma_type: 'sma' or 'ema'
            
        Returns:
            Series with MA values
        """
        if df.empty or 'close' not in df.columns:
            return pd.Series(dtype=float)
        
        if ma_type == 'ema':
            return df['close'].ewm(span=period, adjust=False).mean()
        else:
            return df['close'].rolling(window=period).mean()
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            df: DataFrame with 'close' column
            period: MA period
            std_dev: Standard deviation multiplier
            
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        if df.empty or 'close' not in df.columns:
            empty = pd.Series(dtype=float)
            return empty, empty, empty
        
        middle = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower
    
    def calculate_all_indicators(self, df: pd.DataFrame, current_price: float = None) -> Dict:
        """
        Calculate all indicators for a symbol.
        
        Args:
            df: DataFrame with OHLCV data
            current_price: Optional current price (uses last close if not provided)
            
        Returns:
            Dict with all indicator values
        """
        if df.empty:
            return self._empty_indicators()
        
        current_price = current_price or df['close'].iloc[-1]
        
        # RSI
        rsi_series = self.calculate_rsi(df)
        current_rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
        
        # High/Low from data
        high_24h = df['high'].max() if 'high' in df.columns else df['close'].max()
        low_24h = df['low'].min() if 'low' in df.columns else df['close'].min()
        
        # Dip and Rise percentages
        dip_percent = self.calculate_dip_percent(current_price, high_24h)
        rise_percent = self.calculate_rise_percent(current_price, low_24h)
        
        # Volume
        current_volume = df['volume'].iloc[-1] if 'volume' in df.columns else 0
        avg_volume = self.calculate_average_volume(df)
        volume_spike = self.calculate_volume_spike(current_volume, avg_volume)
        
        # Moving averages
        sma_20 = self.calculate_moving_average(df, 20, 'sma')
        ema_12 = self.calculate_moving_average(df, 12, 'ema')
        
        return {
            'price': current_price,
            'rsi': round(current_rsi, 2),
            'dip_percent': round(dip_percent, 2),
            'rise_percent': round(rise_percent, 2),
            'high_24h': high_24h,
            'low_24h': low_24h,
            'volume': current_volume,
            'avg_volume': avg_volume,
            'volume_spike': round(volume_spike, 2),
            'sma_20': sma_20.iloc[-1] if not sma_20.empty else None,
            'ema_12': ema_12.iloc[-1] if not ema_12.empty else None,
        }
    
    def _empty_indicators(self) -> Dict:
        """Return empty indicator values."""
        return {
            'price': 0,
            'rsi': 50,
            'dip_percent': 0,
            'rise_percent': 0,
            'high_24h': 0,
            'low_24h': 0,
            'volume': 0,
            'avg_volume': 0,
            'volume_spike': 1.0,
            'sma_20': None,
            'ema_12': None,
        }


# Singleton instance
_indicator_calculator = None

def get_indicator_calculator() -> IndicatorCalculator:
    """Get or create the indicator calculator singleton."""
    global _indicator_calculator
    if _indicator_calculator is None:
        _indicator_calculator = IndicatorCalculator()
    return _indicator_calculator
