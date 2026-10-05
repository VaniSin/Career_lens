"""
Career Lens — AI Chatbot Blueprint
Handles chat API and conversation history management.
"""

from flask import Blueprint, request, jsonify
from database import get_db, row_to_dict
from auth import require_auth
from ai_service import get_chatbot_response

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chat")

MAX_HISTORY = 50  # Messages to keep per user


@chatbot_bp.route("/message", methods=["POST"])
def send_message():
    uid, err = require_auth()
    if err:
        # Allow unauthenticated users with limited history
        uid = None

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify(error="Message cannot be empty."), 400

    if len(user_message) > 2000:
        return jsonify(error="Message is too long. Please keep it under 2000 characters."), 400

    history = []
    if uid:
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT role, content FROM chat_history
                   WHERE user_id = ? ORDER BY created_at DESC LIMIT 20""",
                (uid,)
            ).fetchall()
            history = [row_to_dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    # Get AI response
    try:
        bot_response = get_chatbot_response(user_message, history)
    except Exception as e:
        return jsonify(error=f"Could not generate response: {e}"), 500

    # Persist to database if user is authenticated
    if uid:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (?, 'user', ?)",
                (uid, user_message)
            )
            conn.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (?, 'assistant', ?)",
                (uid, bot_response)
            )
            # Trim old messages
            conn.execute(
                """DELETE FROM chat_history WHERE user_id = ? AND id NOT IN (
                       SELECT id FROM chat_history WHERE user_id = ?
                       ORDER BY created_at DESC LIMIT ?
                   )""",
                (uid, uid, MAX_HISTORY)
            )
            conn.commit()
        finally:
            conn.close()

    return jsonify(
        message=bot_response,
        authenticated=uid is not None
    )


@chatbot_bp.route("/history", methods=["GET"])
def get_history():
    uid, err = require_auth()
    if err:
        return err

    limit = min(100, int(request.args.get("limit", 50)))

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, role, content, created_at FROM chat_history
               WHERE user_id = ? ORDER BY created_at ASC LIMIT ?""",
            (uid, limit)
        ).fetchall()
        return jsonify(history=[row_to_dict(r) for r in rows])
    finally:
        conn.close()


@chatbot_bp.route("/history", methods=["DELETE"])
def clear_history():
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (uid,))
        conn.commit()
        return jsonify(message="Chat history cleared.")
    finally:
        conn.close()
