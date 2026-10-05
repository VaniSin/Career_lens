"""
Career Lens — Authentication Blueprint
Handles user registration, login, logout, and profile management.
"""

from flask import Blueprint, request, jsonify, session
import hashlib, secrets, re
from database import get_db, row_to_dict

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(password: str, salt: str = None):
    """Hash a password with a random salt using SHA-256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(stored: str, provided: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt, _ = stored.split(":", 1)
        return stored == hash_password(provided, salt)
    except Exception:
        return False


def is_valid_gmail(email: str) -> bool:
    """Validate that the email address ends strictly with @gmail.com."""
    if not email:
        return False
    email = email.strip().lower()
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@gmail\.com$", email))


def current_user_id():
    return session.get("user_id")


def require_auth():
    """Returns (user_id, error_response) — error_response is None if authenticated."""
    uid = current_user_id()
    if not uid:
        return None, (jsonify(error="Authentication required."), 401)
    return uid, None


# ─── Routes ───────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name:
        return jsonify(error="Name is required."), 400
    if not is_valid_gmail(email):
        return jsonify(error="Invalid Gmail: Email must end strictly with @gmail.com (e.g. yourname@gmail.com)."), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return jsonify(error="An account with this email already exists."), 409

        ph = hash_password(password)
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, ph)
        )
        conn.commit()

        user = row_to_dict(conn.execute(
            "SELECT id, name, email FROM users WHERE email = ?", (email,)
        ).fetchone())

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        return jsonify(
            message="Account created successfully.",
            user={"id": user["id"], "name": user["name"], "email": user["email"]}
        ), 201

    except Exception as e:
        return jsonify(error=f"Registration failed: {e}"), 500
    finally:
        conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="Email and password are required."), 400

    if not is_valid_gmail(email):
        return jsonify(error="Invalid Gmail: Email must end with @gmail.com to sign in."), 400

    conn = get_db()
    try:
        user = row_to_dict(conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,)
        ).fetchone())

        if not user or not verify_password(user["password_hash"], password):
            return jsonify(error="Invalid email or password."), 401

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        return jsonify(
            message="Logged in successfully.",
            user={"id": user["id"], "name": user["name"], "email": user["email"]}
        )
    finally:
        conn.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(message="Logged out successfully.")


@auth_bp.route("/me", methods=["GET"])
def me():
    uid = current_user_id()
    if not uid:
        return jsonify(authenticated=False, user=None)

    conn = get_db()
    try:
        user = row_to_dict(conn.execute(
            """SELECT id, name, email, bio, location, github_url,
                      linkedin_url, phone, job_title, experience_years, created_at
               FROM users WHERE id = ?""",
            (uid,)
        ).fetchone())
        if not user:
            session.clear()
            return jsonify(authenticated=False, user=None)
        user.pop("password_hash", None)
        return jsonify(authenticated=True, user=user)
    finally:
        conn.close()


@auth_bp.route("/profile", methods=["PUT"])
def update_profile():
    uid, err = require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    allowed = ["name", "bio", "location", "github_url", "linkedin_url",
               "phone", "job_title", "experience_years"]

    updates = {k: v for k, v in data.items() if k in allowed and v is not None}

    if not updates:
        return jsonify(error="No valid fields to update."), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [uid]

    conn = get_db()
    try:
        conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            values
        )
        conn.commit()

        user = row_to_dict(conn.execute(
            """SELECT id, name, email, bio, location, github_url,
                      linkedin_url, phone, job_title, experience_years
               FROM users WHERE id = ?""",
            (uid,)
        ).fetchone())

        if "name" in updates:
            session["user_name"] = updates["name"]

        return jsonify(message="Profile updated successfully.", user=user)
    finally:
        conn.close()


@auth_bp.route("/password", methods=["PUT"])
def change_password():
    uid, err = require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""

    if len(new_pw) < 8:
        return jsonify(error="New password must be at least 8 characters."), 400

    conn = get_db()
    try:
        row = row_to_dict(conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (uid,)
        ).fetchone())

        if not row or not verify_password(row["password_hash"], current):
            return jsonify(error="Current password is incorrect."), 401

        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_pw), uid)
        )
        conn.commit()
        return jsonify(message="Password changed successfully.")
    finally:
        conn.close()
