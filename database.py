import os
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "subscriptions.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                billing_period TEXT NOT NULL CHECK(billing_period IN ('monthly','yearly')),
                next_payment_date TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_subs_date ON subscriptions(next_payment_date)
        """)


def ensure_user(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )


def add_subscription(user_id: int, name: str, price: float, billing_period: str, next_payment_date: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO subscriptions (user_id, name, price, billing_period, next_payment_date)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, name, price, billing_period, next_payment_date)
        )
        return cur.lastrowid


def get_subscriptions(user_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY next_payment_date",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_subscription(sub_id: int, user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, user_id)
        ).fetchone()
        return dict(row) if row else None


def delete_subscription(sub_id: int, user_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, user_id)
        )


def update_subscription(sub_id: int, user_id: int, field: str, value):
    allowed_fields = {"name", "price", "billing_period", "next_payment_date"}
    if field == "date":
        field = "next_payment_date"
    if field not in allowed_fields:
        raise ValueError(f"Invalid field: {field}")
    with get_conn() as conn:
        conn.execute(
            f"UPDATE subscriptions SET {field} = ? WHERE id = ? AND user_id = ?",
            (value, sub_id, user_id)
        )


def get_subscriptions_due_on(date_str: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE next_payment_date = ?",
            (date_str,)
        ).fetchall()
        return [dict(r) for r in rows]
