from utils.logger import log_event

log_event("System started")
print("AI Job Portal System Started")

print("AI Job Portal System Started")

from parsers.resume_text_extractor import process_resume_folder

input_folder = "data/resumes"
output_file = "data/extracted_text/resume_text.json"

process_resume_folder(input_folder, output_file)

print("Resume extraction completed")



from parsers.jd_parser import parse_job_description

import os
import glob
import json

jd_folder = "data/job_descriptions/jd_samples/"
output_folder = "data/job_descriptions/parsed_jd/"

# ✅ Clear old parsed files first
if os.path.exists(output_folder):
    for old_file in glob.glob(os.path.join(output_folder, "*.json")):
        os.remove(old_file)
    print("Cleared old parsed files.")

os.makedirs(output_folder, exist_ok=True)

jd_files = glob.glob(os.path.join(jd_folder, "*.txt"))

for jd_file in jd_files:
    with open(jd_file, "r", encoding="utf-8") as f:
        jd_text = f.read()

    parsed_jd = parse_job_description(jd_text)

    # ✅ Use JD filename, not role name
    file_name = os.path.basename(jd_file).replace(".txt", "")
    output_file = os.path.join(output_folder, f"{file_name}_parsed_jd.json")

    with open(output_file, "w", encoding="utf-8") as outfile:
        json.dump(parsed_jd, outfile, indent=4)

    print(f"Saved: {output_file}")
