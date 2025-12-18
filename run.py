#!/usr/bin/env python3
"""
Crypto Trading Bot - Main Entry Point
======================================
Run this file to start the trading bot and web dashboard.
"""

import os
import sys
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOG_FILE),
    ]
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print startup banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║    ₿  CRYPTO TRADING BOT                                      ║
    ║                                                               ║
    ║    Automated trading with configurable triggers               ║
    ║    RSI • Dip % • Volume • Take Profit • Stop Loss             ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_config():
    """Print current configuration."""
    print(f"""
    Configuration:
    ─────────────────────────────────────────────────
    Exchange:       {settings.DEFAULT_EXCHANGE.upper()}
    Mode:           {'PAPER (Safe)' if settings.PAPER_TRADING else '⚠️  LIVE (Real Money)'}
    Coins:          {', '.join([c.split('/')[0] for c in settings.DEFAULT_COINS])}
    
    Buy Triggers:
      • RSI Below:    {settings.DEFAULT_BUY_TRIGGERS['rsi_below']}
      • Dip %:        {settings.DEFAULT_BUY_TRIGGERS['dip_percent']}%
      • Volume Spike: {settings.DEFAULT_BUY_TRIGGERS['volume_spike']}x
    
    Sell Triggers:
      • RSI Above:    {settings.DEFAULT_SELL_TRIGGERS['rsi_above']}
      • Take Profit:  {settings.DEFAULT_SELL_TRIGGERS['take_profit']}%
      • Stop Loss:    {settings.DEFAULT_SELL_TRIGGERS['stop_loss']}%
    
    Dashboard:      http://localhost:{settings.WEB_PORT}
    ─────────────────────────────────────────────────
    """)


def check_dependencies():
    """Check if required packages are installed."""
    missing = []
    
    try:
        import flask
    except ImportError:
        missing.append('flask')
    
    try:
        import flask_socketio
    except ImportError:
        missing.append('flask-socketio')
    
    try:
        import pandas
    except ImportError:
        missing.append('pandas')
    
    try:
        import requests
    except ImportError:
        missing.append('requests')
    
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        print(f"\nInstall with: pip install -r requirements.txt\n")
        return False
    
    return True


def main():
    """Main entry point."""
    print_banner()
    
    if not check_dependencies():
        sys.exit(1)
    
    print_config()
    
    logger.info("Starting Crypto Trading Bot...")
    
    # Import and run the web app
    from web.app import run_app
    
    try:
        run_app()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\n\n👋 Goodbye! Bot stopped.\n")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise


if __name__ == '__main__':
    main()
