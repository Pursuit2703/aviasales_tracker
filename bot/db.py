# bot/db.py
import sqlite3
from typing import Optional, List

DB_FILE = "alerts.db"

def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database and tables."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            origin TEXT NOT NULL,
            hour INTEGER NOT NULL DEFAULT 10,
            minute INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            target_price REAL,
            last_price REAL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()

# ---------- Subscriptions ----------
def add_subscription(user_id: int, origin: str, hour: int = 10, minute: int = 0):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO subscriptions (user_id, origin, hour, minute, enabled) VALUES (?, ?, ?, ?, 1)",
            (user_id, origin, hour, minute)
        )

def list_subscriptions() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM subscriptions WHERE enabled=1").fetchall()

# ---------- Alerts ----------
def add_alert(user_id: int, origin: str, destination: str, target_price: Optional[float], last_price: Optional[float] = None) -> Optional[int]:
    with get_conn() as conn:
        cur = conn.cursor()
        if cur.execute(
            "SELECT 1 FROM alerts WHERE user_id = ? AND origin = ? AND destination = ? AND active = 1",
            (user_id, origin, destination)
        ).fetchone():
            return None  # Already exists

        cur.execute(
            "INSERT INTO alerts (user_id, origin, destination, target_price, last_price, active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, origin, destination, target_price, last_price)
        )
        return cur.lastrowid

def list_alerts() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM alerts WHERE active=1").fetchall()

def list_user_alerts(user_id: int, active_only: bool = True) -> List[sqlite3.Row]:
    with get_conn() as conn:
        if active_only:
            return conn.execute("SELECT * FROM alerts WHERE user_id = ? AND active=1", (user_id,)).fetchall()
        return conn.execute("SELECT * FROM alerts WHERE user_id = ?", (user_id,)).fetchall()

def update_alert_price(alert_id: int, new_price: float):
    with get_conn() as conn:
        conn.execute("UPDATE alerts SET last_price=? WHERE id=?", (new_price, alert_id))

def deactivate_alert(alert_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE alerts SET active=0 WHERE id=?", (alert_id,))

def disable_alert(alert_id: int, user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE alerts SET active=0 WHERE id=? AND user_id=?", (alert_id, user_id))
        return cur.rowcount > 0

def alert_exists(user_id: int, origin: str, destination: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM alerts WHERE user_id=? AND origin=? AND destination=? AND active=1 LIMIT 1",
            (user_id, origin, destination)
        ).fetchone() is not None
