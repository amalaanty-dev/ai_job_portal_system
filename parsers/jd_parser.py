import re
import json
import os
import glob

SKILLS_DB = [
    "python","sql","excel","tableau","power bi",
    "machine learning","data visualization","statistics",
    "r","sas","tensorflow","pytorch"
]

ROLE_DB = [
    "healthcare data analyst (junior)",
    "clinical data analyst",
    "healthcare reporting analyst",
    "medical data analyst",
    "health information analyst",
    "data entry analyst (healthcare)",
    "public health data analyst (entry-level)",
    "ehr data analyst",
    "healthcare data analyst",
    "senior clinical data analyst",
    "healthcare business analyst",
    "population health analyst",
    "quality improvement analyst (healthcare)",
    "healthcare operations analyst",
    "revenue cycle data analyst",
    "healthcare performance analyst",
    "Healthcare BI (Business Intelligence) Analyst",
    "claims data analyst",
    "senior healthcare data analyst",
    "lead data analyst (healthcare)",
    "healthcare analytics manager",
    "healthcare data science manager",
    "director of healthcare analytics",
    "chief data officer",
    "head of health informatics",
    "healthcare data scientist",
    "clinical data scientist",
    "healthcare machine learning engineer",
    "ai specialist in healthcare analytics",
    "predictive analytics specialist",
    "healthcare statistician",
    "biostatistician",
    "clinical research data analyst",
    "clinical trials data manager",
    "epidemiologist",
    "healthcare outcomes analyst",
    "Real-World Evidence (RWE) Analyst",
    "health informatics specialist",
    "clinical informatics analyst",
    "healthcare data integration specialist",
    "ehr implementation analyst",
    "healthcare data architect",
    "health information systems analyst",
    "healthcare financial analyst",
    "medical billing data analyst",
    "insurance claims analyst",
    "revenue cycle analyst",
    "cost & utilization analyst",
    "public health analyst",
    "health policy analyst",
    "epidemiology data analyst",
    "healthcare program analyst",
    "global health data analyst",
    "digital health analyst",
    "telehealth data analyst",
    "healthcare ai analyst",
    "patient experience analyst",
    "healthcare risk analyst",
    "fraud & compliance analyst",
    "wearable health data analyst",
    "genomics data analyst",
    "freelance healthcare data analyst",
    "healthcare analytics consultant",
    "data analytics trainer",
    "healthcare dashboard developer",
    "remote clinical data analyst"
]

EDUCATION_DB = [
    "bachelor",
    "master",
    "phd",
    "degree"
]


def normalize_text(text):
    return text.lower()


def extract_role(text):
    # Normalize both text and role to lowercase, collapse multiple spaces
    def clean(s):
        s = s.lower()
        s = s.replace('-', ' ')                  # normalize hyphens to spaces
        s = re.sub(r'[^a-z0-9 ]', ' ', s)
        s = re.sub(r' +', ' ', s).strip()
        return s

    clean_text = clean(text)
    # Sort roles by length descending to match longest first
    for role in sorted(ROLE_DB, key=len, reverse=True):
        if clean(role) in clean_text:
            return role

    return "Unknown"

def extract_skills(text):
    found = []
    for skill in SKILLS_DB:
        if skill in text:
            found.append(skill)
    return found


def extract_experience(text):
    match = re.search(r"(\d+)\+?\s*years", text)
    if match:
        return match.group(1) + " years"
    return "Not specified"


def extract_education(text):
    for edu in EDUCATION_DB:
        if edu in text:
            return edu
    return "Not specified"


def parse_job_description(jd_text):
    jd_text = normalize_text(jd_text)
    job_object = {
        "role": extract_role(jd_text),
        "skills_required": extract_skills(jd_text),
        "experience_required": extract_experience(jd_text),
        "education_required": extract_education(jd_text)
    }
    return job_object


# ======================
# Run parser for all JD TXT files
# ======================
if __name__ == "__main__":

    # Folder containing all JD TXT files
    jd_folder = "data/job_descriptions/jd_samples/"
    output_folder = "data/job_descriptions/parsed_jd/"
    os.makedirs(output_folder, exist_ok=True)

    # Get list of all .txt JD files
    jd_files = glob.glob(os.path.join(jd_folder, "*.txt"))

    if not jd_files:
        print("No JD files found in folder!")
        exit()

    # Process each JD file
    for jd_file in jd_files:
        with open(jd_file, "r", encoding="utf-8") as f:
            jd_text = f.read()

        parsed_jd = parse_job_description(jd_text)

        # Use role name for JSON file
        role_name = parsed_jd["role"].replace(" ", "_")
        output_file = os.path.join(output_folder, f"{role_name}_parsed_jd.json")

        # Save parsed JD
        with open(output_file, "w", encoding="utf-8") as outfile:
            json.dump(parsed_jd, outfile, indent=4)

        print(f"Parsed JD saved: {output_file}")
