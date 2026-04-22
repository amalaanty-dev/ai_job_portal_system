"""
data/sample_data.py
────────────────────
Realistic inline sample data for Day 12 testing.
Covers 5 job types: Data Analyst, Software Engineer, Healthcare DA,
                    Marketing Manager, Mechanical Engineer.
Each sample contains structured resume sections + a JD.
No file I/O required.
"""

# ═══════════════════════════════════════════════════════════════
# SAMPLE RESUMES  (structured sections)
# ═══════════════════════════════════════════════════════════════

SAMPLE_RESUMES = [

    # ── 1. Data Analyst ───────────────────────────────────────
    {
        "id": "resume_da_001",
        "name": "Amala Rajan",
        "target_role": "Data Analyst",
        "skills": [
            "Python", "SQL", "Tableau", "Power BI", "Excel",
            "pandas", "NumPy", "data cleaning", "ETL",
            "statistical analysis", "data visualisation",
            "MySQL", "PostgreSQL", "Google Analytics"
        ],
        "experience_summary": (
            "MBA graduate with 4 years of experience in data analytics and business "
            "intelligence. Proven track record in transforming raw data into actionable "
            "insights using Python, SQL, and Tableau. Delivered dashboards for C-suite "
            "stakeholders reducing reporting time by 40%. Strong background in finance "
            "and marketing analytics."
        ),
        "projects": [
            "Built an end-to-end sales forecasting pipeline using Python and ARIMA models, "
            "reducing forecast error by 22%.",
            "Designed interactive Power BI dashboards for monthly KPI tracking across 5 "
            "business units.",
            "Automated data ingestion from 12 source systems using SQL stored procedures "
            "and Python scripts, saving 10 hours of manual effort per week.",
        ],
        "education": "MBA – Finance & Marketing, Rajagiri College of Social Sciences, 2018",
        "certifications": ["Google Data Analytics Professional Certificate – Coursera, 2023"],
    },

    # ── 2. Software Engineer ──────────────────────────────────
    {
        "id": "resume_se_001",
        "name": "Rahul Menon",
        "target_role": "Software Engineer",
        "skills": [
            "Python", "Java", "Spring Boot", "REST API", "Microservices",
            "Docker", "Kubernetes", "AWS", "CI/CD", "Jenkins",
            "PostgreSQL", "Redis", "Git", "Agile", "Scrum"
        ],
        "experience_summary": (
            "B.Tech Computer Science graduate with 3 years of software engineering "
            "experience building scalable microservices and REST APIs. Proficient in "
            "Python and Java. Deployed cloud-native applications on AWS using Docker "
            "and Kubernetes. Experience with CI/CD pipelines and Agile development."
        ),
        "projects": [
            "Developed a high-throughput payment processing microservice in Java/Spring Boot "
            "handling 50k transactions per day with 99.9% uptime.",
            "Containerised a legacy monolith into 8 Docker microservices deployed on "
            "Kubernetes, reducing deployment time from 2 hours to 10 minutes.",
            "Implemented an event-driven notification system using AWS SNS/SQS, "
            "processing 1M events per day.",
        ],
        "education": "B.Tech – Computer Science, IIT Bombay, 2021",
        "certifications": ["AWS Certified Solutions Architect – Associate, 2022"],
    },

    # ── 3. Healthcare Data Analyst ────────────────────────────
    {
        "id": "resume_hda_001",
        "name": "Sophia James",
        "target_role": "Healthcare Data Analyst",
        "skills": [
            "SQL", "Python", "R", "Tableau", "Epic EHR", "ICD-10 coding",
            "HIPAA compliance", "clinical data analysis", "SAS",
            "health informatics", "data warehousing", "Excel", "SPSS"
        ],
        "experience_summary": (
            "BS Biological Sciences graduate with a Certificate in Healthcare Data Analytics. "
            "2 years experience in clinical data analysis and health information management. "
            "Proficient in SQL, Python, and Epic EHR. Skilled in ICD-10 coding, HIPAA "
            "compliance, and translating clinical data into operational insights."
        ),
        "projects": [
            "Analysed patient readmission patterns using SQL and Python, identifying "
            "3 key risk factors that informed a care management programme reducing "
            "30-day readmissions by 15%.",
            "Built a Tableau dashboard for hospital bed utilisation tracking across "
            "6 departments, adopted by nursing management for daily operations.",
            "Automated monthly quality metrics reporting using Python and SQL, "
            "replacing a 20-hour manual Excel process.",
        ],
        "education": "BS – Biological Sciences, Georgia State University, 2020",
        "certifications": [
            "Certificate in Healthcare Data Analytics – Coursera / Johns Hopkins, 2021",
            "RHIT – AHIMA, 2022",
        ],
    },

    # ── 4. Marketing Manager ──────────────────────────────────
    {
        "id": "resume_mm_001",
        "name": "Priya Nair",
        "target_role": "Marketing Manager",
        "skills": [
            "Digital marketing", "SEO", "SEM", "Google Ads", "Meta Ads",
            "content strategy", "brand management", "email marketing",
            "HubSpot", "Salesforce CRM", "Google Analytics",
            "campaign management", "A/B testing", "copywriting"
        ],
        "experience_summary": (
            "MBA Marketing graduate with 5 years of digital marketing experience. "
            "Managed end-to-end campaigns achieving 3x ROAS on paid channels. "
            "Led a team of 4 content creators and 2 SEO specialists. Expertise in "
            "brand positioning, demand generation, and marketing analytics."
        ),
        "projects": [
            "Launched a multi-channel digital campaign generating 120k leads in Q3, "
            "exceeding target by 35% with a combined SEO/SEM strategy.",
            "Redesigned email nurture sequences in HubSpot, improving open rates from "
            "18% to 31% and conversion rates by 22%.",
            "Built a marketing attribution model in Google Analytics and Salesforce CRM "
            "providing full-funnel visibility for the first time.",
        ],
        "education": "MBA – Marketing, Symbiosis Institute of Business Management, 2019",
        "certifications": [
            "Google Ads Certified – Google, 2023",
            "HubSpot Inbound Marketing – HubSpot, 2022",
        ],
    },

    # ── 5. Mechanical Engineer ────────────────────────────────
    {
        "id": "resume_me_001",
        "name": "Arun Kumar",
        "target_role": "Mechanical Engineer",
        "skills": [
            "AutoCAD", "SolidWorks", "ANSYS", "FEA", "CFD",
            "GD&T", "manufacturing processes", "lean manufacturing",
            "Six Sigma", "quality control", "MATLAB", "Python",
            "project management", "supplier management"
        ],
        "experience_summary": (
            "B.Tech Mechanical Engineering graduate with 3 years experience in product "
            "design and manufacturing. Proficient in SolidWorks, ANSYS FEA, and AutoCAD. "
            "Worked on engine component design and tooling optimisation. Six Sigma Green "
            "Belt certified. Reduced scrap rate by 18% through process improvement."
        ),
        "projects": [
            "Designed and validated a lightweight engine bracket using SolidWorks and "
            "ANSYS FEA, achieving 23% weight reduction while meeting all stress requirements.",
            "Led a lean manufacturing initiative eliminating 3 non-value-added steps in "
            "the assembly line, reducing cycle time by 14%.",
            "Developed CFD simulations for heat exchanger optimisation, improving thermal "
            "efficiency by 9% in the final prototype.",
        ],
        "education": "B.Tech – Mechanical Engineering, NIT Trichy, 2021",
        "certifications": ["Six Sigma Green Belt – ASQ, 2022"],
    },

    # ── 6. Mismatched resume (wrong field vs JD) ──────────────
    {
        "id": "resume_mismatch_001",
        "name": "Test Mismatch",
        "target_role": "Software Engineer",
        "skills": ["cooking", "event planning", "hospitality", "customer service"],
        "experience_summary": (
            "Experienced hospitality professional with 5 years in hotel management "
            "and event coordination. Strong interpersonal and customer service skills."
        ),
        "projects": [
            "Coordinated a 500-guest corporate event at The Taj, managing vendors, "
            "catering, and AV setup.",
        ],
        "education": "BHM – Hotel Management, IHM Chennai, 2019",
        "certifications": [],
    },
]


