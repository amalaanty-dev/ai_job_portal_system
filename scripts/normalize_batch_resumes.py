"""
Normalize Batch Resumes (Day 15)
Path: ai_job_portal_system/scripts/normalize_batch_resumes.py

USAGE:
    python -m scripts.normalize_batch_resumes \
        --resumes_dir   data/parsed \
        --sections_dir  data/parsed_sections

Pairs each <name>.json with its <name>_sections.json (if present).
"""

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fairness_engine.resume_normalizer import ResumeNormalizer
from utils.fairness_utils import get_logger

logger = get_logger("normalize_batch")


def main():
    p = argparse.ArgumentParser(description="Batch normalize resumes")
    p.add_argument("--resumes_dir", required=True,
                   help="dir with parsed resume JSONs")
    p.add_argument("--sections_dir",
                   help="dir with section JSONs (optional)")
    p.add_argument("--output_dir", default="fairness_engine_outputs/normalized_resumes")
    args = p.parse_args()

    normalizer = ResumeNormalizer(output_dir=args.output_dir)
    resume_files = sorted(glob.glob(str(Path(args.resumes_dir) / "*.json")))
    resume_files = [f for f in resume_files if "_sections" not in f]

    if not resume_files:
        logger.error(f"No resume JSONs in {args.resumes_dir}")
        return

    success, failed = 0, 0
    for rf in resume_files:
        stem = Path(rf).stem
        sec = None
        if args.sections_dir:
            cand = Path(args.sections_dir) / f"{stem}_sections.json"
            if cand.exists():
                sec = str(cand)
        try:
            normalizer.normalize(rf, sec)
            success += 1
        except Exception as e:
            logger.error(f"Failed {rf}: {e}")
            failed += 1

    print(f"\nNormalized: {success} | Failed: {failed} "
          f"| Output: {args.output_dir}")


if __name__ == "__main__":
    main()
