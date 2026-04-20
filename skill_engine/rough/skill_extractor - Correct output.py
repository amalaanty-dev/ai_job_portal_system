import os
import json
import re
from difflib import get_close_matches
import spacy

from skill_engine.skill_dictionary import (
    MASTER_SKILLS_DB,
    SKILL_SYNONYMS,
    SKILL_STACKS,
    normalize_skill,
    get_skill_category
)

# -------------------------------
# Load NLP model
# -------------------------------
nlp = spacy.load("en_core_web_sm")

INPUT_FOLDER = "data/resumes/parsed_resumes/json/"
OUTPUT_FOLDER = "data/extracted_skills/"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

MASTER_SKILLS = MASTER_SKILLS_DB


# -------------------------------
# Detect skill stacks (MERN/MEAN)
# -------------------------------
def detect_skill_stacks(text):

    found = []

    for stack, skills in SKILL_STACKS.items():
        if stack in text:
            found.extend(skills)

    return found


# -------------------------------
# Spelling correction
# -------------------------------
def correct_spelling(word):

    matches = get_close_matches(word, MASTER_SKILLS, n=1, cutoff=0.8)

    if matches:
        return matches[0]

    return None


# -------------------------------
# NLP-based entity extraction
# -------------------------------
def extract_entities_nlp(text):

    doc = nlp(text)
    entities = []

    for ent in doc.ents:
        word = ent.text.lower().strip()

        # Keep only valid skills
        if word in MASTER_SKILLS:
            entities.append(word)

    return entities


# -------------------------------
# Main skill extraction
# -------------------------------
def extract_skills(text):

    text = text.lower()
    words = re.findall(r'\b\w+\b', text)

    skills_found = []

    # 1️⃣ Exact phrase matching
    for skill in MASTER_SKILLS:
        pattern = r"\b" + re.escape(skill) + r"\b"

        if re.search(pattern, text):
            skills_found.append(skill)

    # 2️⃣ Spelling correction
    for word in words:
        corrected = correct_spelling(word)

        if corrected:
            skills_found.append(corrected)

    # 3️⃣ Skill stacks (MERN/MEAN)
    skills_found.extend(detect_skill_stacks(text))

    # 4️⃣ NLP entity extraction
    skills_found.extend(extract_entities_nlp(text))

    # 5️⃣ Normalize + filter valid skills
    normalized = []

    for skill in skills_found:
        skill = normalize_skill(skill)

        if skill in MASTER_SKILLS:
            normalized.append(skill)

    return list(set(normalized))


# -------------------------------
# Confidence scoring
# -------------------------------
def skill_confidence(skill, text):

    count = text.count(skill)

    if count >= 3:
        return 0.95
    elif count == 2:
        return 0.85
    else:
        return 0.75


# -------------------------------
# Process all resumes
# -------------------------------
def process_resumes():

    for file in os.listdir(INPUT_FOLDER):

        if not file.endswith(".json"):
            continue

        file_path = os.path.join(INPUT_FOLDER, file)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        text = data.get("clean_text", "")

        if not text:
            print("No text found in:", file)
            continue

        skills = extract_skills(text)

        structured_output = []

        for skill in skills:

            confidence = skill_confidence(skill, text)

            structured_output.append({
                "skill": skill,
                "category": get_skill_category(skill),
                "confidence": confidence
            })

        output = {
            "candidate": file.replace(".json", ""),
            "skills": structured_output
        }

        output_file = file.replace(".json", "_skills.json")

        with open(os.path.join(OUTPUT_FOLDER, output_file), "w") as f:
            json.dump(output, f, indent=4)

        print("Extracted skills for:", file)


# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    process_resumes()
