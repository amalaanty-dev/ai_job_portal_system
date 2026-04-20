import os
import json
import sys

# ----------------------------
# FIX MODULE PATH
# ----------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from education_engine.education_parser import extract_education
from education_engine.education_formatter import format_academic_profile
from education_engine.education_matcher import calculate_education_relevance


# ----------------------------
# PATH CONFIG
# ----------------------------
RESUME_PATH = "data/resumes/sectioned_resumes/"
JD_PATH = "data/job_descriptions/parsed_jd/"

OUTPUT_DIR = "data/education_outputs/"
OUTPUT_FILE = "education_output.json"


# ----------------------------
# HELPER: RESUME INPUT
# ----------------------------
def get_resume_education_text(resume_json):
    """
    Handles both string and list education formats
    """

    education = resume_json.get("education")

    # If list → join into single string
    if isinstance(education, list):
        return " ".join(education).strip()

    # If string → clean
    if isinstance(education, str):
        return education.strip()

    # Fallback
    full_text = resume_json.get("full_text")
    if isinstance(full_text, str):
        return full_text[:2000].strip()

    return ""



# ----------------------------
# HELPER: JD INPUT (FIXED)
# ----------------------------
def build_jd_education_text(jd_json):

    parts = []

    # EDUCATION
    education = jd_json.get("education")
    if isinstance(education, list):
        parts.append(" ".join(education))
    elif isinstance(education, str):
        parts.append(education)

    # ROLE
    role = jd_json.get("role")
    if isinstance(role, list):
        parts.append(" ".join(role))
    elif isinstance(role, str):
        parts.append(role)

    # SKILLS
    skills = jd_json.get("required_skills", [])
    if isinstance(skills, list):
        parts.append(" ".join(skills[:10]))
    elif isinstance(skills, str):
        parts.append(skills)

    return " ".join(parts).strip().lower()


# ----------------------------
# MAIN PIPELINE
# ----------------------------
def run_education_pipeline(resume_json, jd_json):

    # CLEAN INPUTS
    resume_education_text = get_resume_education_text(resume_json)
    jd_text = build_jd_education_text(jd_json)

    # WARNINGS
    if not resume_education_text:
        print("⚠️ Warning: No education section found in resume")

    if not jd_text:
        print("⚠️ Warning: JD content is weak or missing education info")

    # STEP 1: PARSE
    parsed_education = extract_education(resume_education_text)

    # STEP 2: FORMAT
    formatted_education = format_academic_profile(parsed_education)

    # STEP 3: MATCH
    education_relevance = calculate_education_relevance(
        formatted_education,
        jd_text
    )

    # FINAL OUTPUT
    output = {
        "education_data": formatted_education,
        "education_relevance_score": education_relevance
    }

    return output


# ----------------------------
# EXECUTION BLOCK
# ----------------------------
if __name__ == "__main__":

    # ----------------------------
    # LOAD RESUME FILE
    # ----------------------------
    resume_files = [f for f in os.listdir(RESUME_PATH) if f.endswith(".json")]
    resume_files.sort()

    if not resume_files:
        raise Exception("❌ No JSON resume files found in sectioned_resumes")

    resume_file_path = os.path.join(RESUME_PATH, resume_files[0])

    try:
        with open(resume_file_path, "r", encoding="utf-8") as f:
            resume_json = json.load(f)
    except json.JSONDecodeError:
        raise Exception(f"❌ Invalid JSON in resume file: {resume_files[0]}")

    print(f"📄 Using Resume: {resume_files[0]}")


    # ----------------------------
    # LOAD JD FILE
    # ----------------------------
    jd_files = [f for f in os.listdir(JD_PATH) if f.endswith(".json")]
    jd_files.sort()

    if not jd_files:
        raise Exception("❌ No JSON JD files found in parsed_jd")

    jd_file_path = os.path.join(JD_PATH, jd_files[0])

    try:
        with open(jd_file_path, "r", encoding="utf-8") as f:
            jd_json = json.load(f)
    except json.JSONDecodeError:
        raise Exception(f"❌ Invalid JSON in JD file: {jd_files[0]}")

    print(f"📄 Using JD: {jd_files[0]}")


    # ----------------------------
    # RUN PIPELINE
    # ----------------------------
    result = run_education_pipeline(resume_json, jd_json)

    # ----------------------------
    # SAVE OUTPUT
    # ----------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("✅ Education pipeline completed successfully")
    print(f"📂 Output saved at: {output_path}")
    print(f"🎯 Education Relevance Score: {result['education_relevance_score']}")