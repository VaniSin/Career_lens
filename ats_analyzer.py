
import re

SECTIONS = {
    "Contact Information": [
        "email", "phone", "linkedin"
    ],
    "Education": [
        "education", "academic", "university", "college"
    ],
    "Skills": [
        "skills", "technical skills", "technologies"
    ],
    "Projects": [
        "projects", "project experience"
    ],
    "Experience": [
        "experience", "internship", "employment",
        "work history"
    ],
    "Certifications": [
        "certifications", "certificates", "courses"
    ]
}

STOP_WORDS = {
    "the", "and", "for", "with", "you", "your", "our",
    "are", "will", "this", "that", "from", "have",
    "has", "who", "what", "where", "when", "their",
    "they", "about", "into", "such", "all", "any",
    "can", "should", "must", "using", "use", "work",
    "working", "role", "team", "years", "year",
    "ability", "experience", "knowledge", "strong",
    "good", "required"
}


def extract_keywords(text):
    words = re.findall(
        r"\b[a-zA-Z][a-zA-Z+#.-]{1,}\b",
        text.lower()
    )
    return list(dict.fromkeys(
        word for word in words
        if word not in STOP_WORDS and len(word) > 2
    ))


def analyze_resume(text, job_description=""):
    clean_text = re.sub(r"\s+", " ", text).strip()
    lower_text = clean_text.lower()

    suggestions = []
    breakdown = {}

    # 1. Section completeness: 30 points
    found_sections = []

    for section, keywords in SECTIONS.items():
        if any(
            re.search(r"\b" + re.escape(keyword) + r"\b", lower_text)
            for keyword in keywords
        ):
            found_sections.append(section)

    section_score = round(
        len(found_sections) / len(SECTIONS) * 30
    )

    missing_sections = [
        section for section in SECTIONS
        if section not in found_sections
    ]

    breakdown["Section Completeness"] = {
        "score": section_score,
        "max": 30
    }

    if missing_sections:
        suggestions.append(
            "Add or clearly label relevant sections: "
            + ", ".join(missing_sections)
        )

    # 2. Contact information: 15 points
    contact_score = 0

    if re.search(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        text
    ):
        contact_score += 7
    else:
        suggestions.append("Add a valid email address.")

    if re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text):
        contact_score += 5
    else:
        suggestions.append("Add a clearly formatted phone number.")

    if "linkedin" in lower_text:
        contact_score += 3
    else:
        suggestions.append("Consider adding your LinkedIn profile.")

    breakdown["Contact Information"] = {
        "score": contact_score,
        "max": 15
    }

    # 3. Job keyword matching: 25 points
    matched_keywords = []
    missing_keywords = []

    if job_description.strip():
        keywords = extract_keywords(job_description)

        matched_keywords = [
            word for word in keywords
            if re.search(r"\b" + re.escape(word) + r"\b", lower_text)
        ]

        missing_keywords = [
            word for word in keywords
            if word not in matched_keywords
        ]

        keyword_score = (
            round(len(matched_keywords) / len(keywords) * 25)
            if keywords else 0
        )

        if missing_keywords:
            suggestions.append(
                "Review missing job keywords and include those "
                "that genuinely match your skills: "
                + ", ".join(missing_keywords[:15])
            )
    else:
        keyword_score = 12
        suggestions.append(
            "Add a target job description for personalized "
            "keyword matching."
        )

    breakdown["Keyword Matching"] = {
        "score": keyword_score,
        "max": 25
    }

    # 4. Readability indicators: 15 points
    formatting_score = 15
    word_count = len(clean_text.split())

    if len(text) < 300:
        formatting_score -= 5
        suggestions.append(
            "Check whether your resume has enough extractable text."
        )

    if len(re.findall(r"[^\x00-\x7F]", text)) > len(text) * 0.1:
        formatting_score -= 3
        suggestions.append(
            "Review unusual symbols and special characters."
        )

    if text.count("|") > 10 or text.count("•") > 50:
        formatting_score -= 3
        suggestions.append(
            "Review separators and bullet formatting."
        )

    formatting_score = max(0, formatting_score)

    breakdown["Readability Indicators"] = {
        "score": formatting_score,
        "max": 15
    }

    # 5. Resume length: 15 points
    if 250 <= word_count <= 1000:
        length_score = 15
    elif 150 <= word_count < 250 or 1001 <= word_count <= 1300:
        length_score = 10
    elif 100 <= word_count < 150 or 1301 <= word_count <= 1600:
        length_score = 5
    else:
        length_score = 2

    breakdown["Resume Length"] = {
        "score": length_score,
        "max": 15
    }

    if word_count < 250:
        suggestions.append(
            "Consider adding relevant projects, skills or experience."
        )
    elif word_count > 1000:
        suggestions.append(
            "Consider removing repetitive or less relevant content."
        )

    total_score = sum(
        item["score"] for item in breakdown.values()
    )

    if total_score >= 85:
        rating = "Strong compatibility indicators"
    elif total_score >= 70:
        rating = "Good compatibility indicators"
    elif total_score >= 50:
        rating = "Needs improvement"
    else:
        rating = "Significant improvements suggested"

    return {
        "score": total_score,
        "rating": rating,
        "breakdown": breakdown,
        "found_sections": found_sections,
        "missing_sections": missing_sections,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "word_count": word_count,
        "suggestions": suggestions
    }