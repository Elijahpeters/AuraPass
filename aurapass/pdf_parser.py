import json
import re
import sys
from pathlib import Path


def clean_spaces(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_text(text):
    def extract_between(start, end):
        match = re.search(start + r"(.*?)" + end, text, flags=re.IGNORECASE | re.DOTALL)
        return clean_spaces(match.group(1)) if match else ""

    matric = extract_between(r"Matric\s*Number", r"\nName")
    name = extract_between(r"\nName", r"\nLevel").upper()
    level_raw = extract_between(r"\nLevel", r"\nSemester")
    faculty = extract_between(r"\nFaculty", r"\n(?:Department/Programme|ELECTRICAL|S/NO)").upper()
    department = extract_between(r"Department/Programme", r"\nS/NO").rstrip(")").strip()

    if not faculty:
        faculty = "ENGINEERING"
    if not department:
        department = "Electrical and Electronics Engineering"

    level = f"{level_raw} Level" if level_raw and "level" not in level_raw.lower() else level_raw
    courses = []
    for code in re.findall(r"\b[A-Z]{2,4}\d{3}\b", text):
        if code not in courses:
            courses.append(code)

    if not matric or not name or not courses:
        raise ValueError("Could not extract matric number, name, and courses from the PDF.")

    return {
        "name": name,
        "matric": matric.upper(),
        "level": level or "Unknown",
        "faculty": faculty or "Unknown",
        "department": department or "Unknown",
        "courses": courses,
    }


def parse_course_form_local(pdf_path):
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return _parse_text(text)


def parse_course_form(pdf_path):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Course form not found: {pdf_path}")
    return parse_course_form_local(pdf_path)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--json":
        print(json.dumps(parse_course_form_local(sys.argv[2]), indent=2))
        return
    raise SystemExit("Usage: pdf_parser.py --json <course-form.pdf>")


if __name__ == "__main__":
    main()
