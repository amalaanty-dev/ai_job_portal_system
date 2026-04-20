from datetime import datetime

DEGREE_PRIORITY = {
    "PHD": 1,
    "MBA": 2,
    "M.TECH": 3,
    "MSC": 4,
    "MCA": 5,
    "B.TECH": 6,
    "B.E": 6,
    "BSC": 7,
    "BBA": 8
}


def format_academic_profile(parsed):

    edu = parsed.get("education", [])
    cert = parsed.get("certifications", [])

    return {
        "academic_profile": {
            "highest_degree": get_highest(edu),
            "total_degrees": len(edu),
            "latest_graduation_year": get_year_range(edu),
            "certification_count": len(cert),
            "education_strength": calculate_strength(edu, cert)
        },
        "education_details": edu,
        "certifications": cert
    }


# ----------------------------
# REQUIRED FOR FINAL SCORE
# ----------------------------
def calculate_education_relevance(edu_list, jd_text):

    if not edu_list:
        return 0

    highest = get_highest(edu_list)

    DEGREE_SCORE = {
        "PHD": 100,
        "MBA": 90,
        "M.TECH": 85,
        "MSC": 80,
        "B.TECH": 75,
        "B.E": 75,
        "BSC": 70,
        "BBA": 72
    }

    degree_score = DEGREE_SCORE.get(highest, 60)

    field_score = 70   # keep simple stable baseline (or enhance later NLP match)

    cert_score = 50    # no cert logic here for now

    return round(
        degree_score * 0.5 +
        field_score * 0.3 +
        cert_score * 0.2,
        2
    )


def get_year_range(edu_list):

    ranges = []

    for e in edu_list:
        y = e.get("graduation_year")

        if isinstance(y, str) and "-" in y:
            ranges.append(y)
        elif isinstance(y, str) and y.isdigit():
            ranges.append(y)

    if len(ranges) >= 2:
        return f"{ranges[0]}-{ranges[-1]}"

    if len(ranges) == 1:
        return ranges[0]

    return "UNKNOWN"


def get_highest(edu_list):

    for d in ["MBA", "M.TECH", "MSC", "B.TECH", "B.E", "BSC", "BBA"]:
        for e in edu_list:
            if e.get("degree") == d:
                return d

    return "UNKNOWN"


def calculate_strength(edu, cert):

    return round(
        len(edu) * 20 +
        len(cert) * 15 +
        40,
        2
    )