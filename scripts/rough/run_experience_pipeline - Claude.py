import json
import os
import glob
import sys
import logging
from pathlib import Path

# Fix Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experience_engine.experience_formatter import format_day10_output
from experience_engine.experience_parser    import extract_experience
from experience_engine.experience_matcher   import build_experience_summary
from experience_engine.experience_cleaner   import clean_experiences

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
RESUME_FOLDER = os.getenv("RESUME_FOLDER", "data/resumes/sectioned_resumes/")
JD_FOLDER     = os.getenv("JD_FOLDER",     "data/job_descriptions/parsed_jd/")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "data/experience_outputs/")

# ── All known experience key variants (sectioned resume formats) ──────
_EXP_KEYS = [
    "experience_section",
    "experience",
    "work_experience",
    "professional_experience",
    "employment_history",
    "work_history",
    "jobs",
    "positions",
]

# ── All known JD role key variants ────────────────────────────────────
_JD_ROLE_KEYS = [
    "role",
    "roles",
    "required_roles",
    "job_roles",
    "position",
    "positions",
    "job_title",
    "titles",
]

# ── All known JD skill key variants ───────────────────────────────────
_JD_SKILL_KEYS = [
    "required_skills",
    "skills",
    "skill_requirements",
    "technical_skills",
    "competencies",
    "key_skills",
]

# ── Required keys for pre-structured experience dicts ─────────────────
_REQUIRED_EXP_KEYS = {"job_title", "company", "start_date", "end_date"}


# ── Helper: resolve experience field from any key variant ─────────────
def _resolve_exp_field(resume_data: dict) -> tuple:
    """
    Try all known experience key variants in order.

    Returns:
        (field_value, matched_key) or ([], None) if nothing found.
    """
    for key in _EXP_KEYS:
        val = resume_data.get(key)
        if val:
            return val, key
    return [], None


# ── Helper: resolve JD roles from any key variant ─────────────────────
def _resolve_jd_roles(jd_data: dict) -> tuple:
    """
    Try all known JD role key variants in order.

    Returns:
        (roles_list, matched_key) or ([], None) if nothing found.
    """
    for key in _JD_ROLE_KEYS:
        val = jd_data.get(key)
        if val:
            roles = [val] if isinstance(val, str) else list(val)
            return roles, key
    return [], None


# ── Helper: resolve JD skills from any key variant ────────────────────
def _resolve_jd_skills(jd_data: dict) -> list:
    """
    Try all known JD skill key variants in order.

    Returns a flat list of skill strings, or [] if none found.
    When empty, the skill component is simply omitted from scoring
    rather than zeroing the whole score.
    """
    for key in _JD_SKILL_KEYS:
        val = jd_data.get(key)
        if val:
            return [val] if isinstance(val, str) else list(val)
    return []


