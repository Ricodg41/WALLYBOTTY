"""
Flask Web Application
=====================
Web dashboard for the crypto trading bot.
"""

import os
import sys
import logging
from datetime import datetime
from threading import Thread
import time

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from core.data_fetcher import get_data_fetcher
from core.indicators import get_indicator_calculator
from core.strategy import get_trading_strategy, SignalType
from core.executor import get_order_executor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Bot state
bot_state = {
    'running': False,
    'paper_mode': settings.PAPER_TRADING,
    'coins': settings.DEFAULT_COINS.copy(),
    'last_update': None,
}


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Get current bot status."""
    executor = get_order_executor()
    strategy = get_trading_strategy()
    
    return jsonify({
        'running': bot_state['running'],
        'paper_mode': bot_state['paper_mode'],
        'coins': bot_state['coins'],
        'balance': executor.get_balance(),
        'triggers': strategy.triggers.to_dict(),
        'positions': [p.to_dict() for p in strategy.get_all_positions().values()],
        'total_pnl': executor.get_total_pnl(),
    })


@app.route('/api/prices')
def get_prices():
    """Get current prices for all coins."""
    fetcher = get_data_fetcher()
    calculator = get_indicator_calculator()
    
    prices_data = []
    prices = fetcher.get_current_prices(bot_state['coins'])
    stats = fetcher.get_24h_stats(bot_state['coins'])
    
    for symbol in bot_state['coins']:
        price = prices.get(symbol, 0)
        stat = stats.get(symbol, {})
        
        # Get OHLCV for indicator calculation
        df = fetcher.get_ohlcv(symbol, '1h', 50)
        indicators = calculator.calculate_all_indicators(df, price)
        
        prices_data.append({
            'symbol': symbol,
            'price': price,
            'change_24h': stat.get('change_percent', 0),
            'high_24h': stat.get('high', 0),
            'low_24h': stat.get('low', 0),
            'volume': stat.get('volume', 0),
            'rsi': indicators.get('rsi', 50),
            'dip_percent': indicators.get('dip_percent', 0),
            'volume_spike': indicators.get('volume_spike', 1),
        })
    
    return jsonify(prices_data)


@app.route('/api/market/top100')
def get_top_100():
    """Get top 100 coins by market cap."""
    fetcher = get_data_fetcher()
    data = fetcher.get_top_100_coins()
    return jsonify(data)


@app.route('/api/triggers', methods=['GET', 'POST'])
def manage_triggers():
    """Get or update trading triggers."""
    strategy = get_trading_strategy()
    
    if request.method == 'POST':
        data = request.json
        strategy.update_triggers(data)
        return jsonify({'success': True, 'triggers': strategy.triggers.to_dict()})
    
    return jsonify(strategy.triggers.to_dict())


@app.route('/api/coins', methods=['GET', 'POST'])
def manage_coins():
    """Get or update coin list."""
    if request.method == 'POST':
        data = request.json
        bot_state['coins'] = data.get('coins', settings.DEFAULT_COINS)
        return jsonify({'success': True, 'coins': bot_state['coins']})
    
    return jsonify(bot_state['coins'])


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot."""
    if not bot_state['running']:
        bot_state['running'] = True
        Thread(target=run_bot_loop, daemon=True).start()
        logger.info("Trading bot started")
    return jsonify({'success': True, 'running': True})


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot."""
    bot_state['running'] = False
    logger.info("Trading bot stopped")
    return jsonify({'success': True, 'running': False})


@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Set paper/live trading mode."""
    data = request.json
    paper_mode = data.get('paper_mode', True)
    bot_state['paper_mode'] = paper_mode
    
    # Update executor
    executor = get_order_executor()
    executor.paper_mode = paper_mode
    
    logger.info(f"Trading mode set to: {'PAPER' if paper_mode else 'LIVE'}")
    return jsonify({'success': True, 'paper_mode': paper_mode})


@app.route('/api/wallet/deposit', methods=['POST'])
def wallet_deposit():
    """Deposit simulated funds."""
    data = request.json
    amount = float(data.get('amount', 0))
    if amount > 0:
        executor = get_order_executor()
        executor.deposit_paper_funds(amount)
        logger.info(f"Wallet deposit: ${amount}")
        return jsonify({'success': True, 'balance': executor.get_balance()})
    return jsonify({'success': False, 'error': 'Invalid amount'})


@app.route('/api/wallet/withdraw', methods=['POST'])
def wallet_withdraw():
    """Withdraw simulated funds."""
    data = request.json
    amount = float(data.get('amount', 0))
    if amount > 0:
        executor = get_order_executor()
        success = executor.withdraw_paper_funds(amount)
        if success:
            logger.info(f"Wallet withdrawal: ${amount}")
            return jsonify({'success': True, 'balance': executor.get_balance()})
        return jsonify({'success': False, 'error': 'Insufficient funds'})
    return jsonify({'success': False, 'error': 'Invalid amount'})


@app.route('/api/wallet/reset', methods=['POST'])
def wallet_reset():
    """Reset simulated wallet."""
    data = request.json
    amount = float(data.get('amount', 10000.0))
    executor = get_order_executor()
    executor.reset_paper_funds(amount)
    logger.info(f"Wallet reset to: ${amount}")
    return jsonify({'success': True, 'balance': executor.get_balance()})


