"""
Database Layer — Async SQLite Operations
==========================================
Handles all database operations for users and subscriptions.
"""

import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = "subscriptions.db"
logger = logging.getLogger(__name__)


async def init_db():
    """Initialize the database and create tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table with language preference
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Subscriptions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                cost REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                billing_cycle TEXT NOT NULL DEFAULT 'monthly',
                next_payment_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()
        logger.info("Database initialized successfully.")


# ── User Operations ──────────────────────────────────────────

async def get_user_language(user_id: int) -> Optional[str]:
    """Get the user's language preference. Returns None if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_user_language(user_id: int, language: str):
    """Set or update the user's language preference."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, language) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET language = ?""",
            (user_id, language, language)
        )
        await db.commit()


async def ensure_user_exists(user_id: int):
    """Ensure a user record exists in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


# ── Subscription Operations ──────────────────────────────────

async def add_subscription(user_id: int, service_name: str, cost: float,
                           currency: str, billing_cycle: str,
                           next_payment_date: str) -> int:
    """Add a new subscription. Returns the subscription ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO subscriptions 
               (user_id, service_name, cost, currency, billing_cycle, next_payment_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, service_name, cost, currency, billing_cycle, next_payment_date)
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_subscriptions(user_id: int) -> list:
    """Get all active subscriptions for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM subscriptions 
               WHERE user_id = ? AND is_active = 1 
               ORDER BY next_payment_date ASC""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_subscription(sub_id: int, user_id: int) -> bool:
    """Soft-delete a subscription. Returns True if successful."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE subscriptions SET is_active = 0 WHERE id = ? AND user_id = ?",
            (sub_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_due_subscriptions(days_ahead: int) -> list:
    """Get all active subscriptions due in exactly `days_ahead` days."""
    target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE is_active = 1 AND next_payment_date = ?",
            (target_date,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_past_due_subscriptions() -> list:
    """Get all active subscriptions that are past due."""
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE is_active = 1 AND next_payment_date < ?",
            (today,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_next_payment_date(sub_id: int, new_date: str):
    """Update the next payment date for a subscription."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET next_payment_date = ? WHERE id = ?",
            (new_date, sub_id)
        )
        await db.commit()
