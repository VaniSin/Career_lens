CAREER LENS WEBSITE STARTER
1. Back up the existing app.py.
2. Copy this package's app.py into career_intelligence_starter, replacing the Streamlit app.py.
3. Copy templates and static folders into career_intelligence_starter (merge folders if prompted).
4. Keep modules/ats_analyzer.py already present. Keep resume_parser.py; this Flask prototype uses PyMuPDF directly.
5. With .venv activated and terminal in career_intelligence_starter, run:
   pip install -r requirements_web.txt
6. Run: python app.py
7. Open http://127.0.0.1:5000

Local prototype only: uploaded resume text is held in server memory. ATS and keyword scores are heuristic, not guarantees.
