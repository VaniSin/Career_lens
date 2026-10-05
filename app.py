"""
Career Lens — Main Flask Application
Registers all blueprints and preserves original analyze/upload routes.
Adds SEO endpoints (robots.txt, sitemap.xml) and DB persistence for analyses.
"""

import os
import re
import uuid
import json
from datetime import datetime

import fitz
from flask import (
    Flask, render_template, request, jsonify,
    session, Response, send_from_directory
)

from ats_analyzer import analyze_resume
from database import (
    init_db, save_resume_to_db, get_active_resume,
    save_ats_analysis, save_role_analysis, save_roadmap,
    get_user_history, get_db, row_to_dict
)
from auth import auth_bp
from portfolio import portfolio_bp
from interview import interview_bp
from chatbot import chatbot_bp
from ai_service import (
    analyze_target_roles_with_llm,
    analyze_role_skills_with_llm,
    generate_learning_roadmap_with_llm,
)

# ─── App setup ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-replace-in-production")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16 MB global limit

# Site configuration for SEO
SITE_URL  = os.getenv("SITE_URL", "http://careerlens")
SITE_NAME = "CareerLens"

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(portfolio_bp)
app.register_blueprint(interview_bp)
app.register_blueprint(chatbot_bp)

# In-memory resume cache (per session, as in original)
resume_cache: dict[str, str] = {}

# ─── Career role definitions (UNCHANGED from original) ────────────────────────

CAREER_ROLES = {
    "Data Analyst": {
        "skills": ["sql", "excel", "python", "statistics", "power bi",
                   "tableau", "data visualization"],
        "description": "Analyze data, identify trends and create reports or dashboards.",
        "education": ["data science", "computer science", "statistics",
                      "mathematics", "business"]
    },
    "Data Scientist": {
        "skills": ["python", "sql", "statistics", "machine learning",
                   "pandas", "numpy", "data visualization", "scikit-learn"],
        "description": "Use statistics and machine learning to solve data-driven problems.",
        "education": ["data science", "computer science", "mathematics", "statistics"]
    },
    "Machine Learning Engineer": {
        "skills": ["python", "machine learning", "deep learning",
                   "tensorflow", "pytorch", "sql", "scikit-learn",
                   "data structures"],
        "description": "Build, train and deploy machine learning models.",
        "education": ["computer science", "data science", "artificial intelligence"]
    },
    "Business Analyst": {
        "skills": ["excel", "sql", "power bi", "tableau", "statistics",
                   "communication", "business analysis", "problem solving"],
        "description": "Connect business needs with data-driven insights and solutions.",
        "education": ["business", "computer science", "data science",
                      "management", "economics"]
    },
    "Python Developer": {
        "skills": ["python", "flask", "django", "sql", "git",
                   "rest api", "data structures", "javascript"],
        "description": "Develop applications, APIs and backend services using Python.",
        "education": ["computer science", "information technology",
                      "software engineering", "data science"]
    },
    "Frontend Developer": {
        "skills": ["html", "css", "javascript", "react", "responsive design",
                   "git", "ui", "ux"],
        "description": "Build interactive and user-friendly web interfaces.",
        "education": ["computer science", "information technology", "software engineering"]
    },
    "Database Developer": {
        "skills": ["sql", "mysql", "oracle", "mongodb", "database",
                   "plsql", "database design", "python"],
        "description": "Design, develop and maintain databases and data systems.",
        "education": ["computer science", "information technology", "data science"]
    },
    "Software Developer": {
        "skills": ["python", "java", "c++", "sql", "data structures",
                   "algorithms", "git", "software development"],
        "description": "Design, develop, test and maintain software applications.",
        "education": ["computer science", "information technology", "software engineering"]
    }
}

# ─── Original helper functions (UNCHANGED) ────────────────────────────────────

def analyze_ats_readiness(text):
    report = analyze_resume(text)
    checks = []
    for name, item in report["breakdown"].items():
        score = item["score"]
        maximum = item["max"]
        status = "pass" if score >= maximum * 0.7 else "review"
        checks.append({
            "name": name,
            "status": status,
            "detail": f"Score: {score}/{maximum}"
        })
    return {
        "score": report["score"],
        "label": report["rating"],
        "checks": checks,
        "detected_sections": report["found_sections"],
        "missing_sections": report["missing_sections"],
        "matched_keywords": report["matched_keywords"],
        "missing_keywords": report["missing_keywords"],
        "word_count": report["word_count"],
        "suggestions": report["suggestions"],
        "breakdown": report["breakdown"]
    }


