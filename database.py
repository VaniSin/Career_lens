"""
Career Lens — Database Layer
Production-grade SQLite with full schema for user data, resumes,
analysis results, roadmaps, interview sessions, and chat history.
"""

import sqlite3
import os

DB_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "careerlens.db")
)
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)


def get_db():
    """Return a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they do not exist + run safe migrations."""
    conn = get_db()
    c = conn.cursor()

    # ── Users ────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            email            TEXT    NOT NULL UNIQUE,
            password_hash    TEXT    NOT NULL,
            created_at       TEXT    DEFAULT (datetime('now')),
            updated_at       TEXT    DEFAULT (datetime('now')),
            bio              TEXT,
            location         TEXT,
            github_url       TEXT,
            linkedin_url     TEXT,
            phone            TEXT,
            job_title        TEXT,
            experience_years INTEGER DEFAULT 0,
            avatar_url       TEXT
        )
    """)

    # ── Resumes (persistent per-user uploads) ────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename     TEXT    NOT NULL,
            original_name TEXT   NOT NULL,
            file_size    INTEGER,
            word_count   INTEGER,
            char_count   INTEGER,
            raw_text     TEXT,
            uploaded_at  TEXT    DEFAULT (datetime('now')),
            is_active    INTEGER DEFAULT 1
        )
    """)

    # ── Documents (career portfolio uploads) ─────────────────────────────────
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

    # ── ATS Analysis results ─────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS ats_analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
            resume_id       INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
            score           INTEGER,
            rating          TEXT,
            word_count      INTEGER,
            found_sections  TEXT,
            missing_sections TEXT,
            matched_keywords TEXT,
            missing_keywords TEXT,
            suggestions      TEXT,
            breakdown_json   TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Target role / career analysis ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS role_analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
            resume_id       INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
            role            TEXT    NOT NULL,
            match_score     INTEGER,
            matched_skills  TEXT,
            missing_skills  TEXT,
            companies       TEXT,
            recommendations TEXT,
            result_json     TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Learning roadmaps ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS learning_roadmaps (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
            resume_id    INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
            target_role  TEXT    NOT NULL,
            roadmap_json TEXT    NOT NULL,
            created_at   TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Mock interview sessions ───────────────────────────────────────────────
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

    # ── Interview questions + answers ─────────────────────────────────────────
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

    # ── AI chatbot conversation history ───────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Safe migrations for existing databases ───────────────────────────────
    _safe_add_columns(c, "interview_questions", [
        ("is_pyq",       "INTEGER DEFAULT 0"),
        ("source_label", "TEXT DEFAULT 'AI-Generated Practice Question'"),
        ("source_note",  "TEXT"),
    ])
    _safe_add_columns(c, "users", [
        ("updated_at",   "TEXT DEFAULT (datetime('now'))"),
        ("avatar_url",   "TEXT"),
    ])

    conn.commit()
    conn.close()


def _safe_add_columns(cursor, table: str, columns: list[tuple]):
    """Add columns to an existing table without failing if they exist."""
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass  # Column already exists


def row_to_dict(row):
    """Convert a sqlite3.Row object to a plain dict."""
    if row is None:
        return None
    return dict(row)


# ── CRUD helpers ─────────────────────────────────────────────────────────────

def save_resume_to_db(user_id: int, filename: str, original_name: str,
                      file_size: int, word_count: int, char_count: int,
                      raw_text: str) -> int:
    """Persist a resume upload and return the new resume id."""
    conn = get_db()
    try:
        # Mark previous resumes as inactive
        conn.execute(
            "UPDATE resumes SET is_active = 0 WHERE user_id = ?", (user_id,)
        )
        cur = conn.execute(
            """INSERT INTO resumes
               (user_id, filename, original_name, file_size, word_count,
                char_count, raw_text, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (user_id, filename, original_name, file_size,
             word_count, char_count, raw_text)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_active_resume(user_id: int) -> dict | None:
    """Fetch the user's most recently active resume."""
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT * FROM resumes
               WHERE user_id = ? AND is_active = 1
               ORDER BY uploaded_at DESC LIMIT 1""",
            (user_id,)
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def save_ats_analysis(user_id, resume_id, result: dict):
    """Persist an ATS analysis result."""
    import json
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO ats_analyses
               (user_id, resume_id, score, rating, word_count,
                found_sections, missing_sections, matched_keywords,
                missing_keywords, suggestions, breakdown_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, resume_id,
                result.get("score"), result.get("rating"),
                result.get("word_count"),
                json.dumps(result.get("found_sections", [])),
                json.dumps(result.get("missing_sections", [])),
                json.dumps(result.get("matched_keywords", [])),
                json.dumps(result.get("missing_keywords", [])),
                json.dumps(result.get("suggestions", [])),
                json.dumps(result.get("breakdown", {})),
            )
        )
        conn.commit()
    finally:
        conn.close()


def save_role_analysis(user_id, resume_id, role: str, result: dict):
    """Persist a role/skills analysis."""
    import json
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO role_analyses
               (user_id, resume_id, role, match_score,
                matched_skills, missing_skills, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, resume_id, role,
                result.get("match_score") or result.get("score"),
                json.dumps(result.get("matched_skills", [])),
                json.dumps(result.get("missing_skills", [])),
                json.dumps(result),
            )
        )
        conn.commit()
    finally:
        conn.close()


def save_roadmap(user_id, resume_id, target_role: str, roadmap: dict):
    """Persist a learning roadmap."""
    import json
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO learning_roadmaps
               (user_id, resume_id, target_role, roadmap_json)
               VALUES (?, ?, ?, ?)""",
            (user_id, resume_id, target_role, json.dumps(roadmap))
        )
        conn.commit()
    finally:
        conn.close()


def get_user_history(user_id: int) -> dict:
    """Return a summary of all persisted data for a user."""
    import json
    conn = get_db()
    try:
        ats = [row_to_dict(r) for r in conn.execute(
            "SELECT id, score, rating, created_at FROM ats_analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        ).fetchall()]

        roles = [row_to_dict(r) for r in conn.execute(
            "SELECT id, role, match_score, created_at FROM role_analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        ).fetchall()]

        roadmaps = [row_to_dict(r) for r in conn.execute(
            "SELECT id, target_role, created_at FROM learning_roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        ).fetchall()]

        resumes = [row_to_dict(r) for r in conn.execute(
            "SELECT id, original_name, word_count, uploaded_at, is_active FROM resumes WHERE user_id = ? ORDER BY uploaded_at DESC LIMIT 5",
            (user_id,)
        ).fetchall()]

        return {
            "ats_analyses": ats,
            "role_analyses": roles,
            "roadmaps": roadmaps,
            "resumes": resumes,
        }
    finally:
        conn.close()
