"""
Career Lens — Database Layer
Handles SQLite connection and schema initialization.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "careerlens.db")


def get_db():
    """Return a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they do not exist."""
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            password_hash TEXT  NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now')),
            bio         TEXT,
            location    TEXT,
            github_url  TEXT,
            linkedin_url TEXT,
            phone       TEXT,
            job_title   TEXT,
            experience_years INTEGER DEFAULT 0
        )
    """)

    # Documents table (career portfolio)
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            category    TEXT    NOT NULL DEFAULT 'Other',
            filename    TEXT    NOT NULL,
            file_size   INTEGER,
            file_type   TEXT,
            description TEXT,
            uploaded_at TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Mock interview sessions
    c.execute("""
        CREATE TABLE IF NOT EXISTS mock_interviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company     TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now')),
            status      TEXT    DEFAULT 'in_progress',
            score       INTEGER,
            notes       TEXT
        )
    """)

    # Individual interview questions + answers
    c.execute("""
        CREATE TABLE IF NOT EXISTS interview_questions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL REFERENCES mock_interviews(id) ON DELETE CASCADE,
            question     TEXT    NOT NULL,
            category     TEXT    NOT NULL DEFAULT 'General',
            answer       TEXT,
            feedback     TEXT,
            order_num    INTEGER DEFAULT 0,
            answered_at  TEXT,
            is_pyq       INTEGER DEFAULT 0,
            source_label TEXT    DEFAULT 'AI-Generated Practice Question',
            source_note  TEXT
        )
    """)

    # Safe migrations for existing databases
    for col_name, col_type in [
        ("is_pyq", "INTEGER DEFAULT 0"),
        ("source_label", "TEXT DEFAULT 'AI-Generated Practice Question'"),
        ("source_note", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE interview_questions ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    # AI chatbot conversation history
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


def row_to_dict(row):
    """Convert a sqlite3.Row object to a plain dict."""
    if row is None:
        return None
    return dict(row)
