import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "jobs.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                region TEXT,
                salary_from INTEGER,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS seen_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                job_id TEXT NOT NULL,
                seen_at TEXT DEFAULT (datetime('now')),
                UNIQUE(subscription_id, job_id)
            );
        """)
        self.conn.commit()

    def add_user(self, user_id: int, username: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
            (user_id, username)
        )
        self.conn.commit()

    def add_subscription(self, user_id, source, query, region, salary_from):
        cur = self.conn.execute(
            """INSERT INTO subscriptions (user_id, source, query, region, salary_from)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, source, query, region, salary_from)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_subscriptions(self, user_id=None):
        if user_id:
            rows = self.conn.execute(
                "SELECT * FROM subscriptions WHERE user_id=? AND active=1", (user_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM subscriptions WHERE active=1"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_subscription(self, sub_id, user_id):
        self.conn.execute(
            "UPDATE subscriptions SET active=0 WHERE id=? AND user_id=?",
            (sub_id, user_id)
        )
        self.conn.commit()

    def is_job_seen(self, sub_id, job_id):
        row = self.conn.execute(
            "SELECT 1 FROM seen_jobs WHERE subscription_id=? AND job_id=?",
            (sub_id, str(job_id))
        ).fetchone()
        return row is not None

    def mark_job_seen(self, sub_id, job_id):
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO seen_jobs (subscription_id, job_id) VALUES (?, ?)",
                (sub_id, str(job_id))
            )
            self.conn.commit()
        except Exception:
            pass

    def cleanup_old_seen(self, days=7):
        """Remove seen_jobs older than N days to keep DB small."""
        self.conn.execute(
            "DELETE FROM seen_jobs WHERE seen_at < datetime('now', ?)",
            (f"-{days} days",)
        )
        self.conn.commit()
