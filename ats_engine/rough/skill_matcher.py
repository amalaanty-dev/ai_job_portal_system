def match_skills(resume_skills, job_skills):
    """
    Find matching skills between resume and job description
    """

    resume_set = set(resume_skills)
    job_set = set(job_skills)

    matched_skills = resume_set.intersection(job_set)

    return list(matched_skills)