# ── MAIN ──────────────────────────────────────────────────────────────
def main():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # ── Load file lists ───────────────────────────────────────────────
    resume_files = glob.glob(os.path.join(RESUME_FOLDER, "*.json"))
    jd_files     = glob.glob(os.path.join(JD_FOLDER,     "*.json"))

    if not resume_files:
        logger.error("❌ No resume JSON files found in: %s", RESUME_FOLDER)
        sys.exit(1)

    if not jd_files:
        logger.error("❌ No JD JSON files found in: %s", JD_FOLDER)
        sys.exit(1)

    logger.info("📄 Found %d resume(s) and %d JD(s)\n", len(resume_files), len(jd_files))

    # ── Pre-load all JDs once (avoid N×M disk reads) ──────────────────
    jd_cache: dict = {}

    for jd_file in jd_files:
        jd_name = Path(jd_file).stem
        try:
            with open(jd_file, encoding="utf-8") as f:
                jd_cache[jd_name] = json.load(f)
        except Exception as e:
            logger.warning("❌ Could not load JD '%s': %s", jd_name, e)

    if not jd_cache:
        logger.error("❌ All JD files failed to load — aborting")
        sys.exit(1)

    # ── Pre-validate JDs once — avoids inflating skipped N×M ─────────
    invalid_jds: set = set()

    for jd_name, jd_data in jd_cache.items():
        roles, _ = _resolve_jd_roles(jd_data)
        if not roles:
            logger.warning(
                "⚠️ JD '%s' — no roles key found. Available keys: %s",
                jd_name, list(jd_data.keys()),
            )
            invalid_jds.add(jd_name)

    if invalid_jds:
        logger.warning("⚠️ %d JD(s) skipped — no roles key: %s", len(invalid_jds), invalid_jds)

    # ── Counters ──────────────────────────────────────────────────────
    processed    = 0
    skipped      = 0
    empty_result = 0

    # ── MAIN LOOP ─────────────────────────────────────────────────────
    for resume_file in resume_files:
        resume_name = Path(resume_file).stem

        # Load resume
        try:
            with open(resume_file, encoding="utf-8") as f:
                resume_data = json.load(f)
        except Exception as e:
            logger.warning("❌ Could not load resume '%s': %s", resume_name, e)
            skipped += 1
            continue

        # ── Resolve experience field ───────────────────────────────────
        resume_exp, matched_key = _resolve_exp_field(resume_data)

        if not matched_key:
            logger.warning(
                "❌ '%s' — no experience key found. Available keys: %s",
                resume_name, list(resume_data.keys()),
            )
            skipped += 1
            continue

        logger.debug("🔑 '%s' — experience key resolved: '%s'", resume_name, matched_key)

        # ── Handle all input shapes ───────────────────────────────────
        if isinstance(resume_exp, list):

            if resume_exp and isinstance(resume_exp[0], dict):
                # Already structured — validate required keys
                raw_experiences = [
                    e for e in resume_exp
                    if _REQUIRED_EXP_KEYS.issubset(e)
                ]
                dropped = len(resume_exp) - len(raw_experiences)
                if dropped:
                    logger.warning(
                        "⚠️ '%s' — dropped %d entr%s missing required keys %s",
                        resume_name, dropped,
                        "y" if dropped == 1 else "ies",
                        _REQUIRED_EXP_KEYS,
                    )
                # ── Clean sectioner bleed-in from structured dicts ────
                experiences = clean_experiences(raw_experiences)

            else:
                # List of strings → join → parse (regex path; no cleaning needed)
                combined_text = "\n".join(str(e) for e in resume_exp)
                experiences   = extract_experience(combined_text)

        elif isinstance(resume_exp, str):
            # Raw text → parse (regex path; no cleaning needed)
            experiences = extract_experience(resume_exp)

        else:
            logger.warning(
                "⚠️ '%s' — unrecognised experience field type: %s",
                resume_name, type(resume_exp),
            )
            experiences = []

        # ── Early exit — no point running through every JD ────────────
        if not experiences:
            logger.warning(
                "⚠️ '%s' — no valid experiences after cleaning; skipping all JDs",
                resume_name,
            )
            skipped += 1
            continue

        # ── JD LOOP ───────────────────────────────────────────────────
        for jd_name, jd_data in jd_cache.items():

            if jd_name in invalid_jds:
                continue

            jd_roles, _ = _resolve_jd_roles(jd_data)
            jd_skills   = _resolve_jd_skills(jd_data)

            if not jd_skills:
                logger.debug(
                    "ℹ️  '%s' — no skills key found; skill component skipped in scoring",
                    jd_name,
                )

            # Build summary
            try:
                summary      = build_experience_summary(experiences, jd_roles, jd_skills)
                final_output = format_day10_output(experiences, summary)
            except Exception as e:
                logger.warning(
                    "❌ build_experience_summary failed (%s × %s): %s",
                    resume_name, jd_name, e,
                )
                skipped += 1
                continue

            score    = final_output["relevance_analysis"]["overall_relevance_score"]
            months   = final_output["experience_summary"]["total_experience_months"]
            gaps     = final_output["timeline_analysis"]["gaps"]
            overlaps = final_output["timeline_analysis"]["overlaps"]

            # ── Detect empty summary BEFORE writing to disk ───────────
            is_empty = (score == 0.0 and months == 0 and not gaps and not overlaps)

            if is_empty:
                logger.warning(
                    "⚠️ %s × %s → empty summary — experiences=%d | jd_roles=%d"
                    " | check keys/date format",
                    resume_name, jd_name, len(experiences), len(jd_roles),
                )
                empty_result += 1
                continue

            # Write output
            output_file = os.path.join(
                OUTPUT_FOLDER,
                f"{resume_name}_vs_{jd_name}_experience.json",
            )

            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(final_output, f, indent=4)
            except Exception as e:
                logger.warning(
                    "❌ Failed to write output for %s × %s: %s",
                    resume_name, jd_name, e,
                )
                skipped += 1
                continue

            logger.info(
                "✅ %s × %s → score=%.2f%% | months=%d | gaps=%d | overlaps=%d",
                resume_name, jd_name,
                score, months, len(gaps), len(overlaps),
            )

            processed += 1

    # ── SUMMARY ───────────────────────────────────────────────────────
    logger.info("─" * 60)
    logger.info("✅ Experience Pipeline Completed")
    logger.info("JDs Loaded   : %d", len(jd_cache))
    logger.info("Processed    : %d", processed)
    logger.info(
        "Empty Result : %d  ← fix resume/JD keys or date format if > 0",
        empty_result,
    )
    logger.info("Skipped      : %d", skipped)
    logger.info("Output       : %s", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()