@app.route('/api/trades')
def get_trades():
    """Get trade history."""
    executor = get_order_executor()
    return jsonify({
        'open': executor.get_open_trades(),
        'closed': executor.get_closed_trades(),
        'total_pnl': executor.get_total_pnl(),
    })


@app.route('/api/chart/<symbol>')
def get_chart_data(symbol):
    """Get chart data for a specific symbol."""
    # Convert URL-safe symbol back to trading pair
    symbol = symbol.replace('-', '/')
    
    timeframe = request.args.get('timeframe', '1h')
    limit = int(request.args.get('limit', 100))
    
    fetcher = get_data_fetcher()
    calculator = get_indicator_calculator()
    
    # Get OHLCV data
    df = fetcher.get_ohlcv(symbol, timeframe, limit)
    
    if df.empty:
        return jsonify({'error': 'No data available', 'data': []})
    
    # Get current stats
    prices = fetcher.get_current_prices([symbol])
    stats = fetcher.get_24h_stats([symbol])
    current_price = prices.get(symbol, 0)
    stat = stats.get(symbol, {})
    
    # Calculate indicators
    indicators = calculator.calculate_all_indicators(df, current_price)
    
    # Format OHLCV for Chart.js
    chart_data = []
    for _, row in df.iterrows():
        chart_data.append({
            'x': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
            'o': row['open'],
            'h': row['high'],
            'l': row['low'],
            'c': row['close'],
        })
    
    return jsonify({
        'symbol': symbol,
        'timeframe': timeframe,
        'data': chart_data,
        'current_price': current_price,
        'rsi': indicators.get('rsi', 50),
        'high_24h': stat.get('high', indicators.get('high_24h', 0)),
        'low_24h': stat.get('low', indicators.get('low_24h', 0)),
        'dip_percent': indicators.get('dip_percent', 0),
        'volume_spike': indicators.get('volume_spike', 1),
    })


# =============================================================================
# WEBSOCKET EVENTS
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected to WebSocket")
    emit('status', {'connected': True})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected from WebSocket")


@socketio.on('get_update')
def handle_get_update():
    """Send current data to client."""
    send_update()


# =============================================================================
# BOT LOOP
# =============================================================================

def run_bot_loop():
    """Main bot trading loop."""
    logger.info("Bot loop started")
    
    while bot_state['running']:
        try:
            check_for_signals()
            send_update()
            time.sleep(settings.STRATEGY_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            time.sleep(5)
    
    logger.info("Bot loop stopped")


def check_for_signals():
    """Check all coins for trading signals."""
    fetcher = get_data_fetcher()
    calculator = get_indicator_calculator()
    strategy = get_trading_strategy()
    executor = get_order_executor()
    
    for symbol in bot_state['coins']:
        try:
            # Get data
            df = fetcher.get_ohlcv(symbol, '1h', 50)
            prices = fetcher.get_current_prices([symbol])
            current_price = prices.get(symbol, 0)
            
            if current_price <= 0:
                continue
            
            # Calculate indicators
            indicators = calculator.calculate_all_indicators(df, current_price)
            
            # Evaluate strategy
            signal = strategy.evaluate(symbol, indicators)
            
            # Execute signal
            if signal.signal_type != SignalType.HOLD:
                order = executor.execute_signal(signal)
                if order:
                    # Emit trade event to clients
                    socketio.emit('trade', {
                        'symbol': symbol,
                        'signal': signal.signal_type.value,
                        'price': current_price,
                        'reasons': signal.reasons,
                        'timestamp': datetime.now().isoformat(),
                    })
        
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")


def send_update():
    """Send current state to all connected clients."""
    try:
        fetcher = get_data_fetcher()
        calculator = get_indicator_calculator()
        strategy = get_trading_strategy()
        executor = get_order_executor()
        
        # Get prices and indicators
        prices_data = []
        prices = fetcher.get_current_prices(bot_state['coins'])
        
        for symbol in bot_state['coins']:
            price = prices.get(symbol, 0)
            df = fetcher.get_ohlcv(symbol, '1h', 50)
            indicators = calculator.calculate_all_indicators(df, price)
            
            prices_data.append({
                'symbol': symbol,
                'price': price,
                'rsi': indicators.get('rsi', 50),
                'dip_percent': indicators.get('dip_percent', 0),
                'volume_spike': indicators.get('volume_spike', 1),
            })
        
        bot_state['last_update'] = datetime.now().isoformat()
        
        socketio.emit('update', {
            'running': bot_state['running'],
            'paper_mode': bot_state['paper_mode'],
            'prices': prices_data,
            'balance': executor.get_balance(),
            'positions': [p.to_dict() for p in strategy.get_all_positions().values()],
            'total_pnl': executor.get_total_pnl(),
            'last_update': bot_state['last_update'],
        })
        
    except Exception as e:
        logger.error(f"Error sending update: {e}")


def run_app():
    """Run the Flask application."""
    logger.info(f"Starting web dashboard on http://{settings.WEB_HOST}:{settings.WEB_PORT}")
    socketio.run(app, host=settings.WEB_HOST, port=settings.WEB_PORT, debug=settings.DEBUG_MODE)


if __name__ == '__main__':
    run_app()
