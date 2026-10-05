"""
Career Lens — Mock Interview Blueprint
Company-specific interview question generation, per-answer evaluation,
and final comprehensive interview performance review.
"""

import json
from flask import Blueprint, request, jsonify
from database import get_db, row_to_dict
from auth import require_auth
from ai_service import (
    generate_interview_questions,
    evaluate_interview_answer,
    generate_interview_summary,
)

interview_bp = Blueprint("interview", __name__, url_prefix="/interview")

AVAILABLE_ROLES = [
    "Data Analyst", "Data Scientist", "Machine Learning Engineer",
    "Business Analyst", "Python Developer", "Frontend Developer",
    "Database Developer", "Software Developer"
]

POPULAR_COMPANIES = [
    "Google", "Amazon", "Microsoft", "Meta", "Apple", "Netflix",
    "Infosys", "TCS", "Wipro", "Accenture", "Cognizant", "HCL",
    "Startup", "Other"
]


# ─── Routes ───────────────────────────────────────────────────────────────────

@interview_bp.route("/sessions", methods=["GET"])
def list_sessions():
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, company, role, created_at, status, score, notes
               FROM mock_interviews WHERE user_id = ?
               ORDER BY created_at DESC""",
            (uid,)
        ).fetchall()

        sessions = []
        for row in rows:
            s = row_to_dict(row)
            q_count = conn.execute(
                "SELECT COUNT(*) as n FROM interview_questions WHERE interview_id = ?",
                (s["id"],)
            ).fetchone()["n"]
            answered = conn.execute(
                """SELECT COUNT(*) as n FROM interview_questions
                   WHERE interview_id = ? AND answer IS NOT NULL AND answer != ''""",
                (s["id"],)
            ).fetchone()["n"]
            s["question_count"] = q_count
            s["answered_count"] = answered
            if s.get("notes"):
                try:
                    s["summary"] = json.loads(s["notes"])
                except Exception:
                    s["summary"] = None
            sessions.append(s)

        return jsonify(sessions=sessions, roles=AVAILABLE_ROLES, companies=POPULAR_COMPANIES)
    finally:
        conn.close()


@interview_bp.route("/sessions", methods=["POST"])
def create_session():
    uid, err = require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    company = (data.get("company") or "").strip()
    role = (data.get("role") or "").strip()
    question_count = min(20, max(3, int(data.get("count", 15))))

    if not company:
        return jsonify(error="Company name is required."), 400
    if not role:
        return jsonify(error="Job role is required."), 400

    # Generate questions via AI service (Groq LLM with PYQ distinction)
    questions = generate_interview_questions(company, role, question_count)

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO mock_interviews (user_id, company, role, status)
               VALUES (?, ?, ?, 'in_progress')""",
            (uid, company, role)
        )
        interview_id = cur.lastrowid

        for q in questions:
            conn.execute(
                """INSERT INTO interview_questions
                   (interview_id, question, category, order_num, is_pyq, source_label, source_note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    interview_id,
                    q["question"],
                    q.get("category", "Technical"),
                    q.get("order_num", 1),
                    1 if q.get("is_pyq") else 0,
                    q.get("source_label", "AI-Generated Practice Question"),
                    q.get("source_note", "")
                )
            )

        conn.commit()

        session_data = row_to_dict(conn.execute(
            "SELECT * FROM mock_interviews WHERE id = ?", (interview_id,)
        ).fetchone())

        saved_questions = [row_to_dict(r) for r in conn.execute(
            """SELECT id, question, category, answer, feedback, order_num, is_pyq, source_label, source_note
               FROM interview_questions WHERE interview_id = ?
               ORDER BY order_num ASC""",
            (interview_id,)
        ).fetchall()]

        return jsonify(
            message="Interview session created.",
            session=session_data,
            questions=saved_questions
        ), 201
    except Exception as e:
        return jsonify(error=f"Failed to create session: {e}"), 500
    finally:
        conn.close()


@interview_bp.route("/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id):
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        session_row = row_to_dict(conn.execute(
            "SELECT * FROM mock_interviews WHERE id = ? AND user_id = ?",
            (session_id, uid)
        ).fetchone())

        if not session_row:
            return jsonify(error="Interview session not found."), 404

        questions = [row_to_dict(r) for r in conn.execute(
            """SELECT id, question, category, answer, feedback, order_num, answered_at,
                      is_pyq, source_label, source_note
               FROM interview_questions WHERE interview_id = ?
               ORDER BY order_num ASC""",
            (session_id,)
        ).fetchall()]

        # Parse feedback if stored as JSON
        for q in questions:
            if q.get("feedback"):
                try:
                    q["feedback_detail"] = json.loads(q["feedback"])
                except Exception:
                    q["feedback_detail"] = None

        summary = None
        if session_row.get("notes"):
            try:
                summary = json.loads(session_row["notes"])
            except Exception:
                summary = None

        return jsonify(session=session_row, questions=questions, summary=summary)
    finally:
        conn.close()


@interview_bp.route("/sessions/<int:session_id>/answer", methods=["POST"])
def submit_answer(session_id):
    uid, err = require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    answer = (data.get("answer") or "").strip()

    if not question_id:
        return jsonify(error="question_id is required."), 400

    conn = get_db()
    try:
        # Verify ownership
        session_row = conn.execute(
            "SELECT * FROM mock_interviews WHERE id = ? AND user_id = ?",
            (session_id, uid)
        ).fetchone()
        if not session_row:
            return jsonify(error="Session not found."), 404

        q = row_to_dict(conn.execute(
            "SELECT * FROM interview_questions WHERE id = ? AND interview_id = ?",
            (question_id, session_id)
        ).fetchone())
        if not q:
            return jsonify(error="Question not found."), 404

        # Detailed evaluation via Groq LLM
        eval_result = evaluate_interview_answer(
            question=q["question"],
            category=q.get("category", "Technical"),
            company=session_row["company"],
            role=session_row["role"],
            answer=answer,
            source_label=q.get("source_label", "")
        )

        feedback_json = json.dumps(eval_result)
        formatted_feedback = eval_result.get("formatted") or "Answer evaluated."

        conn.execute(
            """UPDATE interview_questions
               SET answer = ?, feedback = ?, answered_at = datetime('now')
               WHERE id = ?""",
            (answer, feedback_json, question_id)
        )

        # Check if all questions are now answered
        total = conn.execute(
            "SELECT COUNT(*) as n FROM interview_questions WHERE interview_id = ?",
            (session_id,)
        ).fetchone()["n"]
        answered = conn.execute(
            """SELECT COUNT(*) as n FROM interview_questions
               WHERE interview_id = ? AND answer IS NOT NULL AND answer != ''""",
            (session_id,)
        ).fetchone()["n"]

        is_completed = answered >= total
        summary = None

        if is_completed:
            # Generate final evaluation summary with overall score, strengths, weaknesses & tips
            all_questions = [row_to_dict(r) for r in conn.execute(
                """SELECT question, category, answer, feedback, order_num
                   FROM interview_questions WHERE interview_id = ?
                   ORDER BY order_num ASC""",
                (session_id,)
            ).fetchall()]

            summary = generate_interview_summary(
                company=session_row["company"],
                role=session_row["role"],
                qa_pairs=all_questions
            )
            overall_score = int(summary.get("overall_score", 75))

            conn.execute(
                """UPDATE mock_interviews
                   SET status = 'completed', score = ?, notes = ?
                   WHERE id = ?""",
                (overall_score, json.dumps(summary), session_id)
            )

        conn.commit()

        return jsonify(
            message="Answer evaluated.",
            feedback=formatted_feedback,
            feedback_detail=eval_result,
            progress={"answered": answered, "total": total},
            completed=is_completed,
            summary=summary
        )
    finally:
        conn.close()


@interview_bp.route("/sessions/<int:session_id>/summary", methods=["GET"])
def get_session_summary(session_id):
    """Retrieve or compute the overall interview evaluation summary."""
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        session_row = row_to_dict(conn.execute(
            "SELECT * FROM mock_interviews WHERE id = ? AND user_id = ?",
            (session_id, uid)
        ).fetchone())
        if not session_row:
            return jsonify(error="Session not found."), 404

        if session_row.get("notes"):
            try:
                summary = json.loads(session_row["notes"])
                return jsonify(summary=summary, score=session_row.get("score"))
            except Exception:
                pass

        # If not already computed, compute it now
        all_questions = [row_to_dict(r) for r in conn.execute(
            """SELECT question, category, answer, feedback, order_num
               FROM interview_questions WHERE interview_id = ?
               ORDER BY order_num ASC""",
            (session_id,)
        ).fetchall()]

        summary = generate_interview_summary(
            company=session_row["company"],
            role=session_row["role"],
            qa_pairs=all_questions
        )
        overall_score = int(summary.get("overall_score", 75))

        conn.execute(
            "UPDATE mock_interviews SET score = ?, notes = ? WHERE id = ?",
            (overall_score, json.dumps(summary), session_id)
        )
        conn.commit()

        return jsonify(summary=summary, score=overall_score)
    finally:
        conn.close()


@interview_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM mock_interviews WHERE id = ? AND user_id = ?",
            (session_id, uid)
        ).fetchone()
        if not row:
            return jsonify(error="Session not found."), 404

        conn.execute("DELETE FROM mock_interviews WHERE id = ?", (session_id,))
        conn.commit()
        return jsonify(message="Session deleted.")
    finally:
        conn.close()


@interview_bp.route("/roles", methods=["GET"])
def get_roles():
    return jsonify(roles=AVAILABLE_ROLES, companies=POPULAR_COMPANIES)
