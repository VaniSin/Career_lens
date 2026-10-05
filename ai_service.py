"""
Career Lens — AI Service Layer
Abstraction over AI/LLM providers (Groq, OpenAI, Google Gemini).
Provides:
1. Target Role Alignment (analyzing resume against real-world roles & recommending companies)
2. Actionable Learning Roadmap (prioritized week-by-week learning plan based on resume gaps)
3. Company-Based Mock Interview (generating company questions, PYQs vs practice, per-answer evaluation, overall performance summary)
4. Career Chatbot multi-turn consultation
"""

import os
import re
import json
import random
from pathlib import Path

# Load .env file automatically if present
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

# ==============================================================================
# 🔑 API KEY CONFIGURATION (GROQ, CHATGPT, GEMINI)
# ==============================================================================
# Groq API Key (starts with gsk_...):
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# OpenAI API Key (starts with sk-...):
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Google Gemini API Key (starts with AIza...):
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Unified key (auto-detected):
AI_API_KEY = os.getenv("AI_API_KEY", "")
# ==============================================================================


def get_active_ai_config():
    """Detect active AI provider, key, and model (Groq preferred)."""
    # 1. Direct Groq key
    groq_key = (os.getenv("GROQ_API_KEY") or GROQ_API_KEY or "").strip()
    if groq_key:
        return "groq", groq_key, os.getenv("GROQ_MODEL", GROQ_MODEL)

    # 2. Check unified AI_API_KEY
    unified = (os.getenv("AI_API_KEY") or AI_API_KEY or "").strip()
    if unified:
        if unified.startswith("gsk_"):
            return "groq", unified, os.getenv("GROQ_MODEL", GROQ_MODEL)
        if unified.startswith("AIza"):
            return "gemini", unified, os.getenv("GEMINI_MODEL", GEMINI_MODEL)
        return "openai", unified, os.getenv("OPENAI_MODEL", OPENAI_MODEL)

    # 3. Check OPENAI_API_KEY (might contain Groq gsk_ key if user pasted it there)
    openai_key = (os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY or "").strip()
    if openai_key:
        if openai_key.startswith("gsk_"):
            return "groq", openai_key, os.getenv("GROQ_MODEL", GROQ_MODEL)
        return "openai", openai_key, os.getenv("OPENAI_MODEL", OPENAI_MODEL)

    # 4. Check explicit Gemini key
    gemini_key = (os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or "").strip()
    if gemini_key:
        return "gemini", gemini_key, os.getenv("GEMINI_MODEL", GEMINI_MODEL)

    return "rule_based", "", ""


# ──────────────────────────────────────────────────────────────────────────────
# Core Career Roles (Deterministic Fallback)
# ──────────────────────────────────────────────────────────────────────────────

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

COMPANY_PROFILES = {
    "google": {
        "known_for": ["algorithms", "system design", "culture fit", "data structures"],
        "hr_style": "Behavioral + culture fit with 'Googleyness' focus",
        "tech_style": "Heavy algorithms, coding, system design at scale"
    },
    "amazon": {
        "known_for": ["leadership principles", "customer obsession", "ownership"],
        "hr_style": "Star-method behavioral questions tied to 14 Leadership Principles",
        "tech_style": "Coding + system design; LP integration throughout"
    },
    "microsoft": {
        "known_for": ["problem solving", "growth mindset", "product thinking"],
        "hr_style": "Culture-add, collaboration, growth mindset",
        "tech_style": "Coding, system design, product questions"
    },
    "meta": {
        "known_for": ["coding", "system design", "data structures", "scale"],
        "hr_style": "Behavioral + collaboration + moving fast",
        "tech_style": "Pure coding + large-scale system design"
    },
    "startup": {
        "known_for": ["ownership", "adaptability", "breadth", "scrappiness"],
        "hr_style": "Culture, motivation, risk tolerance",
        "tech_style": "Full-stack breadth, ownership, practical problem solving"
    }
}

ROLE_TECH_QUESTIONS = {
    "Data Analyst": [
        "Walk me through how you would clean a dataset with 20% missing values.",
        "Explain the difference between a left join and an inner join with a real example.",
        "How would you use SQL window functions? Give a practical use case.",
        "Describe a dashboard you built. What metrics did you track and why?",
        "How do you decide between using Excel, SQL, or Python for analysis?",
        "Given a sales dataset, how would you identify top-performing regions?",
        "What is the difference between OLAP and OLTP? When would you use each?",
        "How do you validate the accuracy of your analysis before presenting results?",
    ],
    "Data Scientist": [
        "Explain the bias-variance tradeoff in plain language.",
        "How would you handle a dataset where the target class is 1% of the total?",
        "Walk me through how you would build a churn prediction model from scratch.",
        "What is cross-validation and why is it important?",
        "How do you explain a complex model's predictions to non-technical stakeholders?",
        "What is regularization? Compare L1 and L2.",
        "How would you detect and handle outliers in a regression model?",
        "Describe a time your model failed in production. What did you do?",
    ],
    "Machine Learning Engineer": [
        "Explain the difference between batch and online learning.",
        "How do you deploy a machine learning model to production?",
        "What is feature engineering? Give three examples you have done.",
        "How would you monitor a model in production for data drift?",
        "Explain how gradient boosting works at a high level.",
        "What is the difference between precision and recall? When does each matter?",
        "How do you handle model versioning and rollback in a production system?",
        "Design an ML pipeline for a recommendation system.",
    ],
    "Python Developer": [
        "What is the difference between a list and a tuple? When would you use each?",
        "Explain Python's GIL and how it affects multithreading.",
        "How do you design a RESTful API in Flask or FastAPI?",
        "What are Python decorators? Write a simple example.",
        "Explain the difference between synchronous and asynchronous Python.",
        "How would you optimize a Python function that is running too slowly?",
        "What is the difference between `is` and `==` in Python?",
        "How do you write unit tests in Python? What libraries do you prefer?",
    ],
    "Frontend Developer": [
        "Explain the difference between `==` and `===` in JavaScript.",
        "What is the virtual DOM and why does React use it?",
        "How do you optimize a web page for performance?",
        "Explain CSS specificity and how it affects styling.",
        "What is the difference between `null` and `undefined`?",
        "How do you handle asynchronous operations in JavaScript?",
        "What are CSS Grid and Flexbox? When would you use each?",
        "How do you approach cross-browser compatibility?",
    ],
    "Software Developer": [
        "Explain SOLID principles with a short example for each.",
        "What is the difference between SQL and NoSQL? When would you use each?",
        "How do you approach debugging a bug you cannot reproduce locally?",
        "Explain the concept of technical debt. How do you manage it?",
        "What design patterns have you used? Give a concrete example.",
        "How do you ensure your code is maintainable?",
        "Describe your code review process.",
        "What is CI/CD and how have you used it?",
    ],
    "Business Analyst": [
        "How do you gather requirements from stakeholders who disagree?",
        "Explain the difference between functional and non-functional requirements.",
        "Describe a time you translated a business problem into a data solution.",
        "How do you prioritize competing feature requests?",
        "What tools do you use for requirements documentation?",
        "Walk me through how you would conduct a gap analysis.",
        "How do you measure the success of a project after delivery?",
        "Describe a project where you identified a key insight that changed direction.",
    ],
    "Database Developer": [
        "Explain database normalization. What are the first three normal forms?",
        "What is an index and how does it improve query performance?",
        "When would you use a stored procedure vs. an ORM?",
        "Explain the difference between clustered and non-clustered indexes.",
        "How do you handle database migrations in a live production system?",
        "What is database sharding and when would you apply it?",
        "How do you diagnose and fix a slow query?",
        "Explain ACID properties with a real-world example.",
    ],
}

