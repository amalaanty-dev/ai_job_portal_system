from ats_engine.skill_matcher import match_skills


def ats_score(resume_skills, job_skills):
    """
    Calculate ATS score based on skill match percentage
    """

    matched = match_skills(resume_skills, job_skills)

    if len(job_skills) == 0:
        return 0

    score = (len(matched) / len(job_skills)) * 100

    return round(score, 2)