def format_day10_output(experiences, summary):
    return {
        "experience_summary": {
            "total_experience_months": summary.get("total_experience_months", 0)
        },

        "roles": [
            {
                "company": exp.get("company", ""),
                "job_title": exp.get("job_title", ""),
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", ""),
                "duration_months": exp.get("duration_months", 0)
            }
            for exp in experiences
        ],

        "timeline_analysis": {
            "gaps": summary.get("gaps", []),
            "overlaps": summary.get("overlaps", [])
        },

        "relevance_analysis": {
            "overall_relevance_score": summary.get("relevance_score", 0.0)
        }
    }