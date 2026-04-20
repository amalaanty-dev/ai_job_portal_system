from utils.logger import log_event
from parsers.resume_text_extractor import process_resume_folder
from parsers.jd_parser import parse_job_description

import os
import glob
import json


# 🔹 Start System
log_event("System started")
print("AI Job Portal System Started")


# =========================
# 🔹 Resume Text Extraction
# =========================
input_folder = "data/resumes/raw_resumes/"
output_folder = "data/extracted_text/"

process_resume_folder(input_folder, output_folder)

print("Resume extraction completed")


# =========================
# 🔹 Job Description Parsing
# =========================
jd_folder = "data/job_descriptions/jd_samples/"
parsed_jd_folder = "data/job_descriptions/parsed_jd/"

# ✅ Clear old parsed files
if os.path.exists(parsed_jd_folder):
    for old_file in glob.glob(os.path.join(parsed_jd_folder, "*.json")):
        os.remove(old_file)
    print("Cleared old parsed files.")

os.makedirs(parsed_jd_folder, exist_ok=True)

jd_files = glob.glob(os.path.join(jd_folder, "*.txt"))

for jd_file in jd_files:
    with open(jd_file, "r", encoding="utf-8") as f:
        jd_text = f.read()

    parsed_jd = parse_job_description(jd_text)

    # ✅ Use JD filename
    file_name = os.path.basename(jd_file).replace(".txt", "")
    jd_output_file = os.path.join(parsed_jd_folder, f"{file_name}_parsed_jd.json")

    with open(jd_output_file, "w", encoding="utf-8") as outfile:
        json.dump(parsed_jd, outfile, indent=4)

    print(f"Saved: {jd_output_file}")