HR_QUESTIONS = [
    "Tell me about yourself and your career journey so far.",
    "Why are you interested in this role at {company}?",
    "What is your greatest professional strength? Give an example.",
    "Describe a time you faced a major challenge at work. How did you handle it?",
    "Where do you see yourself in 3–5 years?",
    "Tell me about a time you had to work with a difficult team member.",
    "How do you prioritize when you have multiple deadlines at once?",
    "Why are you leaving your current role?",
    "What motivates you in your work?",
    "What is one area where you are actively working to improve?",
]

BEHAVIORAL_QUESTIONS = [
    "Describe a project you are most proud of. What was your contribution?",
    "Tell me about a time you took initiative beyond your job description.",
    "Give an example of a time you failed and what you learned.",
    "Describe a situation where you had to influence someone without direct authority.",
    "Tell me about a time you had to learn something new quickly.",
    "Describe how you handle feedback and criticism.",
    "Give an example of a time you improved a process or workflow.",
    "Tell me about a time you had to make a decision with incomplete information.",
]


# ──────────────────────────────────────────────────────────────────────────────
# LLM Core Calling Layer (Groq / OpenAI / Gemini)
# ──────────────────────────────────────────────────────────────────────────────

def _parse_json_response(raw_text: str):
    """Safely parse JSON response from LLM."""
    if not raw_text:
        return {}
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return {}


