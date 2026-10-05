# 🎯 CareerLens

**CareerLens** is an AI-powered Career Intelligence and Mock Interview Platform that helps developers, students, and professionals analyze their resumes against real-world job requirements, bridge skill gaps with actionable learning roadmaps, and practice realistic company-tailored interviews powered by **Groq / LLMs**.

---

## ✨ Key Features

### 1. 🔍 Target Role Alignment (Groq / LLM Powered)
- Analyzes uploaded resumes (PDF) using modern LLMs.
- Maps your actual skills, experience, education, and projects to the most suitable job roles.
- Recommends real-world hiring companies (FAANG, tier-1 tech, high-growth startups) tailored to each matched role.
- Highlights strengths and identifies missing skills against actual production hiring bars with clear, evidence-based rationales.

### 2. 🗺️ Actionable Learning Roadmap
- Generates a prioritized, week-by-week learning plan tailored to your profile.
- Chronological milestone phases designed to bridge missing skill gaps in the correct sequence.
- Recommends concrete, portfolio-ready projects and engineering artifacts to prove mastery to recruiters.

### 3. 💼 Company-Based Mock Interview Loop
- **Authentic Questions**: Input any target company (e.g. Google, Amazon, Microsoft, Meta, Stripe) and role.
- **PYQ vs. AI-Practice Distinction**: Clearly distinguishes genuine publicly reported previous-year interview questions (PYQs) from AI-generated practice questions without fabricating data.
- **Live Per-Question Evaluation**: Real-time scoring (1-10), identification of subtle mistakes, missing technical points, and improved model answers with detailed explanations.
- **Executive Performance Report**: Overall interview readiness score (0-100), hiring verdict (*Strong Hire*, *Hire*, *Lean Hire*, *Needs More Prep*), demonstrated strengths, areas for improvement, and company-specific tips.

### 4. 📄 ATS Resume Analyzer
- Automated ATS compatibility scoring.
- Section completeness analysis, action-verb detection, quantify-results recommendations, and bullet-point critique.

### 5. 🤖 Career Intelligence AI Chatbot
- Multi-turn conversational AI mentor for resume polishing, interview prep, salary negotiation, and career strategy.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask, SQLite
- **AI / LLM Integration**: Groq API (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`) with automatic fallbacks
- **PDF Extraction**: PyMuPDF (`fitz`)
- **Frontend**: Responsive HTML5, Modern CSS Design System, Vanilla JavaScript

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/bhupendrasinghh/Career_Lens.git
cd Career_Lens
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements_web.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and set your Groq API key:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
PORT=5001
```

### 5. Run the Application

#### Option A: Run with Docker & Docker Compose (Recommended)
```bash
docker compose up -d --build
```
Check container logs:
```bash
docker compose logs -f
```
Stop the container:
```bash
docker compose down
```

#### Option B: Run Directly with Python
```bash
python3 app.py
```
Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

---

## 📁 Project Structure

```
├── Dockerfile              # Production multi-stage Docker configuration
├── docker-compose.yml      # Single-command orchestration with volume mounts
├── .dockerignore           # Excludes local environments & secrets from images
├── app.py                  # Main Flask application & routes
├── ai_service.py           # Core AI/LLM service layer (Groq integration)
├── interview.py            # Mock interview Blueprint & evaluation logic
├── ats_analyzer.py         # ATS resume scoring and heuristics
├── auth.py                 # User authentication & session management
├── chatbot.py              # AI career chatbot blueprint
├── database.py             # SQLite schema, tables & auto-migrations
├── portfolio.py            # Portfolio & document management
├── templates/
│   └── index.html          # Single-page web application UI
├── static/
│   ├── css/style.css       # Complete modern CSS design system
│   └── js/main.js          # Interactive frontend controller
├── requirements_web.txt    # Python dependencies
├── .env.example            # Environment variable template
└── .gitignore              # Git ignore rules (protects credentials)
```

---

## 🔒 Security
- Secrets and `.env` files are excluded via `.gitignore`.
- Database files (`careerlens.db`) and uploaded resumes (`uploads/`) are kept local.
