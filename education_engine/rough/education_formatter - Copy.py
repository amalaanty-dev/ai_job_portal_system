from datetime import datetime

# ----------------------------
# DEGREE PRIORITY (FOR SORTING)
# ----------------------------
DEGREE_PRIORITY = {
    "PHD": 1,
    "MBA": 2,
    "M.TECH": 3,
    "MSC": 4,
    "MASTER": 5,
    "MCA": 6,
    "B.TECH": 7,
    "B.E": 7,
    "BSC": 8,
    "BCA": 9,
    "BACHELOR": 10,
    "DIPLOMA": 11
}


# ----------------------------
# SORT EDUCATION (DEGREE + YEAR)
# ----------------------------
def sort_education(education_list):
    def sort_key(edu):
        degree = edu.get("degree", "")
        year = edu.get("graduation_year")

        degree_rank = DEGREE_PRIORITY.get(degree, 99)

        if year and str(year).isdigit():
            year_value = -int(year)   # latest first
        else:
            year_value = 0

        return (degree_rank, year_value)

    return sorted(education_list, key=sort_key)


# ----------------------------
# MAIN FORMATTER
# ----------------------------
def format_academic_profile(parsed_education):

    education_list = parsed_education.get("education", [])
    education_list = sort_education(education_list)

    certifications = parsed_education.get("certifications", [])

    return {
        "academic_profile": {
            "highest_degree": get_highest_degree(education_list),
            "total_degrees": len(education_list),
            "certification_count": len(certifications),
            "latest_graduation_year": get_latest_year(education_list),
            "education_strength": calculate_education_strength(
                education_list,
                certifications
            )
        },
        "education_details": education_list,
        "certifications": certifications
    }


# ----------------------------
# HELPERS
# ----------------------------
def get_highest_degree(education_list):

    PRIORITY_ORDER = list(DEGREE_PRIORITY.keys())

    degrees = [
        edu.get("degree", "").upper()
        for edu in education_list
        if edu.get("degree")
    ]

    for p in PRIORITY_ORDER:
        if p in degrees:
            return p

    return "UNKNOWN"


def get_latest_year(education_list):

    years = []

    for edu in education_list:
        year = edu.get("graduation_year")

        if year and str(year).isdigit():
            years.append(int(year))

    return max(years) if years else "UNKNOWN"


# ----------------------------
# EDUCATION STRENGTH
# ----------------------------
def calculate_education_strength(education_list, certifications):

    DEGREE_SCORE_MAP = {
        "PHD": 100,
        "MBA": 90,
        "M.TECH": 85,
        "MSC": 80,
        "MASTER": 80,
        "MCA": 80,
        "B.TECH": 75,
        "B.E": 75,
        "BSC": 70,
        "BCA": 70,
        "BACHELOR": 70,
        "DIPLOMA": 60
    }

    # ----------------------------
    # DEGREE SCORE (50%)
    # ----------------------------
    highest_degree = get_highest_degree(education_list)
    degree_score = DEGREE_SCORE_MAP.get(highest_degree, 50)

    # ----------------------------
    # CERTIFICATION SCORE (30%)
    # ----------------------------
    cert_count = len(certifications)

    if cert_count == 0:
        cert_score = 0
    elif cert_count == 1:
        cert_score = 50
    elif cert_count == 2:
        cert_score = 70
    else:
        cert_score = 90

    # ----------------------------
    # RECENCY SCORE (20%)
    # ----------------------------
    latest_year = get_latest_year(education_list)

    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        current_year = datetime.now().year
        gap = current_year - latest_year

        if gap <= 2:
            recency_score = 100
        elif gap <= 5:
            recency_score = 80
        elif gap <= 10:
            recency_score = 60
        else:
            recency_score = 40

    # ----------------------------
    # FINAL SCORE
    # ----------------------------
    final_strength = (
        degree_score * 0.5 +
        cert_score * 0.3 +
        recency_score * 0.2
    )

    return round(final_strength, 2)