# ═══════════════════════════════════════════════════════════════
# SAMPLE JOBs  (structured JDs)
# ═══════════════════════════════════════════════════════════════

SAMPLE_JDS = [

    # ── 1. Data Analyst JD ────────────────────────────────────
    {
        "id": "jd_da_001",
        "title": "Data Analyst",
        "company": "FinEdge Analytics",
        "required_skills": [
            "SQL", "Python", "Tableau or Power BI", "Excel",
            "data cleaning", "ETL pipelines", "statistical analysis"
        ],
        "preferred_skills": [
            "pandas", "NumPy", "Google Analytics", "A/B testing",
            "dashboard development", "business intelligence"
        ],
        "responsibilities": (
            "Analyse large datasets to extract business insights. Build and maintain "
            "dashboards in Tableau or Power BI. Write complex SQL queries and Python "
            "scripts for data extraction and transformation. Partner with stakeholders "
            "to define KPIs and reporting requirements. Support data-driven decision-making "
            "across finance and marketing teams."
        ),
        "qualifications": (
            "Bachelor's or master's degree in business, finance, statistics, or a related "
            "field. 2+ years of data analytics experience. Strong SQL and Python skills. "
            "MBA or advanced analytics qualification preferred."
        ),
        "job_type": "data_analytics",
    },

    # ── 2. Software Engineer JD ───────────────────────────────
    {
        "id": "jd_se_001",
        "title": "Backend Software Engineer",
        "company": "CloudStack Tech",
        "required_skills": [
            "Python or Java", "REST API design", "Microservices architecture",
            "Docker", "Kubernetes", "AWS or GCP", "Git"
        ],
        "preferred_skills": [
            "Spring Boot", "CI/CD", "Jenkins", "Redis", "PostgreSQL",
            "event-driven architecture", "Agile/Scrum"
        ],
        "responsibilities": (
            "Design and build scalable backend microservices. Define and maintain REST APIs "
            "consumed by frontend and mobile clients. Containerise services with Docker "
            "and deploy on Kubernetes. Participate in code reviews, architecture discussions, "
            "and sprint planning. Ensure 99.9% uptime through monitoring and on-call support."
        ),
        "qualifications": (
            "Bachelor's degree in computer science or software engineering. 2+ years of "
            "backend development experience. Strong Python or Java skills. Experience with "
            "cloud platforms (AWS/GCP) required."
        ),
        "job_type": "software_engineering",
    },

    # ── 3. Healthcare Data Analyst JD ─────────────────────────
    {
        "id": "jd_hda_001",
        "title": "Junior Healthcare Data Analyst",
        "company": "MedInsights Corp",
        "required_skills": [
            "SQL", "Python or R", "EHR systems", "clinical data analysis",
            "data visualisation", "HIPAA compliance"
        ],
        "preferred_skills": [
            "Epic EHR", "Tableau", "ICD-10 coding", "health informatics",
            "SAS", "healthcare analytics certificate"
        ],
        "responsibilities": (
            "Analyse clinical and operational healthcare data to support quality improvement. "
            "Build dashboards tracking patient outcomes and operational KPIs. Write SQL queries "
            "against EHR data warehouses. Ensure data governance and HIPAA compliance. "
            "Collaborate with clinical teams to define metrics and interpret findings."
        ),
        "qualifications": (
            "Bachelor's degree in health sciences, biology, public health, or related field. "
            "Experience with EHR systems (Epic preferred). Knowledge of ICD coding and "
            "healthcare informatics. SQL and Python/R required."
        ),
        "job_type": "healthcare_analytics",
    },

    # ── 4. Marketing Manager JD ───────────────────────────────
    {
        "id": "jd_mm_001",
        "title": "Digital Marketing Manager",
        "company": "BrandPulse Agency",
        "required_skills": [
            "Digital marketing", "SEO", "Google Ads", "Meta Ads",
            "content strategy", "campaign management", "Google Analytics"
        ],
        "preferred_skills": [
            "HubSpot", "Salesforce CRM", "email marketing", "A/B testing",
            "brand management", "copywriting", "SEM"
        ],
        "responsibilities": (
            "Plan and execute multi-channel digital marketing campaigns. Manage paid search "
            "and social media advertising budgets. Develop content strategy and oversee "
            "content creation. Track and report on campaign performance metrics. Lead and "
            "mentor a small marketing team. Drive lead generation and brand awareness."
        ),
        "qualifications": (
            "MBA or bachelor's degree in marketing, communications, or related field. "
            "4+ years of digital marketing experience. Proven track record with SEO/SEM "
            "and paid digital campaigns. HubSpot or Salesforce CRM experience preferred."
        ),
        "job_type": "marketing",
    },

    # ── 5. Mechanical Engineer JD ─────────────────────────────
    {
        "id": "jd_me_001",
        "title": "Mechanical Design Engineer",
        "company": "AutoPrecision Ltd",
        "required_skills": [
            "SolidWorks", "AutoCAD", "ANSYS or FEA", "GD&T",
            "manufacturing processes", "design validation"
        ],
        "preferred_skills": [
            "CFD simulation", "lean manufacturing", "Six Sigma",
            "MATLAB", "quality control", "supplier management"
        ],
        "responsibilities": (
            "Design mechanical components and assemblies using SolidWorks and AutoCAD. "
            "Perform structural analysis using ANSYS FEA. Create detailed engineering "
            "drawings with GD&T. Collaborate with manufacturing teams on DFM. "
            "Support prototyping, testing, and design validation activities."
        ),
        "qualifications": (
            "Bachelor's degree in mechanical engineering. 2+ years of product design "
            "experience. Proficiency in SolidWorks and ANSYS required. Six Sigma "
            "certification preferred."
        ),
        "job_type": "mechanical_engineering",
    },
]


