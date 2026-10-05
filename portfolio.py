"""
Career Lens — Career Portfolio Blueprint
Handles secure document upload, listing, download, and deletion.
"""

import os, uuid, mimetypes
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
from database import get_db, row_to_dict
from auth import require_auth

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/portfolio")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "png", "jpg", "jpeg", "txt"
}

DOCUMENT_CATEGORIES = [
    "Resume/CV",
    "Certificate",
    "Internship Certificate",
    "Experience Letter",
    "Degree/Marksheet",
    "Project",
    "Other"
]


def allowed_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS


def get_upload_path(user_id: int) -> str:
    """Return (and create) a user-specific upload directory."""
    path = os.path.join(UPLOAD_FOLDER, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


# ─── Routes ───────────────────────────────────────────────────────────────────

@portfolio_bp.route("/documents", methods=["GET"])
def list_documents():
    uid, err = require_auth()
    if err:
        return err

    category = request.args.get("category")
    conn = get_db()
    try:
        if category and category != "All":
            rows = conn.execute(
                """SELECT id, name, category, filename, file_size, file_type,
                          description, uploaded_at
                   FROM documents WHERE user_id = ? AND category = ?
                   ORDER BY uploaded_at DESC""",
                (uid, category)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, name, category, filename, file_size, file_type,
                          description, uploaded_at
                   FROM documents WHERE user_id = ?
                   ORDER BY uploaded_at DESC""",
                (uid,)
            ).fetchall()

        docs = [row_to_dict(r) for r in rows]
        return jsonify(documents=docs, categories=DOCUMENT_CATEGORIES)
    finally:
        conn.close()


@portfolio_bp.route("/documents", methods=["POST"])
def upload_document():
    uid, err = require_auth()
    if err:
        return err

    f = request.files.get("file")
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "Other").strip()
    description = (request.form.get("description") or "").strip()

    if not f or not f.filename:
        return jsonify(error="Please select a file to upload."), 400

    if not allowed_file(f.filename):
        ext_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return jsonify(error=f"Unsupported file type. Allowed: {ext_list}"), 400

    if category not in DOCUMENT_CATEGORIES:
        category = "Other"

    if not name:
        name = os.path.splitext(secure_filename(f.filename))[0].replace("_", " ")

    # Read file data and check size
    file_data = f.read()
    if len(file_data) > MAX_FILE_SIZE:
        return jsonify(error="File is too large. Maximum size is 10 MB."), 400

    # Save with a UUID filename to prevent collisions/path traversal
    ext = f.filename.rsplit(".", 1)[-1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    save_dir = get_upload_path(uid)
    save_path = os.path.join(save_dir, safe_name)

    with open(save_path, "wb") as out:
        out.write(file_data)

    file_type = mimetypes.guess_type(f.filename)[0] or "application/octet-stream"

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO documents
               (user_id, name, category, filename, file_size, file_type, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid, name, category, safe_name, len(file_data), file_type, description)
        )
        conn.commit()

        doc = row_to_dict(conn.execute(
            """SELECT id, name, category, filename, file_size, file_type,
                      description, uploaded_at
               FROM documents WHERE user_id = ? ORDER BY id DESC LIMIT 1""",
            (uid,)
        ).fetchone())

        return jsonify(message="Document uploaded successfully.", document=doc), 201
    except Exception as e:
        # Clean up file if DB insert failed
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify(error=f"Upload failed: {e}"), 500
    finally:
        conn.close()


@portfolio_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        doc = row_to_dict(conn.execute(
            "SELECT filename FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, uid)
        ).fetchone())

        if not doc:
            return jsonify(error="Document not found."), 404

        # Delete physical file
        file_path = os.path.join(get_upload_path(uid), doc["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)

        conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, uid))
        conn.commit()
        return jsonify(message="Document deleted successfully.")
    finally:
        conn.close()


@portfolio_bp.route("/documents/<int:doc_id>/download", methods=["GET"])
def download_document(doc_id):
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        doc = row_to_dict(conn.execute(
            "SELECT name, filename FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, uid)
        ).fetchone())

        if not doc:
            return jsonify(error="Document not found."), 404

        upload_dir = get_upload_path(uid)
        ext = doc["filename"].rsplit(".", 1)[-1]
        download_name = f"{secure_filename(doc['name'])}.{ext}"

        return send_from_directory(
            upload_dir,
            doc["filename"],
            as_attachment=True,
            download_name=download_name
        )
    finally:
        conn.close()


@portfolio_bp.route("/stats", methods=["GET"])
def portfolio_stats():
    uid, err = require_auth()
    if err:
        return err

    conn = get_db()
    try:
        total = conn.execute(
            "SELECT COUNT(*) as n FROM documents WHERE user_id = ?", (uid,)
        ).fetchone()["n"]

        by_cat = conn.execute(
            """SELECT category, COUNT(*) as n
               FROM documents WHERE user_id = ?
               GROUP BY category ORDER BY n DESC""",
            (uid,)
        ).fetchall()

        return jsonify(
            total=total,
            by_category=[row_to_dict(r) for r in by_cat]
        )
    finally:
        conn.close()