def _call_groq(messages: list, api_key: str, model: str, temperature: float = 0.4, max_tokens: int = 1500, json_mode: bool = False) -> str:
    """Call Groq API using official SDK or HTTP fallback with automatic fallback models."""
    effective_max_tokens = min(max_tokens, 1500)
    
    # Candidate models to try in case of 429 rate limit or 404
    candidate_models = [model]
    for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    last_error = None
    for cand_model in candidate_models:
        # Try official SDK first
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            kwargs = {
                "model": cand_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            res = client.chat.completions.create(**kwargs)
            content = (res.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as e:
            last_error = e

        # Direct HTTP fallback
        try:
            import requests
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": cand_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45
            )
            if resp.status_code == 200:
                data = resp.json()
                content = (data["choices"][0]["message"]["content"] or "").strip()
                if content:
                    return content
            else:
                err_msg = resp.text
                try:
                    err_msg = resp.json().get("error", {}).get("message", resp.text)
                except Exception:
                    pass
                last_error = RuntimeError(f"Groq API error ({resp.status_code}) on model {cand_model}: {err_msg}")
        except Exception as http_e:
            last_error = http_e

    if last_error:
        raise last_error
    raise RuntimeError("Groq call failed without response")


def _call_openai_generic(messages: list, api_key: str, model: str, temperature: float = 0.5, max_tokens: int = 2000, json_mode: bool = False) -> str:
    """Call OpenAI API with optional json_mode. Auto-detects if user passed a Groq key."""
    # If the user passed a Groq API key (starts with gsk_), seamlessly route to Groq
    if api_key and api_key.strip().startswith("gsk_"):
        return _call_groq(
            messages,
            api_key.strip(),
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        res = client.chat.completions.create(**kwargs)
        return (res.choices[0].message.content or "").strip()
    except Exception as sdk_err:
        import requests
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=35)
        if resp.status_code == 200:
            return (resp.json()["choices"][0]["message"]["content"] or "").strip()
        raise sdk_err


def _call_gemini_generic(messages: list, api_key: str, model: str) -> str:
    """Call Gemini REST API for generic messages."""
    import requests
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents = []
    for m in messages:
        role = "model" if m.get("role") in ("assistant", "model") else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    resp = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": contents}, timeout=35)
    if resp.status_code == 200:
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            return candidates[0]["content"]["parts"][0]["text"].strip()
        return ""
    raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")


def _run_ai_completion(messages: list, temperature: float = 0.4, max_tokens: int = 2500, json_mode: bool = False) -> str:
    """Route completion to the active AI provider."""
    provider, api_key, model = get_active_ai_config()
    if provider == "groq":
        return _call_groq(messages, api_key, model, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
    elif provider == "openai":
        return _call_openai_generic(messages, api_key, model, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
    elif provider == "gemini":
        return _call_gemini_generic(messages, api_key, model)
    raise ValueError(f"No active AI provider configured ({provider})")


# ──────────────────────────────────────────────────────────────────────────────
# 1. Target Role Alignment (Groq / LLM Integration)
# ──────────────────────────────────────────────────────────────────────────────

def analyze_target_roles_with_llm(resume_text: str) -> list[dict]:
    """
    Improve Target Role Alignment:
    - Reads and understands user's resume content.
    - Identifies realistic and most suitable job roles based on skills, education, projects, experience.
    - Recommends relevant companies for those roles.
    - Compares resume against real-world role requirements and clearly shows missing skills / gaps.
    - Gives practical, evidence-based recommendations rather than generic suggestions.
    """
    provider, api_key, model = get_active_ai_config()
    if provider == "rule_based" or not api_key:
        return _rule_based_recommend_careers(resume_text)

    truncated_resume = " ".join(resume_text.split()[:3500])

    prompt = f"""You are a Principal Technical Recruiter and Career Architect.
Thoroughly examine the candidate's uploaded resume below.
Identify 4 to 6 of the candidate's most realistic and suitable job roles based on their:
1. Technical and domain skills
2. Formal education, degrees, and academic specialization
3. Practical internship or professional work experience
4. Hands-on projects, technologies used, and quantifiable achievements

For each recommended role, provide:
- "role": Exact professional job title (e.g. "Data Analyst", "Machine Learning Engineer", "Backend Software Engineer", "Full Stack Developer", etc.)
- "score": Realistic match score integer between 0 and 100 representing how well the current resume fits entry/mid-level hiring bars.
- "description": Concise overview of the role and its current industry scope.
- "reason": Practical, evidence-based recommendation citing specific resume evidence (cite their exact degree, specific projects, exact tools, or past internships). Do NOT give generic advice!
- "matched_skills": List of skills, libraries, and tools verified directly from their resume.
- "missing_skills": Specific missing skills, tools, or gaps required by real-world companies for this role.
- "recommended_companies": List of 4 to 6 real-world companies (mix of tech leaders, enterprise firms, and startups) that actively hire for this profile.

Output strictly valid JSON matching this schema:
{{
  "recommendations": [
    {{
      "role": "Role Title",
      "score": 85,
      "description": "Role overview...",
      "reason": "Evidence-based justification citing resume details...",
      "matched_skills": ["Skill A", "Skill B"],
      "missing_skills": ["Missing Skill X", "Missing Skill Y"],
      "recommended_companies": ["Company 1", "Company 2", "Company 3", "Company 4"]
    }}
  ]
}}

Candidate Resume:
{truncated_resume}
"""

    messages = [
        {"role": "system", "content": "You are a career intelligence AI. You always respond in valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    try:
        content = _run_ai_completion(messages, temperature=0.3, max_tokens=2500, json_mode=True)
        parsed = _parse_json_response(content)
        recs = parsed.get("recommendations", [])
        if recs and isinstance(recs, list):
            recs.sort(key=lambda x: int(x.get("score", 0)), reverse=True)
            return recs
    except Exception as e:
        print(f"[AI Service] Target role alignment error with {provider}: {e}")

    return _rule_based_recommend_careers(resume_text)


def analyze_role_skills_with_llm(resume_text: str, role: str) -> dict:
    """
    Analyze resume specifically for target role using Groq LLM.
    Returns matched skills, missing skills, and prioritized gap analysis.
    """
    provider, api_key, model = get_active_ai_config()
    if provider == "rule_based" or not api_key:
        return _rule_based_analyze_career_skills(resume_text, role)

    truncated_resume = " ".join(resume_text.split()[:3500])

    prompt = f"""You are a Technical Hiring Manager evaluating a candidate for the target role: "{role}".
Benchmark the candidate's resume against real-world industry requirements for this role.

Identify:
1. "matched_skills": Skills, tools, and frameworks already demonstrated in the resume with evidence.
2. "missing_skills": Skills, tools, or domain knowledge currently missing from the user's profile required by companies hiring for "{role}".
3. "prioritized_skills": A prioritized list of skills the candidate must learn, each with:
   - "skill": Name of the skill/technology
   - "priority": Exactly "High", "Medium", or "Later"
   - "reason": Practical, evidence-based reason explaining why hiring companies require this skill and how it connects to the candidate's existing background.
4. "description": A concise summary of what companies look for in a {role}.

Return strictly valid JSON matching this schema:
{{
  "role": "{role}",
  "description": "...",
  "matched_skills": ["Skill 1", "Skill 2"],
  "missing_skills": ["Skill 3", "Skill 4"],
  "prioritized_skills": [
    {{
      "skill": "Skill Name",
      "priority": "High",
      "reason": "Detailed practical explanation..."
    }}
  ]
}}

Resume:
{truncated_resume}
"""

    messages = [
        {"role": "system", "content": "You are a hiring manager and career analyst. Output valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    try:
        content = _run_ai_completion(messages, temperature=0.3, max_tokens=2000, json_mode=True)
        parsed = _parse_json_response(content)
        if parsed and "matched_skills" in parsed:
            return parsed
    except Exception as e:
        print(f"[AI Service] Role skills analysis error: {e}")

    return _rule_based_analyze_career_skills(resume_text, role)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Actionable Learning Roadmap (Groq / LLM Integration)
# ──────────────────────────────────────────────────────────────────────────────

def generate_learning_roadmap_with_llm(resume_text: str, role: str) -> dict:
    """
    Generate a practical, prioritized Actionable Learning Roadmap
    using Groq API/LLM based on:
    - User's actual resume
    - Target role
    - Required skills for that role
    - Real-world company job requirements
    - Skills currently missing from the user's profile
    """
    provider, api_key, model = get_active_ai_config()
    if provider == "rule_based" or not api_key:
        return _rule_based_roadmap(resume_text, role)

    truncated_resume = " ".join(resume_text.split()[:3500])

    prompt = f"""You are a Principal Engineering Mentor and Career Architect.
Generate a practical, prioritized Actionable Learning Roadmap for a candidate aiming for the role: "{role}".

The roadmap MUST be strictly customized to:
1. The user's actual resume (acknowledge verified strengths so they don't waste time re-learning basics).
2. Their target role: "{role}".
3. Real-world corporate and high-growth company requirements (production tools, architectures, data volumes, testing).
4. Skills and proficiencies currently missing from the user's profile.

Provide 4 to 6 chronological milestone phases (e.g., Week 1-2, Week 3-4, Week 5-6, Week 7-8...).
For each phase, specify:
- "week": Milestone period (e.g. "Week 1-2", "Week 3-4", etc.)
- "title": Actionable milestone title
- "detail": What to learn, in what specific order, and WHY this sequence matters for real-world hiring bars. Avoid generic platitudes! Be specific with tools, libraries, concepts, and techniques.
- "practical_project": A concrete, portfolio-ready project or engineering artifact the user should build to prove mastery to recruiters.

Return strictly valid JSON matching this schema:
{{
  "role": "{role}",
  "matched_skills": ["Skill 1", "Skill 2"],
  "missing_skills": ["Missing 1", "Missing 2"],
  "steps": [
    {{
      "week": "Week 1-2",
      "title": "Milestone Title",
      "detail": "What to learn, in what order, and why companies require this...",
      "practical_project": "Concrete project to build and showcase..."
    }}
  ]
}}

Candidate's Resume:
{truncated_resume}
"""

    messages = [
        {"role": "system", "content": "You are a technical mentor and career architect. Output valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    try:
        content = _run_ai_completion(messages, temperature=0.4, max_tokens=2500, json_mode=True)
        parsed = _parse_json_response(content)
        if parsed and parsed.get("steps"):
            return parsed
    except Exception as e:
        print(f"[AI Service] Roadmap generation error: {e}")

    return _rule_based_roadmap(resume_text, role)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Company-Based Mock Interview (Groq / LLM Integration)
# ──────────────────────────────────────────────────────────────────────────────

def generate_interview_questions(company: str, role: str, count: int = 15, question_count: int = None) -> list[dict]:
    """
    Generate company- and role-specific interview questions.
    Uses Groq API/LLM when configured. Where genuine public previous-year/interview questions
    are available, uses them accurately without fabricating PYQs. Clearly distinguishes
    real reported questions from AI-generated practice questions.
    """
    if question_count is not None:
        count = question_count
    provider, api_key, model = get_active_ai_config()
    if provider != "rule_based" and api_key:
        try:
            questions = _generate_interview_questions_llm(company, role, count)
            if questions and len(questions) > 0:
                return questions
        except Exception as e:
            print(f"[AI Service] LLM Question generation error with {provider}: {e}")

    return _rule_based_interview_questions(company, role, count)


def _generate_interview_questions_llm(company: str, role: str, count: int = 15) -> list[dict]:
    """Internal LLM generator for company/role interview questions."""
    prompt = f"""You are a Lead Technical Interviewer and Hiring Bar Raiser specializing in {company} interview loops for the role of {role}.

Generate exactly {count} interview questions tailored to {company} and {role}.

CRITICAL REQUIREMENTS FOR ACCURACY & HONESTY:
1. Genuine Public Previous-Year / Interview Questions (PYQs):
   Where authentic public questions reported by candidates in real {company} interview loops (e.g., from Glassdoor, LeetCode company tags, or interview debriefs) are known, use them accurately.
   Label them strictly with:
   - "is_pyq": true
   - "source_label": "Real Reported Question (PYQ)"
   - "source_note": Concise context (e.g., "Reported in {company} Technical Round / LeetCode #...")

2. Targeted Practice Questions:
   Where real reported questions are not documented or to evaluate complementary domain skills, create high-caliber practice questions tailored to {company}'s tech stack, scale, or leadership principles (e.g. Amazon Leadership Principles, Googleyness, Netflix culture).
   Label them strictly with:
   - "is_pyq": false
   - "source_label": "AI-Generated Practice Question"
   - "source_note": Concise context (e.g., "Targeted drill for {company} architecture and role expectations")

3. DO NOT fabricate questions and label them as real PYQs. Clearly distinguish real reported questions from AI-generated practice questions.

4. Include a balanced mix across:
   - Technical & Domain questions (algorithms, coding, SQL, frameworks)
   - System Design & Architecture (scale, APIs, database choices)
   - Behavioral / Leadership questions (STAR method, ownership, challenges)
   - Company Culture & Problem Domain

Return strictly valid JSON:
{{
  "questions": [
    {{
      "question": "Question text...",
      "category": "Technical" | "Behavioral" | "System Design" | "Company Culture",
      "is_pyq": true | false,
      "source_label": "Real Reported Question (PYQ)" | "AI-Generated Practice Question",
      "source_note": "Context on PYQ source or practice purpose"
    }}
  ]
}}
"""

    messages = [
        {"role": "system", "content": "You are a principal technical interviewer. Output valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    content = _run_ai_completion(messages, temperature=0.4, max_tokens=3000, json_mode=True)
    parsed = _parse_json_response(content)
    raw_questions = parsed.get("questions", [])
    if not raw_questions:
        raise ValueError("No questions returned by LLM.")

    result = []
    for i, q in enumerate(raw_questions[:count]):
        result.append({
            "question": q.get("question", "").strip(),
            "category": q.get("category", "Technical").strip(),
            "is_pyq": bool(q.get("is_pyq", False)),
            "source_label": q.get("source_label", "AI-Generated Practice Question").strip(),
            "source_note": q.get("source_note", "").strip(),
            "order_num": i + 1
        })
    return result


def evaluate_interview_answer(
    question: str,
    category: str,
    company: str,
    role: str,
    answer: str,
    source_label: str = ""
) -> dict:
    """
    Evaluate user's interview answer using Groq API/LLM.
    Identifies mistakes and missing points, provides correct/improved answer,
    gives brief explanation, and scores the answer.
    """
    if not answer or len(answer.strip()) < 10:
        return {
            "score": 2,
            "verdict": "Incomplete",
            "mistakes": ["Answer is too brief or empty to assess technical competency."],
            "missing_points": ["Core technical explanation", "Concrete real-world example", "Methodology / trade-offs"],
            "improved_answer": "A complete answer should address the question directly with clear structure, terminology, and practical examples.",
            "explanation": "Interviewers expect structured answers that demonstrate depth, clarity, and practical problem-solving.",
            "formatted": "⚠️ **Answer too brief:** Please provide a more detailed response to receive meaningful evaluation."
        }

    provider, api_key, model = get_active_ai_config()
    if provider != "rule_based" and api_key:
        try:
            prompt = f"""You are a Senior Technical Interviewer evaluating a candidate practicing for:
Company: {company}
Role: {role}
Category: {category}
Question: {question}
Question Source: {source_label or 'Interview Question'}

Candidate's Answer:
\"\"\"{answer}\"\"\"

Provide an objective, thorough evaluation:
1. "score": An integer from 1 to 10 evaluating the quality, accuracy, and depth of the answer.
2. "verdict": "Excellent" (9-10) | "Good" (7-8) | "Average" (5-6) | "Needs Improvement" (1-4)
3. "mistakes": List of specific mistakes, inaccuracies, or anti-patterns in the candidate's answer. If none, provide an empty list or subtle refinement.
4. "missing_points": List of critical points, edge cases, trade-offs, metrics, or STAR elements the user omitted.
5. "improved_answer": A high-scoring, recruiter-ready model answer demonstrating how to answer this question at an elite level (use Markdown and code/queries if technical).
6. "explanation": A clear, concise explanation of the underlying technical or behavioral concepts.

Return strictly valid JSON:
{{
  "score": 8,
  "verdict": "Good",
  "mistakes": ["Mistake 1", "..."],
  "missing_points": ["Missing point 1", "..."],
  "improved_answer": "...",
  "explanation": "..."
}}
"""
            messages = [
                {"role": "system", "content": "You are a senior hiring bar raiser. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            content = _run_ai_completion(messages, temperature=0.3, max_tokens=2000, json_mode=True)
            parsed = _parse_json_response(content)
            if parsed and "score" in parsed:
                mistakes_md = "\n".join(f"• {m}" for m in parsed.get("mistakes", [])) or "• None noted"
                missing_md = "\n".join(f"• {m}" for m in parsed.get("missing_points", [])) or "• None noted"
                formatted = (
                    f"**Score: {parsed.get('score', 0)}/10 ({parsed.get('verdict', 'Evaluated')})**\n\n"
                    f"**❌ Mistakes / Inaccuracies:**\n{mistakes_md}\n\n"
                    f"**🔍 Missing Points:**\n{missing_md}\n\n"
                    f"**💡 Improved / Model Answer:**\n{parsed.get('improved_answer', '')}\n\n"
                    f"**📖 Explanation:**\n{parsed.get('explanation', '')}"
                )
                parsed["formatted"] = formatted
                return parsed
        except Exception as e:
            print(f"[AI Service] Answer evaluation error: {e}")

    # Fallback to rule-based feedback
    fallback_text = _rule_based_answer_feedback(answer, question, category)
    return {
        "score": 6,
        "verdict": "Practiced",
        "mistakes": [],
        "missing_points": ["Add more concrete examples and quantify results."],
        "improved_answer": "Structure your answer using specific terminology, examples, and measurable outcomes.",
        "explanation": "Provide structured reasoning with clear technical depth.",
        "formatted": fallback_text
    }


def generate_interview_summary(company="Target Company", role="Professional", qa_pairs=None) -> dict:
    """
    Generate final interview evaluation at the end of the session:
    Calculates overall score (0-100), provides strengths, weaknesses,
    and personalized interview improvement tips for {company} and {role}.
    """
    # Handle swapped positional arguments if qa_pairs was passed first
    if isinstance(company, list):
        qa_pairs, company, role = company, (qa_pairs if isinstance(qa_pairs, str) else "Target Company"), (role or "Candidate")
    
    if qa_pairs is None:
        qa_pairs = []

    def _get_val(obj, key, default=""):
        if isinstance(obj, dict):
            return obj.get(key, default)
        try:
            return obj[key] if key in obj.keys() else default
        except Exception:
            return default

    answered_pairs = [p for p in qa_pairs if str(_get_val(p, "answer", "")).strip()]
    if not answered_pairs:
        return {
            "overall_score": 0,
            "verdict": "Incomplete",
            "strengths": ["Session initiated."],
            "weaknesses": ["No questions were answered."],
            "personalized_tips": ["Complete all interview questions to receive a comprehensive analysis."],
            "summary_text": "Interview was concluded without answers."
        }

    provider, api_key, model = get_active_ai_config()
    if provider != "rule_based" and api_key:
        try:
            transcript_items = []
            for i, p in enumerate(answered_pairs):
                q_text = _get_val(p, "question", "")
                cat_text = _get_val(p, "category", "General")
                ans_text = _get_val(p, "answer", "")
                transcript_items.append(
                    f"Q{i+1} ({cat_text}): {q_text}\n"
                    f"Candidate Answer: {ans_text}\n"
                )
            transcript = "\n".join(transcript_items[:15])

            prompt = f"""You are a Hiring Bar Raiser and Principal Recruiter conducting the final debrief for:
Company: {company}
Role: {role}

Below is the candidate's interview transcript ({len(answered_pairs)} questions answered):
{transcript}

Conduct a comprehensive final evaluation:
1. "overall_score": Integer from 0 to 100 representing their overall interview readiness for {company}.
2. "verdict": "Strong Hire" (85-100) | "Hire" (70-84) | "Lean Hire" (55-69) | "Needs More Preparation" (<55)
3. "strengths": 3-5 specific bullet points of demonstrated strengths in their technical knowledge, communication, and problem-solving.
4. "weaknesses": 3-5 specific areas where the candidate fell short or showed knowledge gaps.
5. "personalized_tips": 3-5 actionable, high-impact tips specifically calibrated to succeed in {company}'s actual interview loops for {role}.
6. "summary_text": A 2-3 sentence executive recruiter verdict on the candidate's performance.

Return strictly valid JSON:
{{
  "overall_score": 78,
  "verdict": "Hire",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "personalized_tips": ["..."],
  "summary_text": "..."
}}
"""
            messages = [
                {"role": "system", "content": "You are a hiring bar raiser. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            content = _run_ai_completion(messages, temperature=0.3, max_tokens=2000, json_mode=True)
            parsed = _parse_json_response(content)
            if parsed and "overall_score" in parsed:
                return parsed
        except Exception as e:
            print(f"[AI Service] Interview summary error: {e}")

    # Fallback calculation
    avg_score = min(85, max(40, int(len(answered_pairs) * 12)))
    return {
        "overall_score": avg_score,
        "verdict": "Practiced",
        "strengths": [
            f"Demonstrated dedication to practicing company-specific questions for {company}.",
            "Completed multiple technical and behavioral interview prompts."
        ],
        "weaknesses": [
            "Needs deeper technical examples and structured STAR responses.",
            "Include more quantitative metrics and architectural trade-offs."
        ],
        "personalized_tips": [
            f"Review {company}'s core architectural patterns and leadership values before interviewing.",
            "Practice articulating technical decisions with the 'Trade-off' framework (Option A vs Option B).",
            "Prepare 3 concrete project stories using the STAR format."
        ],
        "summary_text": f"Completed mock interview session for {company} - {role} with {len(answered_pairs)} answers recorded."
    }


# ──────────────────────────────────────────────────────────────────────────────
# Deterministic Rule-Based Fallbacks (Original Logic Preserved)
# ──────────────────────────────────────────────────────────────────────────────

def _detect_company_profile(company: str) -> str:
    """Match a company name to a known profile key."""
    lower = (company or "").lower()
    for key in COMPANY_PROFILES:
        if key in lower:
            return key
    return "startup"


def _rule_based_recommend_careers(resume_text: str) -> list[dict]:
    """Original keyword-based career recommender."""
    resume_lower = resume_text.lower()
    recommendations = []

    default_companies = {
        "Data Analyst": ["Deloitte", "Mu Sigma", "Accenture", "TCS", "Fractal Analytics"],
        "Data Scientist": ["Google", "Amazon", "Microsoft", "Meta", "Tiger Analytics"],
        "Machine Learning Engineer": ["Google", "NVIDIA", "Meta", "Amazon", "OpenAI"],
        "Business Analyst": ["McKinsey", "BCG", "Deloitte", "KPMG", "EY"],
        "Python Developer": ["Red Hat", "Spotify", "Dropbox", "Infosys", "Wipro"],
        "Frontend Developer": ["Meta", "Uber", "Shopify", "Airbnb", "Atlassian"],
        "Database Developer": ["Oracle", "Snowflake", "MongoDB", "Amazon AWS", "IBM"],
        "Software Developer": ["Microsoft", "Google", "Amazon", "Cisco", "Adobe"]
    }

    for role, info in CAREER_ROLES.items():
        matched_skills = [
            skill for skill in info["skills"]
            if re.search(r"(?<![a-z0-9+#])" + re.escape(skill) + r"(?![a-z0-9+#])", resume_lower)
        ]
        missing_skills = [skill for skill in info["skills"] if skill not in matched_skills]
        score = round(len(matched_skills) / len(info["skills"]) * 100)

        if matched_skills:
            recommendations.append({
                "role": role,
                "score": score,
                "description": info["description"],
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "recommended_companies": default_companies.get(role, ["Google", "Amazon", "Microsoft", "TCS"]),
                "reason": (
                    f"Your resume includes {len(matched_skills)} "
                    f"of the {len(info['skills'])} listed skills "
                    f"for this role."
                )
            })

    recommendations.sort(key=lambda item: item["score"], reverse=True)
    return recommendations[:5]


def _rule_based_analyze_career_skills(resume_text: str, role: str) -> dict:
    """Original career skill analyzer."""
    info = CAREER_ROLES.get(role, CAREER_ROLES.get("Software Developer"))
    resume_lower = resume_text.lower()

    matched = [
        skill for skill in info["skills"]
        if re.search(r"(?<![a-z0-9+#])" + re.escape(skill) + r"(?![a-z0-9+#])", resume_lower)
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


def _rule_based_roadmap(resume_text: str, role: str) -> dict:
    """Original rule-based roadmap generator."""
    report = _rule_based_analyze_career_skills(resume_text, role)
    gaps = report["prioritized_skills"]
    steps = []

    if gaps:
        for start in range(0, len(gaps), 2):
            group = gaps[start:start + 2]
            week = len(steps) + 1
            priority = group[0]["priority"]
            skill_names = [item["skill"] for item in group]
            steps.append({
                "week": f"Week {week}",
                "title": f"Learn {priority.lower()}-priority skills",
                "detail": (
                    "Focus on: " + ", ".join(skill_names)
                    + ". Study the concepts, practice with exercises, and build a small example."
                ),
                "practical_project": f"Build a mini project demonstrating {', '.join(skill_names)}."
            })
        steps.append({
            "week": f"Week {len(steps) + 1}",
            "title": f"Build a {role} project",
            "detail": (
                "Apply your newly learned skills in one practical project. "
                "Document your work and add it to your portfolio."
            ),
            "practical_project": f"End-to-end {role} capstone repository."
        })
    else:
        steps = [
            {"week": "Week 1", "title": "Strengthen your foundations",
             "detail": f"Review the skills already listed in your resume for {role}.",
             "practical_project": "Refactor previous coursework or project code."},
            {"week": "Week 2", "title": "Build a practical project",
             "detail": f"Create a project that demonstrates your {role} skills.",
             "practical_project": "Develop a production-grade application."},
            {"week": "Week 3", "title": "Improve your portfolio",
             "detail": "Document your project, decisions and results.",
             "practical_project": "Publish technical README and documentation."},
            {"week": "Week 4", "title": "Prepare for applications",
             "detail": "Practice role-related questions and tailor your resume.",
             "practical_project": "Mock interview practice drills."}
        ]

    return {
        "role": role,
        "matched_skills": report["matched_skills"],
        "missing_skills": report["missing_skills"],
        "steps": steps
    }


def _rule_based_interview_questions(company: str, role: str, count: int = 15) -> list[dict]:
    """Rule-based question generator with source labeling."""
    company_key = _detect_company_profile(company)
    questions = []

    role_q = ROLE_TECH_QUESTIONS.get(role, ROLE_TECH_QUESTIONS.get("Software Developer", []))
    tech_pool = role_q.copy()
    random.shuffle(tech_pool)
    tech_count = min(7, count // 2 + 1)
    for q in tech_pool[:tech_count]:
        questions.append({
            "question": q,
            "category": "Technical",
            "is_pyq": False,
            "source_label": "AI-Generated Practice Question",
            "source_note": f"Standard {role} interview drill",
            "order_num": len(questions) + 1
        })

    hr_pool = [q.replace("{company}", company) for q in HR_QUESTIONS.copy()]
    random.shuffle(hr_pool)
    hr_count = min(4, (count - tech_count) // 2 + 1)
    for q in hr_pool[:hr_count]:
        questions.append({
            "question": q,
            "category": "HR",
            "is_pyq": False,
            "source_label": "AI-Generated Practice Question",
            "source_note": "Behavioral & HR screen",
            "order_num": len(questions) + 1
        })

    beh_pool = BEHAVIORAL_QUESTIONS.copy()
    random.shuffle(beh_pool)
    beh_count = max(1, count - tech_count - hr_count)
    for q in beh_pool[:beh_count]:
        questions.append({
            "question": q,
            "category": "Behavioral",
            "is_pyq": False,
            "source_label": "AI-Generated Practice Question",
            "source_note": "STAR Behavioral scenario",
            "order_num": len(questions) + 1
        })

    if company_key and company_key in COMPANY_PROFILES:
        profile = COMPANY_PROFILES[company_key]
        company_q = {
            "question": (
                f"What do you know about {company}'s culture and values? "
                f"How do you see yourself contributing? "
                f"(Note: {company} is known for {', '.join(profile['known_for'][:2])})"
            ),
            "category": "Company-Specific",
            "is_pyq": False,
            "source_label": "AI-Generated Practice Question",
            "source_note": f"Targeted {company} culture drill",
            "order_num": len(questions) + 1
        }
        questions.insert(1, company_q)
        for i, q in enumerate(questions):
            q["order_num"] = i + 1

    return questions[:count]


def _rule_based_answer_feedback(answer: str, question: str, category: str) -> str:
    """Original rule-based feedback generator."""
    if not answer or len(answer.strip()) < 20:
        return (
            "Your answer is quite brief. Try to expand with a specific example. "
            "For behavioral questions, use the STAR method: "
            "Situation → Task → Action → Result."
        )

    word_count = len(answer.split())
    tips = []

    if word_count < 50:
        tips.append("Consider adding more detail and a concrete example.")
    elif word_count > 400:
        tips.append("Try to be more concise — aim for 100–200 words in an interview.")

    if category == "Behavioral":
        has_star = any(w in answer.lower() for w in ["situation", "task", "action", "result", "outcome", "because", "so i", "therefore"])
        if not has_star:
            tips.append("Structure your answer using the STAR method for stronger impact.")

    if category == "Technical":
        if "for example" not in answer.lower() and "such as" not in answer.lower() and "e.g" not in answer.lower():
            tips.append("Add a concrete technical example to strengthen your answer.")

    if tips:
        return "Good attempt! Tips: " + " | ".join(tips)

    return (
        "Well structured answer! Make sure to verify technical accuracy and "
        "practice delivering it confidently within 90 seconds."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Chatbot Support
# ──────────────────────────────────────────────────────────────────────────────

CHATBOT_SYSTEM_PROMPT = """You are Career Lens AI, an elite, highly intelligent Career Strategist, Technical Recruiter, and Interview Coach — powered by state-of-the-art AI, just like ChatGPT.

You communicate with warmth, authority, clarity, and precision. You format your responses beautifully using bold headings, bullet points, numbered lists, and code blocks where appropriate.

Your core expertise:
1. Resume & ATS Optimization: Section organization, quantifiable achievement bullets, ATS keyword alignment, impact metrics (X-Y-Z formula: Accomplished [X] as measured by [Y], by doing [Z]).
2. Career Pathing & Transitions: Strategic roadmaps from beginner to senior, tech stack recommendations, industry insights.
3. Interview Preparation: Behavioral (STAR method: Situation, Task, Action, Result), technical questions, system design walkthroughs, company-specific culture (e.g. Google, Amazon, Microsoft, Meta).
4. Digital Portfolio & Projects: Guiding users on what projects to showcase, how to present certifications, and documenting skills.
5. Salary Negotiation: Market benchmark research, counter-offers, total compensation analysis, and exact negotiation scripts.
6. Career Lens Features: Seamlessly mention Career Lens built-in tools (ATS Resume Analyzer, Career Role Matcher, Skill Gap Analyzer, Learning Roadmap, Mock Interview drills, and Document Portfolio).

Guidelines:
- Give comprehensive, actionable, real-world advice — avoid generic platitudes.
- Break down complex advice into clear, easy-to-follow steps.
- Maintain an encouraging, sharp, and professional tone.
"""

RULE_BASED_RESPONSES = {
    "resume": [
        "**Resume Tips for ATS Success:**\n\n"
        "• Use a clean, single-column format with standard section headings\n"
        "• Include your contact info (email, phone, LinkedIn) at the top\n"
        "• Tailor keywords to match the job description\n"
        "• Use bullet points starting with action verbs (Built, Designed, Led...)\n"
        "• Keep it to 1–2 pages\n"
        "• Upload your resume in Career Lens to get your ATS score!"
    ],
    "interview": [
        "**Interview Preparation Tips:**\n\n"
        "• Research the company's products, culture, and recent news\n"
        "• Practice the STAR method for behavioral questions\n"
        "• Prepare 3–5 stories from your experience\n"
        "• Study role-specific technical topics\n"
        "• Use Career Lens Mock Interviews to practice company-specific questions!"
    ],
    "career": [
        "**Career Planning Guidance:**\n\n"
        "• Start by identifying your core skills and interests\n"
        "• Upload your resume to Career Lens for role recommendations\n"
        "• Use the Skill Gap Analysis to see what to learn next\n"
        "• Build a portfolio of real projects\n"
        "• Network actively on LinkedIn\n"
        "• Set a 3-month learning goal and track progress weekly"
    ],
    "skill": [
        "**Building Skills for Career Growth:**\n\n"
        "• Identify the top 3 skills needed for your target role\n"
        "• Use platforms like Coursera, freeCodeCamp, or YouTube\n"
        "• Build small projects to apply new skills immediately\n"
        "• Add skills to your resume only after practical use\n"
        "• Use the Skill Gap Analysis in Career Lens to get a personalized list!"
    ],
    "portfolio": [
        "**Career Portfolio Best Practices:**\n\n"
        "• Store your best resume, certificates, and experience letters\n"
        "• Keep documents organized by category\n"
        "• Use Career Lens Portfolio to upload and manage all your career documents\n"
        "• Add your GitHub and LinkedIn links to your profile\n"
        "• Keep your portfolio updated after each new achievement"
    ],
    "salary": [
        "**Salary Negotiation Tips:**\n\n"
        "• Research market rates on Glassdoor, LinkedIn Salary, and Levels.fyi\n"
        "• Know your BATNA (Best Alternative to a Negotiated Agreement)\n"
        "• Wait for the employer to make the first offer when possible\n"
        "• Negotiate the full package: base, bonus, equity, benefits\n"
        "• Practice your negotiation script out loud before the call"
    ],
    "linkedin": [
        "**LinkedIn Profile Optimization:**\n\n"
        "• Add a professional photo (3x more profile views)\n"
        "• Write a compelling headline (not just your job title)\n"
        "• Craft a summary that tells your career story\n"
        "• List your top skills and get endorsements\n"
        "• Add projects, certifications, and publications\n"
        "• Connect with 10 new professionals in your field every week"
    ],
    "default": [
        "I'm Career Lens AI, your career assistant! 🚀\n\n"
        "I can help you with:\n"
        "• **Resume writing** and ATS optimization\n"
        "• **Interview prep** (technical, behavioral, and company-specific)\n"
        "• **Career planning** and skill roadmaps\n"
        "• **Portfolio** guidance\n"
        "• **Job applications** and salary negotiation\n\n"
        "What would you like advice on today?",

        "Great question! Career advancement comes down to three main levers:\n\n"
        "1. **Demonstrated Skills** — continuous hands-on learning\n"
        "2. **Portfolio & Proof** — tangible projects that solve real problems\n"
        "3. **Narrative & Positioning** — how clearly your resume and interviews communicate your value\n\n"
        "Upload your resume to Career Lens to get an instant ATS score and tailored role recommendations!"
    ]
}


def get_chatbot_response(user_message: str, history: list = None) -> str:
    """
    Generate a chatbot response.
    Automatically uses real Groq, OpenAI, or Gemini when an API key is provided,
    otherwise falls back to intelligent built-in career responses.
    """
    provider, api_key, model = get_active_ai_config()

    if provider != "rule_based" and api_key:
        try:
            return _call_llm(user_message, history or [], provider, api_key, model)
        except Exception as e:
            err_str = str(e)
            return (
                f"⚠️ **AI Service Notice:** Could not connect to {provider.upper()} API.\n\n"
                f"*Details:* `{err_str}`\n\n"
                f"---\n\n"
                f"{_rule_based_response(user_message)}"
            )

    return _rule_based_response(user_message)


def _rule_based_response(message: str) -> str:
    """Simple keyword-based response matching."""
    lower = message.lower()
    for keyword, responses in RULE_BASED_RESPONSES.items():
        if keyword in lower:
            return random.choice(responses)
    return random.choice(RULE_BASED_RESPONSES["default"])


def _call_llm(user_message: str, history: list, provider: str, api_key: str, model: str) -> str:
    """Call active LLM API."""
    messages = [{"role": "system", "content": CHATBOT_SYSTEM_PROMPT}]
    for item in (history or [])[-12:]:
        r = item.get("role", "user")
        c = (item.get("content") or "").strip()
        if r in ("user", "assistant") and c:
            messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": user_message})

    if provider == "groq":
        return _call_groq(messages, api_key, model, temperature=0.7, max_tokens=1500)
    elif provider == "openai":
        return _call_openai_generic(messages, api_key, model, temperature=0.7, max_tokens=1500)
    elif provider == "gemini":
        return _call_gemini_generic(messages, api_key, model)
    raise ValueError(f"Unsupported AI provider: {provider}")
