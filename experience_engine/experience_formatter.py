def format_day10_output(experiences: list, summary: dict) -> dict:
    """
    Transform raw experience entries and a summary dict into the
    standardised Day-10 output schema.

    Parameters
    ----------
    experiences : list of dicts produced by extract_experience() or
                  extract_from_role_headers() or the parsed resume roles list
    summary     : dict produced by build_experience_summary()

    Returns
    -------
    {
        "experience_summary":  { "total_experience_months": int },
        "roles":               [ { company, job_title, start_date,
                                   end_date, duration_months } ],
        "timeline_analysis":   { "gaps": [...], "overlaps": [...] },
        "relevance_analysis":  { "overall_relevance_score": float }
    }
    """
    return {
        "experience_summary": {
            "total_experience_months": summary.get("total_experience_months", 0),
        },

        "roles": [
            {
                "company":         exp.get("company", ""),
                "job_title":       exp.get("job_title", ""),
                "start_date":      exp.get("start_date", ""),
                "end_date":        exp.get("end_date", ""),
                "duration_months": exp.get("duration_months", 0),
            }
            for exp in experiences
        ],

        "timeline_analysis": {
            "gaps":     summary.get("gaps", []),
            "overlaps": summary.get("overlaps", []),
        },

        "relevance_analysis": {
            "overall_relevance_score": summary.get("relevance_score", 0.0),
        },
    }