def terms(text):
    stop = {
        "the", "and", "for", "with", "from", "that", "this",
        "you", "your", "are", "will", "have", "has", "our",
        "their", "they", "job", "role", "work", "working",
        "experience", "skills", "skill", "years", "year",
        "required", "preferred", "using"
    }
    return {
        w.strip(".-")
        for w in re.findall(r"[a-zA-Z][a-zA-Z+#.-]{2,}", text.lower())
        if w not in stop
    }


def recommend_careers(resume_text):
    resume_lower = resume_text.lower()
    recommendations = []

    for role, info in CAREER_ROLES.items():
        matched_skills = [
            skill for skill in info["skills"]
            if re.search(
                r"(?<![a-z0-9+#])" + re.escape(skill) + r"(?![a-z0-9+#])",
                resume_lower
            )
        ]
        missing_skills = [
            skill for skill in info["skills"]
            if skill not in matched_skills
        ]
        score = round(len(matched_skills) / len(info["skills"]) * 100)

        if matched_skills:
            recommendations.append({
                "role": role,
                "score": score,
                "description": info["description"],
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "reason": (
                    f"Your resume includes {len(matched_skills)} "
                    f"of the {len(info['skills'])} listed skills "
                    f"for this role."
                )
            })

    recommendations.sort(key=lambda item: item["score"], reverse=True)
    return recommendations[:5]


def analyze_career_skills(resume_text, role):
    info = CAREER_ROLES[role]
    resume_lower = resume_text.lower()

    matched = [
        skill for skill in info["skills"]
        if re.search(
            r"(?<![a-z0-9+#])" + re.escape(skill) + r"(?![a-z0-9+#])",
            resume_lower
        )
    ]
    missing = [skill for skill in info["skills"] if skill not in matched]

    prioritized = []
    for index, skill in enumerate(missing):
        if index < 2:
            priority = "High"
            reason = "Start with this skill in your learning sequence."
        elif index < 4:
            priority = "Medium"
            reason = "Build this skill after your initial priorities."
        else:
            priority = "Later"
            reason = "Add this skill after building the earlier skills."
        prioritized.append({"skill": skill, "priority": priority, "reason": reason})

    return {
        "role": role,
        "description": info["description"],
        "matched_skills": matched,
        "missing_skills": missing,
        "prioritized_skills": prioritized
    }


# ─── SEO Routes ───────────────────────────────────────────────────────────────

