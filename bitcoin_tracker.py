#!/usr/bin/env python3
"""
Bitcoin Price Tracker
"""

import sqlite3
import requests
import time
import logging
from datetime import datetime, timedelta
import os
import signal
import sys
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BitcoinTrackerError(Exception):
    """Base exception for Bitcoin Tracker"""
    pass

class DatabaseError(BitcoinTrackerError):
    """Database operation errors"""
    pass

class APIError(BitcoinTrackerError):
    """API communication errors"""
    pass

class BitcoinTracker:
    def __init__(self, db_path: str = "/app/data/bitcoin_prices.db"):
        self.db_path = db_path
        self.running = True
        self.api_endpoints = {
            'coindesk': 'https://api.coindesk.com/v1/bpi/currentprice/BTC.json',
            'coingecko': 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd'
        }
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.initialize_database()

    @contextmanager
    def get_db_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
        except sqlite3.OperationalError as e:
            logger.error(f"Database operation failed: {e}")
            raise DatabaseError(f"Database operation failed: {e}") from e
        except sqlite3.DatabaseError as e:
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database error: {e}") from e
        finally:
            if conn:
                conn.close()

    def initialize_database(self) -> None:
        """Initialize the SQLite database with proper error handling"""
        try:
            with self.get_db_connection() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS bitcoin_prices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        price REAL NOT NULL,
                        api_source TEXT NOT NULL
                    )
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON bitcoin_prices(timestamp)
                ''')
                conn.commit()
            logger.info("Database initialized successfully")
        except DatabaseError:
            logger.error("Failed to initialize database")
            raise

    def fetch_bitcoin_price(self) -> Optional[Dict[str, Any]]:
        """Fetch Bitcoin price with improved error handling"""
        # Try primary API first
        try:
            response = requests.get(
                self.api_endpoints['coindesk'], 
                timeout=10,
                headers={'User-Agent': 'Bitcoin-Tracker/1.0'}
            )
            response.raise_for_status()
            data = response.json()
            
            price_str = data['bpi']['USD']['rate'].replace(',', '').replace('$', '')
            price = float(price_str)
            
            return {
                'price': price,
                'source': 'CoinDesk',
                'timestamp': datetime.now()
            }
            
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Primary API connection failed: {e}, trying backup API...")
        except requests.exceptions.Timeout as e:
            logger.warning(f"Primary API timeout: {e}, trying backup API...")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Primary API HTTP error: {e}, trying backup API...")
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Primary API data parsing error: {e}, trying backup API...")

        # Try backup API
        try:
            response = requests.get(
                self.api_endpoints['coingecko'], 
                timeout=10,
                headers={'User-Agent': 'Bitcoin-Tracker/1.0'}
            )
            response.raise_for_status()
            data = response.json()
            
            price = float(data['bitcoin']['usd'])
            logger.info(f"Fetched Bitcoin price from CoinGecko: ${price:,.2f}")
            
            return {
                'price': price,
                'source': 'CoinGecko',
                'timestamp': datetime.now()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Backup API request failed: {e}")
            raise APIError(f"All APIs failed. Last error: {e}") from e
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Backup API data parsing error: {e}")
            raise APIError(f"Failed to parse API response: {e}") from e

    def store_price(self, price_data: Dict[str, Any]) -> None:
        """Store price data with improved error handling"""
        try:
            with self.get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO bitcoin_prices (price, api_source) VALUES (?, ?)",
                    (price_data['price'], price_data['source'])
                )
                conn.commit()
        except DatabaseError:
            logger.error("Failed to store price data")
            raise

    def get_statistics(self) -> Dict[str, Any]:
        """Get price statistics with improved error handling"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as count,
                        AVG(price) as avg_price,
                        MIN(price) as min_price,
                        MAX(price) as max_price,
                        MAX(timestamp) as last_updated
                    FROM bitcoin_prices
                ''')
                row = cursor.fetchone()
                
                if row and row['count'] > 0:
                    latest_cursor = conn.execute(
                        "SELECT price FROM bitcoin_prices ORDER BY timestamp DESC LIMIT 1"
                    )
                    latest_row = latest_cursor.fetchone()
                    
                    stats = {
                        'count': row['count'],
                        'average': row['avg_price'],
                        'minimum': row['min_price'],
                        'maximum': row['max_price'],
                        'latest': latest_row['price'] if latest_row else 0,
                        'last_updated': row['last_updated']
                    }
                    
                    # Generate recommendation
                    if stats['latest'] > stats['average'] * 1.05:
                        recommendation = "🔴 SELL - Price is significantly above average (+5%)"
                    elif stats['latest'] < stats['average'] * 0.95:
                        recommendation = "🟢 BUY - Price is significantly below average (-5%)"
                    else:
                        diff_pct = ((stats['latest'] - stats['average']) / stats['average']) * 100
                        recommendation = f"🟡 HOLD - Price is close to average ({diff_pct:+.1f}%)"
                    
                    stats['recommendation'] = recommendation
                    return stats
                else:
                    return {
                        'count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 
                        'latest': 0, 'last_updated': None,
                        'recommendation': "🟡 HOLD - Insufficient data"
                    }
                    
        except DatabaseError:
            logger.error("Failed to get statistics")
            raise

    def display_statistics(self, stats: Dict[str, Any]) -> None:
        """Display formatted statistics"""
        print("\n" + "="*60)
        print(f"📊 BITCOIN PRICE TRACKER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        print(f"💰 Current Price:  ${stats['latest']:,.2f}")
        print(f"📈 Maximum Price:  ${stats['maximum']:,.2f}")
        print(f"📉 Minimum Price:  ${stats['minimum']:,.2f}")
        print(f"📊 Average Price:  ${stats['average']:,.2f}")
        print(f"🔢 Data Points:    {stats['count']:>12}")
        print("-"*60)
        print(f"Recommendation: {stats['recommendation']}")
        print("="*60)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.running = False

    def run(self, fetch_interval: int = 60) -> None:
        """Main tracking loop with improved error handling"""
        print("Bitcoin Price Tracker Started!")
        print(f"Fetching prices every {fetch_interval} seconds...")
        print("Press Ctrl+C to stop gracefully")
        
        iteration = 1
        
        while self.running:
            try:
                logger.info(f"Starting iteration {iteration}")
                
                # Fetch price data
                try:
                    price_data = self.fetch_bitcoin_price()
                    if not price_data:
                        continue
                except APIError as e:
                    logger.error(f"API error in iteration {iteration}: {e}")
                    time.sleep(fetch_interval)
                    iteration += 1
                    continue
                
                # Store price data
                try:
                    self.store_price(price_data)
                except DatabaseError as e:
                    logger.error(f"Database error in iteration {iteration}: {e}")
                    time.sleep(fetch_interval)
                    iteration += 1
                    continue
                
                # Get and display statistics
                try:
                    stats = self.get_statistics()
                    self.display_statistics(stats)
                except DatabaseError as e:
                    logger.error(f"Statistics error in iteration {iteration}: {e}")
                
                logger.info(f"Iteration {iteration} completed successfully")
                iteration += 1
                
                # Wait before next iteration
                time.sleep(fetch_interval)
                
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received. Stopping...")
                break
            except Exception as e:
                logger.error(f"Unexpected error in iteration {iteration}: {e}")
                time.sleep(fetch_interval)
                iteration += 1
        
        print("Bitcoin Price Tracker stopped. Goodbye!")

def main():
    """Main entry point"""
    try:
        tracker = BitcoinTracker()
        tracker.run()
    except Exception as e:
        logger.error(f"Failed to start Bitcoin tracker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()