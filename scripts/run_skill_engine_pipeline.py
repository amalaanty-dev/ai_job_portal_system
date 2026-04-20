import os
import sys
import logging
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

def run_pipeline():
    try:
        from skill_engine.skill_extractor import extract_skills, calculate_weighted_confidence
        from skill_engine.skill_dictionary import get_skill_category
        
        input_dir = os.path.join(project_root, "data", "resumes", "sectioned_resumes")
        output_dir = os.path.join(project_root, "data", "extracted_skills")
        os.makedirs(output_dir, exist_ok=True)

        for file in os.listdir(input_dir):
            if not file.endswith("_sections.json"):
                continue

            with open(os.path.join(input_dir, file), "r", encoding="utf-8") as f:
                sections = json.load(f)

            # Process Experience for weighting
            exp_list = []
            for e in sections.get("experience", []):
                exp_list.append(e.get("role_header", ""))
                exp_list.extend(e.get("duties", []))
            
            sec_texts = {
                "skills": " ".join(sections.get("skills", [])),
                "experience": " ".join(exp_list),
                "projects": " ".join(sections.get("projects", []))
            }

            combined_text = f"{sec_texts['skills']} {sec_texts['experience']} {sec_texts['projects']}"
            unique_skills = extract_skills(combined_text)

            results = []
            for s in unique_skills:
                results.append({
                    "skill": s,
                    "category": get_skill_category(s),
                    "confidence": calculate_weighted_confidence(s, sec_texts)
                })

            with open(os.path.join(output_dir, file.replace("_sections.json", "_skills.json")), "w") as f:
                json.dump({"candidate": file, "skills": results}, f, indent=4)
            
            logger.info(f"✅ Processed: {file}")
            
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")

if __name__ == "__main__":
    run_pipeline()