@app.route("/robots.txt")
def robots_txt():
    content = f"""User-agent: *
Allow: /
Disallow: /auth/
Disallow: /dashboard/
Disallow: /uploads/
Disallow: /portfolio/
Disallow: /interview/
Disallow: /chatbot/

Sitemap: {SITE_URL}/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    pages = [
        {"loc": SITE_URL + "/",             "priority": "1.0", "changefreq": "weekly"},
        {"loc": SITE_URL + "/#features",    "priority": "0.8", "changefreq": "monthly"},
        {"loc": SITE_URL + "/#how",         "priority": "0.7", "changefreq": "monthly"},
        {"loc": SITE_URL + "/#resume",      "priority": "0.9", "changefreq": "weekly"},
    ]
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for page in pages:
        xml_parts.append(f"""  <url>
    <loc>{page['loc']}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{page['changefreq']}</changefreq>
    <priority>{page['priority']}</priority>
  </url>""")
    xml_parts.append("</urlset>")
    return Response("\n".join(xml_parts), mimetype="application/xml")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.png",
        mimetype="image/png"
    )


# ─── Original routes (UNCHANGED core logic, now with DB persistence) ──────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("resume")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify(error="Please upload a PDF resume."), 400
    try:
        file_bytes = f.read()
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            text = "\n".join(p.get_text("text") for p in pdf)
        if not text.strip():
            return jsonify(error="No selectable text found. Please use a text-based PDF."), 400

        rid = str(uuid.uuid4())
        resume_cache[rid] = text
        session["resume_id"] = rid

        word_count  = len(text.split())
        char_count  = len(text)
        file_size   = len(file_bytes)
        original_nm = f.filename

        # Persist resume to DB if user is logged in
        resume_db_id = None
        uid = session.get("user_id")
        if uid:
            resume_db_id = save_resume_to_db(
                user_id=uid,
                filename=rid + ".pdf",
                original_name=original_nm,
                file_size=file_size,
                word_count=word_count,
                char_count=char_count,
                raw_text=text,
            )
            session["resume_db_id"] = resume_db_id

        return jsonify(
            filename=original_nm,
            words=word_count,
            characters=char_count,
            resume_db_id=resume_db_id
        )
    except Exception as e:
        return jsonify(error=f"Could not read this PDF: {e}"), 400


@app.route("/analyze/<feature>", methods=["POST"])
def analyze(feature):
    text = resume_cache.get(session.get("resume_id"))
    if not text:
        # Try to reload from DB if user is logged in
        uid = session.get("user_id")
        if uid:
            resume_row = get_active_resume(uid)
            if resume_row and resume_row.get("raw_text"):
                text = resume_row["raw_text"]
                rid = str(uuid.uuid4())
                resume_cache[rid] = text
                session["resume_id"] = rid
                session["resume_db_id"] = resume_row["id"]

    if not text:
        return jsonify(error="Please upload your resume again."), 400

    uid          = session.get("user_id")
    resume_db_id = session.get("resume_db_id")

    if feature == "ats":
        result = analyze_resume(text)
        # Persist if logged in
        if uid:
            try:
                save_ats_analysis(uid, resume_db_id, result)
            except Exception:
                pass
        return jsonify(result)

    if feature == "jobs":
        recommendations = analyze_target_roles_with_llm(text)
        return jsonify(recommendations=recommendations)

    if feature == "skills":
        role = ((request.json or {}).get("role") or "").strip()
        if not role:
            return jsonify(error="Please select a valid career."), 400
        report = analyze_role_skills_with_llm(text, role)
        # Persist if logged in
        if uid:
            try:
                save_role_analysis(uid, resume_db_id, role, report)
            except Exception:
                pass
        return jsonify(report)

    if feature == "roadmap":
        role = ((request.json or {}).get("role") or "").strip()
        if not role:
            return jsonify(error="Please explore a career first."), 400
        roadmap = generate_learning_roadmap_with_llm(text, role)
        # Persist if logged in
        if uid:
            try:
                save_roadmap(uid, resume_db_id, role, roadmap)
            except Exception:
                pass
        return jsonify(roadmap)

    return jsonify(error="Unknown feature."), 404


# ─── Dashboard data endpoint ──────────────────────────────────────────────────

@app.route("/dashboard/summary", methods=["GET"])
def dashboard_summary():
    uid = session.get("user_id")
    if not uid:
        return jsonify(error="Authentication required."), 401

    conn = get_db()
    try:
        doc_count = conn.execute(
            "SELECT COUNT(*) as n FROM documents WHERE user_id = ?", (uid,)
        ).fetchone()["n"]

        interview_count = conn.execute(
            "SELECT COUNT(*) as n FROM mock_interviews WHERE user_id = ?", (uid,)
        ).fetchone()["n"]

        completed_interviews = conn.execute(
            "SELECT COUNT(*) as n FROM mock_interviews WHERE user_id = ? AND status = 'completed'",
            (uid,)
        ).fetchone()["n"]

        recent_docs = [row_to_dict(r) for r in conn.execute(
            """SELECT id, name, category, uploaded_at
               FROM documents WHERE user_id = ?
               ORDER BY uploaded_at DESC LIMIT 3""",
            (uid,)
        ).fetchall()]

        recent_interviews = [row_to_dict(r) for r in conn.execute(
            """SELECT id, company, role, created_at, status
               FROM mock_interviews WHERE user_id = ?
               ORDER BY created_at DESC LIMIT 3""",
            (uid,)
        ).fetchall()]

        return jsonify(
            documents=doc_count,
            interviews=interview_count,
            completed_interviews=completed_interviews,
            recent_documents=recent_docs,
            recent_interviews=recent_interviews
        )
    finally:
        conn.close()


@app.route("/dashboard/history", methods=["GET"])
def dashboard_history():
    """Return user's full analysis history (ATS, roles, roadmaps, resumes)."""
    uid = session.get("user_id")
    if not uid:
        return jsonify(error="Authentication required."), 401
    try:
        history = get_user_history(uid)
        return jsonify(history)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/dashboard/resume", methods=["GET"])
def get_stored_resume():
    """Return metadata of the user's most recently active resume."""
    uid = session.get("user_id")
    if not uid:
        return jsonify(error="Authentication required."), 401
    resume = get_active_resume(uid)
    if not resume:
        return jsonify(resume=None)
    # Never expose raw_text over the wire
    resume.pop("raw_text", None)
    return jsonify(resume=resume)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Career Lens on http://127.0.0.1:{port} (accessible via http://localhost:{port} or custom host)")
    app.run(debug=True, host=host, port=port)
