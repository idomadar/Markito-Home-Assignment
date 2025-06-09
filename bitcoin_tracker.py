#!/usr/bin/env python3
"""
Bitcoin Price Tracker
Fetches Bitcoin price every minute, calculates statistics, and provides trading recommendations.
"""

import requests
import time
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import statistics
import os
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/bitcoin_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BitcoinTracker:
    def __init__(self, db_path: str = '/app/data/bitcoin_prices.db'):
        self.db_path = db_path
        self.api_url = "https://api.coindesk.com/v1/bpi/currentprice/BTC.json"
        self.backup_api_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        self.running = True
        self.init_database()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def init_database(self):
        """Initialize SQLite database with prices table"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bitcoin_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    price REAL NOT NULL,
                    api_source TEXT DEFAULT 'coindesk'
                )
            ''')
            
            # Create index for better query performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON bitcoin_prices(timestamp)
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def fetch_bitcoin_price(self) -> Optional[float]:
        """Fetch current Bitcoin price from API with fallback"""
        try:
            # Primary API - CoinDesk
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            price_str = data['bpi']['USD']['rate'].replace(',', '').replace('$', '')
            price = float(price_str)
            logger.info(f"Fetched Bitcoin price from CoinDesk: ${price:,.2f}")
            return price
            
        except Exception as e:
            logger.warning(f"Primary API failed: {e}, trying backup API...")
            
            try:
                # Backup API - CoinGecko
                response = requests.get(self.backup_api_url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                price = float(data['bitcoin']['usd'])
                logger.info(f"Fetched Bitcoin price from CoinGecko: ${price:,.2f}")
                return price
                
            except Exception as backup_e:
                logger.error(f"Both APIs failed. Backup error: {backup_e}")
                return None
    
    def store_price(self, price: float, api_source: str = 'coindesk'):
        """Store Bitcoin price in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'INSERT INTO bitcoin_prices (price, api_source) VALUES (?, ?)',
                (price, api_source)
            )
            
            conn.commit()
            conn.close()
            logger.debug(f"Stored price ${price:,.2f} in database")
            
        except Exception as e:
            logger.error(f"Failed to store price in database: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, float]:
        """Calculate min, max, and average prices from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT price FROM bitcoin_prices 
                ORDER BY timestamp DESC
            ''')
            
            prices = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not prices:
                return {'min': 0, 'max': 0, 'avg': 0, 'count': 0, 'latest': 0}
            
            stats = {
                'min': min(prices),
                'max': max(prices),
                'avg': statistics.mean(prices),
                'count': len(prices),
                'latest': prices[0]  # Most recent price
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}")
            return {'min': 0, 'max': 0, 'avg': 0, 'count': 0, 'latest': 0}
    
    def get_recommendation(self, current_price: float, avg_price: float, 
                          min_price: float, max_price: float) -> str:
        """Generate buy/sell recommendation based on current price vs statistics"""
        
        if avg_price == 0:
            return "HOLD - Insufficient data for recommendation"
        
        # Calculate percentage difference from average
        price_diff_pct = ((current_price - avg_price) / avg_price) * 100
        
        # Calculate position relative to min-max range
        if max_price > min_price:
            position_in_range = (current_price - min_price) / (max_price - min_price)
        else:
            position_in_range = 0.5
        
        # Recommendation logic
        if price_diff_pct <= -5 and position_in_range <= 0.3:
            return f"🟢 STRONG BUY - Price is {abs(price_diff_pct):.1f}% below average and near recent lows"
        elif price_diff_pct <= -2:
            return f"🟢 BUY - Price is {abs(price_diff_pct):.1f}% below average"
        elif price_diff_pct >= 5 and position_in_range >= 0.7:
            return f"🔴 STRONG SELL - Price is {price_diff_pct:.1f}% above average and near recent highs"
        elif price_diff_pct >= 2:
            return f"🔴 SELL - Price is {price_diff_pct:.1f}% above average"
        else:
            return f"🟡 HOLD - Price is close to average ({price_diff_pct:+.1f}%)"
    
    def print_status(self, stats: Dict[str, float]):
        """Print formatted status information"""
        print("\n" + "="*60)
        print(f"BITCOIN PRICE TRACKER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        print(f"Current Price:  ${stats['latest']:>10,.2f}")
        print(f"Maximum Price:  ${stats['max']:>10,.2f}")
        print(f"Minimum Price:  ${stats['min']:>10,.2f}")
        print(f"Average Price:  ${stats['avg']:>10,.2f}")
        print(f"Data Points:    {stats['count']:>10,}")
        print("-"*60)
        
        recommendation = self.get_recommendation(
            stats['latest'], stats['avg'], stats['min'], stats['max']
        )
        print(f" Recommendation: {recommendation}")
        print("="*60)
    
    def run(self):
        """Main execution loop"""
        logger.info("Starting Bitcoin Price Tracker...")
        print(" Bitcoin Price Tracker Started!")
        print("Fetching prices every 60 seconds...")
        print("Press Ctrl+C to stop gracefully")
        
        iteration = 0
        
        while self.running:
            try:
                iteration += 1
                logger.info(f"Starting iteration {iteration}")
                
                # Fetch current Bitcoin price
                current_price = self.fetch_bitcoin_price()
                
                if current_price is not None:
                    # Store price in database
                    api_source = 'coindesk'  # Could be dynamic based on which API succeeded
                    self.store_price(current_price, api_source)
                    
                    # Get statistics
                    stats = self.get_statistics()
                    
                    # Print status
                    self.print_status(stats)
                    
                    logger.info(f"Iteration {iteration} completed successfully")
                else:
                    logger.error("Failed to fetch Bitcoin price, skipping iteration")
                    print(f"Failed to fetch price at {datetime.now().strftime('%H:%M:%S')}")
                
                # Wait for next iteration (60 seconds)
                if self.running:
                    logger.debug("Waiting 60 seconds for next iteration...")
                    time.sleep(60)
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                print(f"Error: {e}")
                if self.running:
                    time.sleep(60)  # Wait before retrying
        
        logger.info("Bitcoin Price Tracker stopped")
        print("\n Bitcoin Price Tracker stopped gracefully!")

def main():
    """Main entry point"""
    try:
        tracker = BitcoinTracker()
        tracker.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()