# ═══════════════════════════════════════════════════════════════
# GROUND TRUTH LABELS
# Expected match quality for resume ↔ JD pairs
# Scores: 1.0=strong match, 0.5=partial, 0.0=mismatch
# Used by validator.py for accuracy reporting
# ═══════════════════════════════════════════════════════════════

GROUND_TRUTH = [
    # (resume_id, jd_id, expected_label, expected_score_range)
    ("resume_da_001",       "jd_da_001",  "strong_match",   (0.70, 1.00)),
    ("resume_se_001",       "jd_se_001",  "strong_match",   (0.70, 1.00)),
    ("resume_hda_001",      "jd_hda_001", "strong_match",   (0.65, 1.00)),
    ("resume_mm_001",       "jd_mm_001",  "strong_match",   (0.70, 1.00)),
    ("resume_me_001",       "jd_me_001",  "strong_match",   (0.70, 1.00)),
    # Cross-domain partial matches
    ("resume_da_001",       "jd_hda_001", "partial_match",  (0.40, 0.75)),
    ("resume_se_001",       "jd_da_001",  "partial_match",  (0.30, 0.65)),
    ("resume_hda_001",      "jd_da_001",  "partial_match",  (0.40, 0.75)),
    # Clear mismatches
    ("resume_mismatch_001", "jd_se_001",  "mismatch",       (0.00, 0.30)),
    ("resume_me_001",       "jd_da_001",  "mismatch",       (0.00, 0.35)),
    ("resume_mm_001",       "jd_me_001",  "mismatch",       (0.00, 0.30)),
]
