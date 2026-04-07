import os
import re
import pdfplumber

# -----------------------------
# INPUT PDF
# -----------------------------
pdf_path = "tests/Healthcare Data Analyst Models.pdf"

# -----------------------------
# OUTPUT DIRECTORY
# -----------------------------
output_folder = "data/job_descriptions/jd_samples"
os.makedirs(output_folder, exist_ok=True)

# -----------------------------
# EXTRACT TEXT FROM PDF
# -----------------------------
full_text = ""

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

# -----------------------------
# SPLIT JOB DESCRIPTIONS
# -----------------------------
jd_list = re.split(r"\n(?=\d+\.\s)", full_text)
jd_list = [jd.strip() for jd in jd_list if jd.strip()]

print("Total JD found:", len(jd_list))

# -----------------------------
# FUNCTION TO CLEAN FILE NAME
# -----------------------------
def clean_filename(title):
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", "_", title)
    return title[:80]

# -----------------------------
# SAVE EACH JD
# -----------------------------
for jd in jd_list:

    lines = jd.split("\n")

    # First line usually contains number + job title
    first_line = lines[0]

    # Remove numbering (example: "1. Healthcare Data Analyst")
    title = re.sub(r"^\d+\.\s*", "", first_line)

    file_name = clean_filename(title) + ".txt"
    file_path = os.path.join(output_folder, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(jd)

print("✅ JD TXT files created successfully!")
print("📂 Location:", output_folder)