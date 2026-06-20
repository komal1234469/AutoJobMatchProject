"""
Resume parser.
Extracts raw text from PDF/DOCX, then uses simple heuristics + keyword
matching to pull out skills, experience, and education.

This is intentionally rule-based (not an LLM call) for the extraction
step, so it's fast and free. The AI/LLM step is reserved for matching
and generation, where it adds the most value.
"""
import re
import pdfplumber
from docx import Document

# A reasonably broad skill keyword bank. Extend this over time -
# this is the kind of thing you'll keep tuning as you test with
# real resumes.
SKILL_BANK = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
    "SQL", "NoSQL", "MongoDB", "PostgreSQL", "MySQL", "SQLite", "Redis",
    "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask",
    "FastAPI", "Spring Boot", "HTML", "CSS", "Tailwind", "Bootstrap",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Jenkins",
    "Git", "GitHub", "GitLab", "Linux", "Bash", "Shell Scripting",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "NumPy",
    "Data Analysis", "Data Visualization", "Tableau", "Power BI", "Excel",
    "REST API", "GraphQL", "Microservices", "Agile", "Scrum", "Jira",
    "Project Management", "Communication", "Leadership", "Problem Solving",
    "Figma", "UI/UX", "Photoshop", "Salesforce", "SAP", "Spark", "Hadoop",
    "Kafka", "Terraform", "Ansible", "R", "MATLAB", "Swift", "Kotlin",
    "Android", "iOS", "Flutter", "React Native", "PHP", "Ruby", "Rails",
]

EDUCATION_KEYWORDS = [
    "B.Tech", "M.Tech", "B.E.", "M.E.", "Bachelor", "Master", "B.Sc", "M.Sc",
    "MBA", "BCA", "MCA", "PhD", "Diploma", "B.A.", "M.A.", "B.Com", "M.Com",
]

SECTION_HEADERS = {
    "experience": ["experience", "work experience", "employment history", "professional experience"],
    "education": ["education", "academic background", "qualifications"],
    "skills": ["skills", "technical skills", "core competencies", "key skills"],
}


def extract_text_from_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_docx(filepath):
    doc = Document(filepath)
    return "\n".join(para.text for para in doc.paragraphs)


def extract_raw_text(filepath):
    if filepath.lower().endswith(".pdf"):
        return extract_text_from_pdf(filepath)
    elif filepath.lower().endswith(".docx"):
        return extract_text_from_docx(filepath)
    else:
        raise ValueError("Unsupported file type. Please upload a PDF or DOCX file.")


def extract_skills(text):
    """Match against the skill bank, case-insensitive, word-boundary aware."""
    found = []
    text_lower = text.lower()
    for skill in SKILL_BANK:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def extract_section(text, section_keys):
    """
    Naive section splitter: finds a header line matching one of section_keys,
    and grabs text until the next likely header line.
    """
    lines = text.split("\n")
    start_idx = None
    for i, line in enumerate(lines):
        clean = line.strip().lower().rstrip(":")
        if clean in section_keys:
            start_idx = i + 1
            break
    if start_idx is None:
        return ""

    end_idx = len(lines)
    all_headers = sum(SECTION_HEADERS.values(), [])
    for i in range(start_idx, len(lines)):
        clean = lines[i].strip().lower().rstrip(":")
        if clean in all_headers and clean not in section_keys:
            end_idx = i
            break

    return "\n".join(lines[start_idx:end_idx]).strip()


def extract_education(text):
    edu_text = extract_section(text, SECTION_HEADERS["education"])
    results = []
    search_text = edu_text if edu_text else text
    for line in search_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(kw.lower() in line.lower() for kw in EDUCATION_KEYWORDS):
            year_match = re.search(r"(19|20)\d{2}", line)
            results.append({
                "degree": line,
                "year": year_match.group(0) if year_match else "",
            })
    return results[:5]  # cap to avoid noise


def extract_experience(text):
    """
    Naive experience extraction: grabs the experience section and
    splits into rough entries. This is heuristic - it won't be perfect,
    but it gives the AI matching/generation step a solid base, and the
    user can refine via the edit-profile screen.
    """
    exp_text = extract_section(text, SECTION_HEADERS["experience"])
    if not exp_text:
        return []

    entries = []
    blocks = re.split(r"\n(?=[A-Z])", exp_text)  # split on lines starting with capital letter
    for block in blocks:
        block = block.strip()
        if len(block) < 10:
            continue
        date_match = re.search(
            r"(\d{4}\s*[-–to]+\s*(\d{4}|present|Present|Current))", block
        )
        entries.append({
            "raw": block[:500],
            "duration": date_match.group(0) if date_match else "",
        })
    return entries[:10]


def extract_contact_info(text):
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?\d{10}", text)
    return {
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
    }


def parse_resume(filepath):
    """
    Main entry point. Returns a dict ready to populate the Profile model.
    """
    raw_text = extract_raw_text(filepath)
    if not raw_text.strip():
        raise ValueError("Could not extract any text from this file. It may be a scanned image - try a text-based PDF or DOCX.")

    contact = extract_contact_info(raw_text)

    # Best-effort name guess: first non-empty line that isn't an email/phone
    name = ""
    for line in raw_text.split("\n"):
        line = line.strip()
        if line and "@" not in line and not re.search(r"\d{5,}", line):
            name = line
            break

    return {
        "full_name": name[:255],
        "phone": contact["phone"],
        "skills": extract_skills(raw_text),
        "experience": extract_experience(raw_text),
        "education": extract_education(raw_text),
        "raw_text": raw_text,
    }
