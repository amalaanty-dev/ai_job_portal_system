import os
import sys
import logging

# 1. Setup paths: Add the parent directory (project root) to sys.path
# This allows 'import skill_engine' to work from within the scripts folder.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# 2. Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def run_pipeline():
    try:
        # 3. Import the processing logic from your extractor
        from skill_engine.skill_extractor import process_resumes
        
        logger.info("🚀 Starting Skill Extraction Pipeline...")
        
        # 4. Define and verify input/output paths relative to project root
        input_dir = os.path.join(project_root, "data", "resumes", "parsed_resumes", "json")
        
        if not os.path.exists(input_dir):
            logger.error(f"Input directory not found: {input_dir}")
            return

        # 5. Execute the extraction engine
        process_resumes()
        
        logger.info("✅ Pipeline execution finished successfully.")
        
    except ImportError as e:
        logger.error(f"❌ Failed to import skill_engine: {e}")
        logger.info("Double-check that 'skill_engine/__init__.py' exists.")
    except Exception as e:
        logger.error(f"❌ Critical error during pipeline run: {e}")

if __name__ == "__main__":
    run_pipeline()