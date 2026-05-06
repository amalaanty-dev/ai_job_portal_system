"""
scripts/parse_test_jds.py
=========================
Parses the 11 raw .txt JDs in `data/job_descriptions/ats_test_jds/`
into JSON files in `data/job_descriptions/ats_test_parsed_jds/`.

Mirrors the JD parsing logic in main.py (uses your existing
parsers.jd_parser.parse_job_description function).

Run:
    python scripts/parse_test_jds.py

Day: 17
"""

import sys
import os
import glob
import json
import logging

# -------------------------------------------------------------------
# Resolve project root from THIS file's location (scripts/ -> parent)
# -------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS_DIR)

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s -- %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Import your existing JD parser
# -------------------------------------------------------------------
try:
    from parsers.jd_parser import parse_job_description
except ImportError as e:
    logger.error(f"Could not import parsers.jd_parser: {e}")
    logger.error("Make sure you run this script from the project root.")
    sys.exit(1)


# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
TEST_JD_RAW_DIR = os.path.join(_ROOT, "data", "job_descriptions", "ats_test_jds")
TEST_JD_PARSED_DIR = os.path.join(_ROOT, "data", "job_descriptions", "ats_test_parsed_jds")


def main():
    logger.info("=" * 70)
    logger.info("Day 17 - Parsing Test JDs")
    logger.info("=" * 70)

    # Ensure folders exist
    if not os.path.exists(TEST_JD_RAW_DIR):
        logger.error(f"Test JD folder not found: {TEST_JD_RAW_DIR}")
        logger.error("Create it and add your .txt JD files first.")
        return 1

    os.makedirs(TEST_JD_PARSED_DIR, exist_ok=True)

    jd_files = sorted(glob.glob(os.path.join(TEST_JD_RAW_DIR, "*.txt")))
    if not jd_files:
        logger.warning(f"No .txt files found in {TEST_JD_RAW_DIR}")
        return 1

    logger.info(f"Found {len(jd_files)} test JD .txt files")

    # Optional: clear old parsed files in test_parsed_jds (NOT in dev parsed_jd)
    for old_file in glob.glob(os.path.join(TEST_JD_PARSED_DIR, "*.json")):
        os.remove(old_file)
    logger.info("Cleared old test parsed JD files")

    success = 0
    failed = []
    for jd_file in jd_files:
        try:
            with open(jd_file, "r", encoding="utf-8") as f:
                jd_text = f.read()

            parsed_jd = parse_job_description(jd_text)

            file_name = os.path.basename(jd_file).replace(".txt", "")
            jd_output_file = os.path.join(
                TEST_JD_PARSED_DIR, f"{file_name}_parsed_jd.json"
            )

            with open(jd_output_file, "w", encoding="utf-8") as outfile:
                json.dump(parsed_jd, outfile, indent=4)

            logger.info(f"  [OK] {os.path.basename(jd_file)} -> {os.path.basename(jd_output_file)}")
            success += 1

        except Exception as e:
            logger.error(f"  [FAIL] {os.path.basename(jd_file)}: {e}")
            failed.append(os.path.basename(jd_file))

    logger.info("-" * 70)
    logger.info(f"Parsed {success}/{len(jd_files)} test JDs")
    if failed:
        logger.warning(f"Failed: {failed}")
    logger.info(f"Output: {TEST_JD_PARSED_DIR}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
