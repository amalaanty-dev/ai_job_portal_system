import json
import os

FOLDER = "data/resumes/parsed_resumes/json/"
files  = [f for f in os.listdir(FOLDER) if f.endswith(".json")]

for file in files:
    path = os.path.join(FOLDER, file)
    data = json.load(open(path, encoding="utf-8"))
    text = data.get("clean_text", "MISSING")

    print("=" * 70)
    print("FILE   :", file)
    print("TYPE   :", type(text).__name__)
    print("LENGTH :", len(str(text)))
    print()

    # Show full raw text so we can see ALL keywords present
    text_str = str(text).lower()

    # Check which section keywords are actually present
    keywords = [
        "skills", "technical skills", "core skills", "core competencies",
        "experience", "work experience", "professional experience",
        "employment history", "work history",
        "education", "projects", "certifications", "summary",
        "professional summary",
    ]

    print("SECTION KEYWORDS FOUND IN TEXT:")
    for kw in keywords:
        if kw in text_str:
            # Show context around the keyword
            idx = text_str.find(kw)
            ctx = text_str[max(0, idx-30):idx+len(kw)+30]
            print(f"  ✅ '{kw}' → ...{ctx}...")
        else:
            print(f"  ❌ '{kw}' — NOT FOUND")

    print()
    print("FIRST 1000 CHARS OF RAW TEXT:")
    print(repr(str(text)[:1000]))
    print()
