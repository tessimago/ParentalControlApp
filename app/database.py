import os
import sqlite3
from datetime import datetime

import bcrypt

from app.config import DB_PATH, DATA_DIR, DEFAULT_PASSWORD, DEFAULT_PORT


def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS schedule_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL UNIQUE,
            daily_limit_minutes INTEGER NOT NULL,
            action TEXT NOT NULL DEFAULT 'warn'
        );

        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            process_name TEXT NOT NULL,
            seconds_used INTEGER NOT NULL DEFAULT 0,
            last_updated TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_date_process
            ON usage_logs(date, process_name);

        CREATE TABLE IF NOT EXISTS tracked_apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hidden_apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL UNIQUE
        );
    """)

    # Insert default settings if not present
    defaults = {
        "password_hash": bcrypt.hashpw(DEFAULT_PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "port": str(DEFAULT_PORT),
        "screenshot_interval": "300",
        "screenshot_retention_days": "30",
        "update_check_interval": "900",
        "schedule_enabled": "0",
        "limiter_enabled": "0",
        "parent_name": "Parent",
        "language": "en",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "tunnel_url": "",
    }
    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )

    # Insert default schedules if none exist (Mon-Fri 6-20, Sat-Sun 6-22)
    cursor.execute("SELECT COUNT(*) FROM schedules")
    if cursor.fetchone()[0] == 0:
        for day in range(5):  # Monday-Friday
            cursor.execute(
                "INSERT INTO schedules (day_of_week, start_time, end_time) VALUES (?, ?, ?)",
                (day, "06:00", "20:00")
            )
        for day in range(5, 7):  # Saturday-Sunday
            cursor.execute(
                "INSERT INTO schedules (day_of_week, start_time, end_time) VALUES (?, ?, ?)",
                (day, "06:00", "22:00")
            )

    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    conn.commit()
    conn.close()


def get_schedules():
    conn = get_db()
    rows = conn.execute("SELECT * FROM schedules ORDER BY day_of_week").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_schedule_for_day(day_of_week):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM schedules WHERE day_of_week = ?", (day_of_week,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_override_for_date(date_str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM schedule_overrides WHERE date = ?", (date_str,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_override(date_str, start_time, end_time):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO schedule_overrides (date, start_time, end_time) VALUES (?, ?, ?)",
        (date_str, start_time, end_time)
    )
    conn.commit()
    conn.close()


def update_schedule(day_of_week, start_time, end_time):
    conn = get_db()
    conn.execute(
        "UPDATE schedules SET start_time = ?, end_time = ? WHERE day_of_week = ?",
        (start_time, end_time, day_of_week)
    )
    conn.commit()
    conn.close()


def get_app_limits():
    conn = get_db()
    rows = conn.execute("SELECT * FROM app_limits ORDER BY process_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_app_limit(process_name):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM app_limits WHERE process_name = ?", (process_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_app_limit(process_name, daily_limit_minutes, action="warn"):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO app_limits (process_name, daily_limit_minutes, action) VALUES (?, ?, ?)",
        (process_name, daily_limit_minutes, action)
    )
    conn.commit()
    conn.close()


def delete_app_limit(process_name):
    conn = get_db()
    conn.execute("DELETE FROM app_limits WHERE process_name = ?", (process_name,))
    conn.commit()
    conn.close()


def log_usage(process_name, seconds):
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO usage_logs (date, process_name, seconds_used, last_updated)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date, process_name) DO UPDATE SET
            seconds_used = seconds_used + ?,
            last_updated = ?
    """, (today, process_name, seconds, now, seconds, now))
    conn.commit()
    conn.close()


def get_usage_for_date(date_str):
    conn = get_db()
    rows = conn.execute(
        "SELECT process_name, seconds_used FROM usage_logs WHERE date = ? ORDER BY seconds_used DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_usage_for_process_today(process_name):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    row = conn.execute(
        "SELECT seconds_used FROM usage_logs WHERE date = ? AND process_name = ?",
        (today, process_name)
    ).fetchone()
    conn.close()
    return row["seconds_used"] if row else 0


def get_usage_range(start_date, end_date):
    conn = get_db()
    rows = conn.execute(
        "SELECT date, process_name, seconds_used FROM usage_logs WHERE date BETWEEN ? AND ? ORDER BY date",
        (start_date, end_date)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tracked_apps():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tracked_apps ORDER BY display_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_tracked_app(process_name, display_name):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO tracked_apps (process_name, display_name) VALUES (?, ?)",
        (process_name, display_name)
    )
    conn.commit()
    conn.close()


def remove_tracked_app(process_name):
    conn = get_db()
    conn.execute("DELETE FROM tracked_apps WHERE process_name = ?", (process_name,))
    conn.commit()
    conn.close()


def get_hidden_apps():
    conn = get_db()
    rows = conn.execute("SELECT process_name FROM hidden_apps").fetchall()
    conn.close()
    return {r["process_name"] for r in rows}


def hide_app(process_name):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO hidden_apps (process_name) VALUES (?)",
        (process_name,)
    )
    conn.commit()
    conn.close()


def unhide_app(process_name):
    conn = get_db()
    conn.execute("DELETE FROM hidden_apps WHERE process_name = ?", (process_name,))
    conn.commit()
    conn.close()
