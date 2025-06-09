#!/usr/bin/env python3
"""
Bitcoin Price Tracker Web Dashboard
Real-time web interface to view Bitcoin price data and statistics
"""

from flask import Flask, render_template, jsonify
import sqlite3
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Database path
DB_PATH = '/app/data/bitcoin_prices.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def get_latest_stats():
    """Get latest statistics from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all prices
        cursor.execute('SELECT price, timestamp FROM bitcoin_prices ORDER BY timestamp DESC')
        prices_data = cursor.fetchall()
        
        if not prices_data:
            return {
                'latest': 0, 'min': 0, 'max': 0, 'avg': 0, 'count': 0,
                'last_updated': 'No data', 'recommendation': 'No data available'
            }
        
        prices = [row['price'] for row in prices_data]
        latest_price = prices[0]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        # Get recommendation
        if avg_price > 0:
            price_diff_pct = ((latest_price - avg_price) / avg_price) * 100
            position_in_range = (latest_price - min_price) / (max_price - min_price) if max_price > min_price else 0.5
            
            if price_diff_pct <= -5 and position_in_range <= 0.3:
                recommendation = f"🟢 STRONG BUY - Price is {abs(price_diff_pct):.1f}% below average"
            elif price_diff_pct <= -2:
                recommendation = f"🟢 BUY - Price is {abs(price_diff_pct):.1f}% below average"
            elif price_diff_pct >= 5 and position_in_range >= 0.7:
                recommendation = f"🔴 STRONG SELL - Price is {price_diff_pct:.1f}% above average"
            elif price_diff_pct >= 2:
                recommendation = f"🔴 SELL - Price is {price_diff_pct:.1f}% above average"
            else:
                recommendation = f"🟡 HOLD - Price is close to average ({price_diff_pct:+.1f}%)"
        else:
            recommendation = "🟡 HOLD - Insufficient data"
        
        conn.close()
        
        return {
            'latest': latest_price,
            'min': min_price,
            'max': max_price,
            'avg': avg_price,
            'count': len(prices),
            'last_updated': prices_data[0]['timestamp'],
            'recommendation': recommendation
        }
    except Exception as e:
        return {'error': str(e)}

def get_price_history(hours=24):
    """Get price history for charting"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get prices from last X hours
        since_time = datetime.now() - timedelta(hours=hours)
        cursor.execute(
            'SELECT price, timestamp FROM bitcoin_prices WHERE timestamp >= ? ORDER BY timestamp ASC',
            (since_time.strftime('%Y-%m-%d %H:%M:%S'),)
        )
        
        data = cursor.fetchall()
        conn.close()
        
        return [{'price': row['price'], 'timestamp': row['timestamp']} for row in data]
    except Exception as e:
        return []

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def api_stats():
    """API endpoint for latest statistics"""
    return jsonify(get_latest_stats())

@app.route('/api/history/<int:hours>')
def api_history(hours):
    """API endpoint for price history"""
    return jsonify(get_price_history(hours))

@app.route('/api/recent')
def api_recent():
    """API endpoint for recent prices (last 10)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT price, timestamp, api_source FROM bitcoin_prices ORDER BY timestamp DESC LIMIT 10'
        )
        data = cursor.fetchall()
        conn.close()
        
        return jsonify([{
            'price': row['price'],
            'timestamp': row['timestamp'],
            'api_source': row['api_source']
        } for row in data])
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)