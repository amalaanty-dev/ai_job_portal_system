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

nlp = spacy.load("en_core_web_sm")

# Point to your sectioned results
INPUT_FOLDER = "data/resumes/sectioned_resumes/"
OUTPUT_FOLDER = "data/extracted_skills/"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

MASTER_SKILLS = [s.lower() for s in MASTER_SKILLS_DB]

def correct_spelling(word):
    # Raise cutoff to 0.8 to stop 'learning' matching 'lean'
    matches = get_close_matches(word.lower(), MASTER_SKILLS, n=1, cutoff=0.8)
    return matches[0] if matches else None

def extract_skills(text):
    text = f" {text.lower()} " 
    clean_text = re.sub(r'[,./;:]', ' ', text)
    skills_found = []

    # 1. Exact Phrase Match (The most reliable)
    for skill in MASTER_SKILLS:
        if f" {skill} " in f" {clean_text} ":
            skills_found.append(skill)

    # 2. Synonym Matching (Captures ML, AI, etc.)
    for abbr, full_name in SKILL_SYNONYMS.items():
        if f" {abbr.lower()} " in f" {clean_text} ":
            skills_found.append(full_name.lower())

    # 3. Spelling Check (Only for words > 4 chars to avoid noise)
    words = re.findall(r'\b\w+\b', clean_text)
    for word in words:
        if len(word) > 4:
            corrected = correct_spelling(word)
            if corrected:
                skills_found.append(corrected)

    return list(set(skills_found))

#ADDED
def calculate_weighted_confidence(skill, section_texts):
    """
    Calculates confidence based on frequency and professional context.
    - Base frequency: 1=0.75, 2=0.85, 3+=0.95
    - Bonus: +0.1 if skill is in Experience or Projects
    """
    # 1. Identify the professional context (Experience/Projects)
    if isinstance(section_texts, dict):
        full_text = " ".join(section_texts.values()).lower()
        # The key change: Checking specific high-value sections for the bonus
        in_work = (skill in section_texts.get("experience", "").lower() or 
                   skill in section_texts.get("projects", "").lower())
    else:
        # Fallback for raw text input
        full_text = section_texts.lower()
        in_work = False

    # 2. Base Frequency Calculation
    count = full_text.count(skill)
    if count >= 3:
        score = 0.95
    elif count == 2:
        score = 0.85
    else:
        score = 0.75
        
    # 3. Apply the 'In-Work' Bonus
    if in_work:
        # min(0.95, ...) ensures we don't exceed the max confidence cap
        score = min(0.95, score + 0.1)
        
    return round(score, 2)

def process_resumes():
    for file in os.listdir(INPUT_FOLDER):
        if not file.endswith("_sections.json"): continue
        
        with open(os.path.join(INPUT_FOLDER, file), "r", encoding="utf-8") as f:
            sections = json.load(f)

        # Correctly join the sections from Amala's JSON structure
        sec_texts = {
            "skills": " ".join(sections.get("skills", [])),
            "experience": " ".join([f"{e['role_header']} {' '.join(e['duties'])}" for e in sections.get("experience", [])]),
            "projects": " ".join(sections.get("projects", [])),
        }
        
        combined_text = f"{sec_texts['skills']} {sec_texts['experience']} {sec_texts['projects']}"
        extracted = extract_skills(combined_text)

        results = []
        for s in extracted:
            results.append({
                "skill": s,
                "category": get_skill_category(s),
                "confidence": calculate_confidence(s, sec_texts)
            })

        output_data = {
            "candidate": file.replace("_sections.json", ""),
            "skills": results
        }

        with open(os.path.join(OUTPUT_FOLDER, file.replace("_sections.json", "_skills.json")), "w") as f:
            json.dump(output_data, f, indent=4)
        print(f"✅ Processed {file}")

if __name__ == "__main__":
    process_resumes()