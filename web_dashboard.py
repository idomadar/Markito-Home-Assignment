#!/usr/bin/env python3
"""
Bitcoin Price Tracker Web Dashboard with Enhanced Error Handling and Context Management
"""

import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Generator
from flask import Flask, render_template, jsonify
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardError(Exception):
    """Base exception for Dashboard"""
    pass

class DatabaseError(DashboardError):
    """Database operation errors"""
    pass

class DataNotFoundError(DashboardError):
    """Data not found errors"""
    pass

app = Flask(__name__)

class BitcoinDashboard:
    def __init__(self, db_path: str = "/app/data/bitcoin_prices.db"):
        self.db_path = db_path

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
                
                if not row or row['count'] == 0:
                    raise DataNotFoundError("No price data available")
                
                # Get latest price
                latest_cursor = conn.execute(
                    "SELECT price FROM bitcoin_prices ORDER BY timestamp DESC LIMIT 1"
                )
                latest_row = latest_cursor.fetchone()
                
                if not latest_row:
                    raise DataNotFoundError("No latest price data available")
                
                stats = {
                    'count': row['count'],
                    'avg': float(row['avg_price']),
                    'min': float(row['min_price']),
                    'max': float(row['max_price']),
                    'latest': float(latest_row['price']),
                    'last_updated': row['last_updated']
                }
                
                # Generate recommendation
                if stats['latest'] > stats['avg'] * 1.05:
                    recommendation = "🔴 SELL - Price is significantly above average (+5%)"
                elif stats['latest'] < stats['avg'] * 0.95:
                    recommendation = "🟢 BUY - Price is significantly below average (-5%)"
                else:
                    diff_pct = ((stats['latest'] - stats['avg']) / stats['avg']) * 100
                    recommendation = f"🟡 HOLD - Price is close to average ({diff_pct:+.1f}%)"
                
                stats['recommendation'] = recommendation
                return stats
                
        except DatabaseError:
            logger.error("Failed to get statistics from database")
            raise
        except DataNotFoundError:
            logger.warning("No data found in database")
            raise

    def get_price_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get price history with improved error handling"""
        try:
            with self.get_db_connection() as conn:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                cursor = conn.execute(
                    '''SELECT timestamp, price 
                       FROM bitcoin_prices 
                       WHERE timestamp >= ? 
                       ORDER BY timestamp ASC''',
                    (cutoff_time.isoformat(),)
                )
                rows = cursor.fetchall()
                
                return [
                    {
                        'timestamp': row['timestamp'],
                        'price': float(row['price'])
                    } 
                    for row in rows
                ]
                
        except DatabaseError:
            logger.error(f"Failed to get price history for {hours} hours")
            raise

    def get_recent_data(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent price data with improved error handling"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.execute(
                    '''SELECT timestamp, price, api_source 
                       FROM bitcoin_prices 
                       ORDER BY timestamp DESC 
                       LIMIT ?''',
                    (limit,)
                )
                rows = cursor.fetchall()
                
                return [
                    {
                        'timestamp': row['timestamp'],
                        'price': float(row['price']),
                        'api_source': row['api_source']
                    } 
                    for row in rows
                ]
                
        except DatabaseError:
            logger.error(f"Failed to get recent data (limit: {limit})")
            raise

# Initialize dashboard
dashboard = BitcoinDashboard()

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return f"Dashboard error: {e}", 500

@app.route('/api/stats')
def get_stats():
    """API endpoint for statistics"""
    try:
        stats = dashboard.get_statistics()
        return jsonify(stats)
    except DataNotFoundError as e:
        logger.warning(f"No data available: {e}")
        return jsonify({
            'error': 'No data available yet',
            'count': 0,
            'avg': 0,
            'min': 0,
            'max': 0,
            'latest': 0,
            'last_updated': None,
            'recommendation': '🟡 HOLD - No data available'
        }), 200
    except DatabaseError as e:
        logger.error(f"Database error in stats endpoint: {e}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in stats endpoint: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/history/<int:hours>')
def get_history(hours: int):
    """API endpoint for price history"""
    try:
        # Validate hours parameter
        if hours <= 0 or hours > 168:  # Max 1 week
            return jsonify({'error': 'Hours must be between 1 and 168'}), 400
            
        history = dashboard.get_price_history(hours)
        return jsonify(history)
    except DatabaseError as e:
        logger.error(f"Database error in history endpoint: {e}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in history endpoint: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/recent')
def get_recent():
    """API endpoint for recent price data"""
    try:
        recent_data = dashboard.get_recent_data()
        return jsonify(recent_data)
    except DatabaseError as e:
        logger.error(f"Database error in recent endpoint: {e}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in recent endpoint: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)