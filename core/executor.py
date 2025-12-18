"""
Order Executor Module
=====================
Execute trades in paper or live mode via exchange API.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import os

try:
    import ccxt
except ImportError:
    ccxt = None

from config import settings
from core.strategy import TradingSignal, SignalType, get_trading_strategy

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status types."""
    PENDING = 'pending'
    FILLED = 'filled'
    CANCELLED = 'cancelled'
    FAILED = 'failed'


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market' or 'limit'
    quantity: float
    price: float
    status: OrderStatus
    timestamp: datetime
    filled_price: float = 0.0
    fee: float = 0.0
    is_paper: bool = True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'price': self.price,
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'filled_price': self.filled_price,
            'fee': self.fee,
            'is_paper': self.is_paper,
        }


@dataclass
class Trade:
    """Represents a completed trade."""
    trade_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    entry_time: datetime = None
    exit_time: datetime = None
    is_paper: bool = True
    status: str = 'open'  # 'open' or 'closed'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'is_paper': self.is_paper,
            'status': self.status,
        }


class OrderExecutor:
    """
    Execute orders in paper or live mode.
    
    Paper mode simulates trades without real money.
    Live mode executes via exchange API.
    """
    
    def __init__(self, exchange_name: str = None, paper_mode: bool = None):
        self.exchange_name = exchange_name or settings.DEFAULT_EXCHANGE
        self.paper_mode = paper_mode if paper_mode is not None else settings.PAPER_TRADING
        self.exchange = None
        
        # Order and trade tracking
        self.orders: List[Order] = []
        self.trades: Dict[str, Trade] = {}  # trade_id -> Trade
        self._order_counter = 0
        self._trade_counter = 0
        
        # Paper trading balance
        self.paper_balance = {
            'USDT': 10000.0,  # Starting balance
        }
        
        # Initialize exchange if not in paper mode
        if not self.paper_mode:
            self._init_exchange()
        
        # Load trade history
        self._load_trade_history()

    def deposit_paper_funds(self, amount: float):
        """Add funds to paper balance."""
        if self.paper_mode:
            self.paper_balance['USDT'] = self.paper_balance.get('USDT', 0) + amount
            self._save_trade_history()
            logger.info(f"💵 Simulated Deposit: +${amount:.2f}")

    def withdraw_paper_funds(self, amount: float):
        """Withdraw funds from paper balance."""
        if self.paper_mode:
            current = self.paper_balance.get('USDT', 0)
            if current >= amount:
                self.paper_balance['USDT'] = current - amount
                self._save_trade_history()
                logger.info(f"💸 Simulated Withdrawal: -${amount:.2f}")
                return True
            return False

    def reset_paper_funds(self, amount: float = 10000.0):
        """Reset paper balance to initial amount."""
        if self.paper_mode:
            self.paper_balance['USDT'] = amount
            self._save_trade_history()
            logger.info(f"🔄 Balance Reset to: ${amount:.2f}")
    
    def _init_exchange(self):
        """Initialize the exchange connection."""
        if ccxt is None:
            logger.warning("CCXT not installed. Live trading disabled.")
            self.paper_mode = True
            return
        
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            self.exchange = exchange_class({
                'apiKey': settings.EXCHANGE_API_KEY,
                'secret': settings.EXCHANGE_SECRET,
                'password': settings.EXCHANGE_PASSWORD,
                'enableRateLimit': True,
            })
            logger.info(f"Initialized {self.exchange_name} exchange for live trading")
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            self.paper_mode = True
    
    def execute_signal(self, signal: TradingSignal, amount_usdt: float = None) -> Optional[Order]:
        """
        Execute a trading signal.
        
        Args:
            signal: The trading signal to execute
            amount_usdt: Amount in USDT to trade (default from settings)
            
        Returns:
            The created order, or None if execution failed
        """
        if signal.signal_type == SignalType.HOLD:
            return None
        
        amount_usdt = amount_usdt or settings.DEFAULT_TRADE_AMOUNT_USDT
        
        # Validate amount
        if amount_usdt < settings.MIN_TRADE_AMOUNT_USDT:
            logger.warning(f"Trade amount ${amount_usdt} below minimum ${settings.MIN_TRADE_AMOUNT_USDT}")
            return None
        
        if amount_usdt > settings.MAX_TRADE_AMOUNT_USDT:
            amount_usdt = settings.MAX_TRADE_AMOUNT_USDT
            logger.warning(f"Trade amount capped at ${amount_usdt}")
        
        if signal.signal_type == SignalType.BUY:
            return self._execute_buy(signal, amount_usdt)
        elif signal.signal_type == SignalType.SELL:
            return self._execute_sell(signal)
        
        return None
    
    def _execute_buy(self, signal: TradingSignal, amount_usdt: float) -> Optional[Order]:
        """Execute a buy order."""
        symbol = signal.symbol
        price = signal.price
        
        if price <= 0:
            logger.error(f"Invalid price for {symbol}: {price}")
            return None
        
        # Calculate quantity
        quantity = amount_usdt / price
        
        # Check if we can open a position
        strategy = get_trading_strategy()
        if not strategy.can_open_position(symbol):
            logger.warning(f"Cannot open position for {symbol}: max positions reached or already have position")
            return None
        
        if self.paper_mode:
            return self._paper_buy(symbol, quantity, price, signal)
        else:
            return self._live_buy(symbol, quantity, price, signal)
    
    def _paper_buy(self, symbol: str, quantity: float, price: float, signal: TradingSignal) -> Order:
        """Execute a paper buy order."""
        # Check paper balance
        cost = quantity * price
        if self.paper_balance.get('USDT', 0) < cost:
            logger.warning(f"Insufficient paper balance for {symbol}")
            return None
        
        # Deduct from balance
        self.paper_balance['USDT'] -= cost
        
        # Create order
        self._order_counter += 1
        order = Order(
            order_id=f"PAPER-{self._order_counter}",
            symbol=symbol,
            side='buy',
            order_type='market',
            quantity=quantity,
            price=price,
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            filled_price=price,
            fee=cost * 0.001,  # Simulate 0.1% fee
            is_paper=True,
        )
        self.orders.append(order)
        
        # Create trade record
        self._trade_counter += 1
        trade = Trade(
            trade_id=f"TRADE-{self._trade_counter}",
            symbol=symbol,
            side='long',
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(),
            is_paper=True,
            status='open',
        )
        self.trades[trade.trade_id] = trade
        
        # Update strategy position
        strategy = get_trading_strategy()
        strategy.add_position(symbol, price, quantity)
        
        logger.info(f"📈 PAPER BUY: {symbol} | Qty: {quantity:.6f} | Price: ${price:.2f} | Cost: ${cost:.2f}")
        logger.info(f"   Reasons: {', '.join(signal.reasons)}")
        
        self._save_trade_history()
        return order
    
    def _live_buy(self, symbol: str, quantity: float, price: float, signal: TradingSignal) -> Optional[Order]:
        """Execute a live buy order via exchange."""
        if not self.exchange:
            logger.error("Exchange not initialized for live trading")
            return None
        
        try:
            # Execute market order
            result = self.exchange.create_market_buy_order(symbol, quantity)
            
            order = Order(
                order_id=result['id'],
                symbol=symbol,
                side='buy',
                order_type='market',
                quantity=quantity,
                price=price,
                status=OrderStatus.FILLED if result['status'] == 'closed' else OrderStatus.PENDING,
                timestamp=datetime.now(),
                filled_price=result.get('average', price),
                fee=result.get('fee', {}).get('cost', 0),
                is_paper=False,
            )
            self.orders.append(order)
            
            # Create trade record
            self._trade_counter += 1
            trade = Trade(
                trade_id=f"TRADE-{self._trade_counter}",
                symbol=symbol,
                side='long',
                quantity=quantity,
                entry_price=order.filled_price,
                entry_time=datetime.now(),
                is_paper=False,
                status='open',
            )
            self.trades[trade.trade_id] = trade
            
            # Update strategy position
            strategy = get_trading_strategy()
            strategy.add_position(symbol, order.filled_price, quantity)
            
            logger.info(f"🔴 LIVE BUY: {symbol} | Qty: {quantity:.6f} | Price: ${order.filled_price:.2f}")
            
            self._save_trade_history()
            return order
            
        except Exception as e:
            logger.error(f"Live buy failed: {e}")
            return None
    
    def _execute_sell(self, signal: TradingSignal) -> Optional[Order]:
        """Execute a sell order."""
        symbol = signal.symbol
        price = signal.price
        
        strategy = get_trading_strategy()
        position = strategy.get_position(symbol)
        
        if not position:
            logger.warning(f"No position to sell for {symbol}")
            return None
        
        if self.paper_mode:
            return self._paper_sell(symbol, position.quantity, price, position.entry_price, signal)
        else:
            return self._live_sell(symbol, position.quantity, price, position.entry_price, signal)
    
    def _paper_sell(self, symbol: str, quantity: float, price: float, entry_price: float, signal: TradingSignal) -> Order:
        """Execute a paper sell order."""
        # Calculate P/L
        proceeds = quantity * price
        cost = quantity * entry_price
        pnl = proceeds - cost
        pnl_percent = (pnl / cost) * 100
        
        # Add to balance
        self.paper_balance['USDT'] += proceeds
        
        # Create order
        self._order_counter += 1
        order = Order(
            order_id=f"PAPER-{self._order_counter}",
            symbol=symbol,
            side='sell',
            order_type='market',
            quantity=quantity,
            price=price,
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            filled_price=price,
            fee=proceeds * 0.001,
            is_paper=True,
        )
        self.orders.append(order)
        
        # Update trade record
        for trade in self.trades.values():
            if trade.symbol == symbol and trade.status == 'open':
                trade.exit_price = price
                trade.exit_time = datetime.now()
                trade.pnl = pnl
                trade.pnl_percent = pnl_percent
                trade.status = 'closed'
                break
        
        # Close position
        strategy = get_trading_strategy()
        strategy.close_position(symbol)
        
        emoji = "🟢" if pnl >= 0 else "🔴"
        logger.info(f"{emoji} PAPER SELL: {symbol} | Qty: {quantity:.6f} | Price: ${price:.2f} | P/L: ${pnl:.2f} ({pnl_percent:.1f}%)")
        logger.info(f"   Reasons: {', '.join(signal.reasons)}")
        logger.info(f"   Paper Balance: ${self.paper_balance['USDT']:.2f}")
        
        self._save_trade_history()
        return order
    
    def _live_sell(self, symbol: str, quantity: float, price: float, entry_price: float, signal: TradingSignal) -> Optional[Order]:
        """Execute a live sell order via exchange."""
        if not self.exchange:
            logger.error("Exchange not initialized for live trading")
            return None
        
        try:
            result = self.exchange.create_market_sell_order(symbol, quantity)
            
            filled_price = result.get('average', price)
            proceeds = quantity * filled_price
            cost = quantity * entry_price
            pnl = proceeds - cost
            pnl_percent = (pnl / cost) * 100
            
            order = Order(
                order_id=result['id'],
                symbol=symbol,
                side='sell',
                order_type='market',
                quantity=quantity,
                price=price,
                status=OrderStatus.FILLED if result['status'] == 'closed' else OrderStatus.PENDING,
                timestamp=datetime.now(),
                filled_price=filled_price,
                fee=result.get('fee', {}).get('cost', 0),
                is_paper=False,
            )
            self.orders.append(order)
            
            # Update trade record
            for trade in self.trades.values():
                if trade.symbol == symbol and trade.status == 'open':
                    trade.exit_price = filled_price
                    trade.exit_time = datetime.now()
                    trade.pnl = pnl
                    trade.pnl_percent = pnl_percent
                    trade.status = 'closed'
                    break
            
            # Close position
            strategy = get_trading_strategy()
            strategy.close_position(symbol)
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            logger.info(f"{emoji} LIVE SELL: {symbol} | Qty: {quantity:.6f} | Price: ${filled_price:.2f} | P/L: ${pnl:.2f} ({pnl_percent:.1f}%)")
            
            self._save_trade_history()
            return order
            
        except Exception as e:
            logger.error(f"Live sell failed: {e}")
            return None
    
    def get_balance(self) -> Dict[str, float]:
        """Get current balance."""
        if self.paper_mode:
            return self.paper_balance.copy()
        
        if not self.exchange:
            return {}
        
        try:
            balance = self.exchange.fetch_balance()
            return {k: v['free'] for k, v in balance.items() if v['free'] > 0}
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return {}
    
    def get_trade_history(self) -> List[Dict]:
        """Get all trades as list of dicts."""
        return [trade.to_dict() for trade in self.trades.values()]
    
    def get_order_history(self) -> List[Dict]:
        """Get all orders as list of dicts."""
        return [order.to_dict() for order in self.orders]
    
    def get_open_trades(self) -> List[Dict]:
        """Get open trades."""
        return [t.to_dict() for t in self.trades.values() if t.status == 'open']
    
    def get_closed_trades(self) -> List[Dict]:
        """Get closed trades."""
        return [t.to_dict() for t in self.trades.values() if t.status == 'closed']
    
    def get_total_pnl(self) -> float:
        """Get total P/L from closed trades."""
        return sum(t.pnl for t in self.trades.values() if t.status == 'closed')
    
    def _save_trade_history(self):
        """Save trade history to file."""
        try:
            os.makedirs('logs', exist_ok=True)
            with open(settings.TRADE_LOG_FILE, 'w') as f:
                data = {
                    'trades': self.get_trade_history(),
                    'orders': self.get_order_history(),
                    'paper_balance': self.paper_balance,
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save trade history: {e}")
    
    def _load_trade_history(self):
        """Load trade history from file."""
        try:
            if os.path.exists(settings.TRADE_LOG_FILE):
                with open(settings.TRADE_LOG_FILE, 'r') as f:
                    data = json.load(f)
                    # Could restore trades here if needed
                    self.paper_balance = data.get('paper_balance', {'USDT': 10000.0})
        except Exception as e:
            logger.warning(f"Failed to load trade history: {e}")


# Singleton instance
_order_executor = None

def get_order_executor() -> OrderExecutor:
    """Get or create the order executor singleton."""
    global _order_executor
    if _order_executor is None:
        _order_executor = OrderExecutor()
    return _order_executor
