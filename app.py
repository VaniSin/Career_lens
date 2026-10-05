"""
Career Lens — Main Flask Application
Registers all blueprints and preserves original analyze/upload routes.
"""

import os
import re
import uuid

import fitz
from flask import Flask, render_template, request, jsonify, session

from ats_analyzer import analyze_resume
from database import init_db
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


# ─── Original routes (UNCHANGED) ──────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("resume")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify(error="Please upload a PDF resume."), 400
    try:
        with fitz.open(stream=f.read(), filetype="pdf") as pdf:
            text = "\n".join(p.get_text("text") for p in pdf)
        if not text.strip():
            return jsonify(error="No selectable text found. Please use a text-based PDF."), 400
        rid = str(uuid.uuid4())
        resume_cache[rid] = text
        session["resume_id"] = rid
        return jsonify(filename=f.filename, words=len(text.split()), characters=len(text))
    except Exception as e:
        return jsonify(error=f"Could not read this PDF: {e}"), 400


@app.route("/analyze/<feature>", methods=["POST"])
def analyze(feature):
    text = resume_cache.get(session.get("resume_id"))
    if not text:
        return jsonify(error="Please upload your resume again."), 400

    if feature == "ats":
        return jsonify(analyze_resume(text))

    if feature == "jobs":
        recommendations = analyze_target_roles_with_llm(text)
        return jsonify(recommendations=recommendations)

    if feature == "skills":
        role = ((request.json or {}).get("role") or "").strip()
        if not role:
            return jsonify(error="Please select a valid career."), 400
        report = analyze_role_skills_with_llm(text, role)
        return jsonify(report)

    if feature == "roadmap":
        role = ((request.json or {}).get("role") or "").strip()
        if not role:
            return jsonify(error="Please explore a career first."), 400

        roadmap = generate_learning_roadmap_with_llm(text, role)
        return jsonify(roadmap)

    return jsonify(error="Unknown feature."), 404


# ─── Dashboard data endpoint (new) ────────────────────────────────────────────

@app.route("/dashboard/summary", methods=["GET"])
def dashboard_summary():
    uid = session.get("user_id")
    if not uid:
        return jsonify(error="Authentication required."), 401

    from database import get_db, row_to_dict
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


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Career Lens on http://127.0.0.1:{port} (accessible via http://localhost:{port} or custom host)")
    app.run(debug=True, host=host, port=port)
