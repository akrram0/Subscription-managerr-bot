"""
Database management module
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List


class Database:
    def __init__(self, db_file: str = 'subscriptions.db'):
        self.db_file = db_file
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Subscriptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_type TEXT,
                start_date TIMESTAMP,
                expiry_date TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_type TEXT,
                amount REAL,
                status TEXT DEFAULT 'pending',
                transaction_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def set_user_language(self, user_id: int, language: str):
        """Set user language preference"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET language = ? WHERE user_id = ?
        ''', (language, user_id))
        
        conn.commit()
        conn.close()
    
    def get_user_language(self, user_id: int) -> str:
        """Get user language preference"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return row['language']
        return 'en'
    
    def add_pending_payment(self, user_id: int, plan_type: str, amount: float):
        """Add pending payment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO payments (user_id, plan_type, amount, status)
            VALUES (?, ?, ?, 'pending')
        ''', (user_id, plan_type, amount))
        
        conn.commit()
        conn.close()
    
    def activate_subscription(self, user_id: int, plan_type: str, expiry_date: datetime):
        """Activate user subscription"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Deactivate old subscriptions
        cursor.execute('''
            UPDATE subscriptions SET is_active = 0 WHERE user_id = ?
        ''', (user_id,))
        
        # Create new subscription
        cursor.execute('''
            INSERT INTO subscriptions (user_id, plan_type, start_date, expiry_date, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (user_id, plan_type, datetime.now(), expiry_date))
        
        # Update payment status
        cursor.execute('''
            UPDATE payments SET status = 'completed'
            WHERE user_id = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_subscription(self, user_id: int) -> Optional[Dict]:
        """Get active subscription for user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            subscription = dict(row)
            # Check if expired
            expiry = datetime.fromisoformat(subscription['expiry_date'])
            if expiry < datetime.now():
                subscription['is_active'] = False
                self.deactivate_subscription(user_id)
            return subscription
        return None
    
    def deactivate_subscription(self, user_id: int):
        """Deactivate user subscription"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE subscriptions SET is_active = 0 WHERE user_id = ?
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def remove_pending_payment(self, user_id: int):
        """Remove pending payment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE payments SET status = 'rejected'
            WHERE user_id = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """Get bot statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total users
        cursor.execute('SELECT COUNT(*) as count FROM users')
        total_users = cursor.fetchone()['count']
        
        # Active subscriptions
        cursor.execute('''
            SELECT COUNT(*) as count FROM subscriptions
            WHERE is_active = 1 AND expiry_date > ?
        ''', (datetime.now().isoformat(),))
        active_subscriptions = cursor.fetchone()['count']
        
        # Pending payments
        cursor.execute('''
            SELECT COUNT(*) as count FROM payments WHERE status = 'pending'
        ''')
        pending_payments = cursor.fetchone()['count']
        
        # Total revenue
        cursor.execute('''
            SELECT SUM(amount) as total FROM payments WHERE status = 'completed'
        ''')
        result = cursor.fetchone()
        total_revenue = result['total'] if result['total'] else 0
        
        conn.close()
        
        return {
            'total_users': total_users,
            'active_subscriptions': active_subscriptions,
            'pending_payments': pending_payments,
            'total_revenue': total_revenue
        }
    
    def get_all_active_subscriptions(self) -> List[Dict]:
        """Get all active subscriptions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM subscriptions
            WHERE is_active = 1 AND expiry_date > ?
            ORDER BY expiry_date ASC
        ''', (datetime.now().isoformat(),))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
