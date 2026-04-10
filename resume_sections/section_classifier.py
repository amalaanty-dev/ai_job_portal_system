import os
import re
import json

INPUT_FOLDER = "data/resumes/parsed_resumes/json/"
OUTPUT_FOLDER = "data/resumes/sectioned_resumes/"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

SECTION_PATTERNS = {

    "skills": [
        r"\bskills\b",
        r"\btechnical skills\b",
        r"\bcore competencies\b",
        r"\btechnologies\b"
    ],

    "experience": [
        r"\bexperience\b",
        r"\bwork experience\b",
        r"\bprofessional experience\b",
        r"\bemployment history\b"
    ],

    "education": [
        r"\beducation\b",
        r"\bacademic background\b",
        r"\bqualifications\b"
    ],

    "projects": [
        r"\bprojects\b",
        r"\bpersonal projects\b",
        r"\bacademic projects\b"
    ],

    "certifications": [
        r"\bcertifications\b",
        r"\blicenses\b",
        r"\bprofessional certifications\b"
    ]
}


def detect_section(line):

    for section, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, line.lower()):
                return section

    return None

def segment_resume(text):

    # recreate section breaks if text is one long line
    text = re.sub(
        r'(skills|technical skills|core competencies|technologies|'
        r'experience|work experience|professional experience|employment history|'
        r'education|academic background|qualifications|'
        r'projects|personal projects|academic projects|'
        r'certifications|licenses|professional certifications)',
        r'\n\1\n',
        text,
        flags=re.IGNORECASE
    )

    lines = text.split("\n")

    sections = {
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "other": []
    }

    current_section = "other"

    for line in lines:

        line = line.strip()

        if not line:
            continue

        detected = detect_section(line)

        if detected:
            current_section = detected
            continue

        sections[current_section].append(line)

    return sections



def process_resumes():

    for file in os.listdir(INPUT_FOLDER):

        if not file.endswith(".json"):
            continue

        file_path = os.path.join(INPUT_FOLDER, file)

        with open(file_path, "r", encoding="utf-8") as f:
            parsed_data = json.load(f)

        resume_text = parsed_data.get("clean_text", "")

        sections = segment_resume(resume_text)

        output_file = file.replace(".json", "_sections.json")

        with open(os.path.join(OUTPUT_FOLDER, output_file), "w") as f:
            json.dump(sections, f, indent=4)

        print("Processed:", file)


if __name__ == "__main__":
    process_resumes()
