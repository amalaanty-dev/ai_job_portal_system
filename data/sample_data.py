"""
data/sample_data.py
────────────────────
Day 12 – Semantic Matching Engine  |  Built-in Sample Dataset

Formats match the actual pipeline formats:
  • SAMPLE_RESUMES : sectioned resume JSON  (same as sectioned_resumes/ folder)
  • SAMPLE_JDS     : parsed JD JSON         (same as parsed_jd/ folder)
  • GROUND_TRUTH   : (resume_id, jd_id, expected_label, score_range)

Job types covered:
  data_analytics, software_engineering, healthcare_analytics,
  marketing, mechanical_engineering
"""

# ═══════════════════════════════════════════════════════════════
# SAMPLE RESUMES  (sectioned format)
# ═══════════════════════════════════════════════════════════════

SAMPLE_RESUMES = [

    # ── Data Analyst ──────────────────────────────────────────
    {
        "id":   "resume_da_001",
        "name": "Priya Nair",
        "skills": [
            "Python", "SQL", "Tableau", "Power BI", "Excel",
            "Pandas", "NumPy", "data visualisation", "ETL pipelines",
            "statistical analysis", "A/B testing", "Google Analytics",
            "data cleaning", "KPI dashboards", "business intelligence"
        ],
        "experience": [
            {
                "role_header": "Data Analyst  ·  Infosys  ·  2021–Present",
                "duties": [
                    "Built Tableau dashboards tracking 15+ KPIs for retail clients.",
                    "Automated ETL workflows in Python reducing report time by 40%.",
                    "Performed SQL-based cohort analysis on 5M+ transaction records.",
                    "Collaborated with business stakeholders to define metrics.",
                ]
            },
            {
                "role_header": "Junior Analyst  ·  Wipro  ·  2019–2021",
                "duties": [
                    "Cleaned and validated large datasets using Pandas.",
                    "Produced weekly Excel pivot-table reports for management.",
                    "Supported A/B testing analysis for e-commerce campaigns.",
                ]
            }
        ],
        "projects": [
            "Customer churn prediction using logistic regression in Python.",
            "Sales forecasting dashboard built in Power BI with DAX measures.",
            "Automated data quality checks pipeline using Great Expectations.",
        ],
        "education": [
            "B.Sc. Statistics – University of Mumbai – 2019"
        ],
        "certifications": [
            "Google Data Analytics Professional Certificate – 2021",
            "Tableau Desktop Specialist – 2022",
        ],
        "achievements": [],
        "other": [
            "Priya Nair",
            "Data Analyst",
            "priya.nair@email.com | Mumbai, India",
        ]
    },

    # ── Software Engineer ──────────────────────────────────────
    {
        "id":   "resume_se_001",
        "name": "Arjun Mehta",
        "skills": [
            "Python", "Java", "Spring Boot", "REST APIs", "microservices",
            "Docker", "Kubernetes", "AWS", "CI/CD", "Jenkins", "Git",
            "PostgreSQL", "Redis", "MongoDB", "Agile", "Scrum",
            "event-driven architecture", "backend development"
        ],
        "experience": [
            {
                "role_header": "Software Engineer  ·  TCS  ·  2020–Present",
                "duties": [
                    "Developed microservices in Java Spring Boot for banking platform.",
                    "Deployed containerised services on Kubernetes / AWS EKS.",
                    "Implemented CI/CD pipelines with Jenkins and GitHub Actions.",
                    "Optimised PostgreSQL queries reducing API latency by 35%.",
                ]
            },
            {
                "role_header": "Junior Developer  ·  HCL  ·  2018–2020",
                "duties": [
                    "Built REST APIs consumed by Android and iOS mobile apps.",
                    "Wrote unit and integration tests achieving 90%+ coverage.",
                ]
            }
        ],
        "projects": [
            "Event-driven order processing system using Kafka and Spring Boot.",
            "Containerised deployment of a Node.js app on AWS ECS with Terraform.",
        ],
        "education": [
            "B.Tech Computer Science – IIT Bombay – 2018"
        ],
        "certifications": [
            "AWS Certified Developer – Associate – 2021",
            "Certified Kubernetes Application Developer (CKAD) – 2022",
        ],
        "achievements": [],
        "other": ["Arjun Mehta", "Software Engineer", "arjun.mehta@email.com"]
    },

    # ── Healthcare Data Analyst ────────────────────────────────
    {
        "id":   "resume_hda_001",
        "name": "James Thornton",
        "skills": [
            "Python", "SQL", "R", "Epic", "Cerner", "ICD-10 coding",
            "HIPAA compliance", "clinical data analysis", "scikit-learn",
            "predictive modelling", "patient readmission", "Excel",
            "healthcare analytics", "medical records", "data privacy"
        ],
        "experience": [
            {
                "role_header": "Medical Data Analyst  ·  Emory Healthcare  ·  Jan 2022–Present",
                "duties": [
                    "Analysed 200,000+ medical records to identify treatment patterns.",
                    "Built predictive models to flag high-risk patients using scikit-learn.",
                    "Ensured data privacy through strict HIPAA and institutional policies.",
                    "Collaborated with physicians to provide data-backed clinical decisions.",
                ]
            },
            {
                "role_header": "Healthcare Data Associate  ·  Piedmont Healthcare  ·  2020–2021",
                "duties": [
                    "Extracted and analysed ICD-10 coded diagnosis data for reporting.",
                    "Validated medical data accuracy across Epic and legacy systems.",
                ]
            }
        ],
        "projects": [],
        "education": [
            "B.S. Biological Sciences – Georgia State University – 2020"
        ],
        "certifications": [
            "Certificate in Healthcare Data Analytics – Coursera / Johns Hopkins – 2021",
            "Registered Health Information Technician (RHIT) – AHIMA – 2022",
            "Python for Data Science – IBM – 2021",
        ],
        "achievements": [],
        "other": [
            "James Thornton",
            "Medical Data Analyst",
            "james.thornton@email.com | Atlanta, GA",
        ]
    },

    # ── Marketing Manager ──────────────────────────────────────
    {
        "id":   "resume_mm_001",
        "name": "Sneha Pillai",
        "skills": [
            "digital marketing", "SEO", "SEM", "Google Ads", "Meta Ads",
            "content strategy", "email marketing", "HubSpot", "Salesforce",
            "brand management", "market research", "campaign analytics",
            "social media marketing", "A/B testing", "copywriting"
        ],
        "experience": [
            {
                "role_header": "Marketing Manager  ·  Flipkart  ·  2020–Present",
                "duties": [
                    "Led digital campaigns generating 3M+ impressions per quarter.",
                    "Managed ₹2Cr annual Google Ads and Meta Ads budget.",
                    "Grew organic traffic by 60% through SEO content strategy.",
                ]
            },
            {
                "role_header": "Marketing Executive  ·  Myntra  ·  2018–2020",
                "duties": [
                    "Created and scheduled social media content across platforms.",
                    "Conducted competitor market research and trend analysis.",
                ]
            }
        ],
        "projects": [
            "Influencer campaign for festive season delivering 5x ROAS.",
            "Email drip sequence for cart abandonment – 18% recovery rate.",
        ],
        "education": [
            "MBA Marketing – IIM Kozhikode – 2018"
        ],
        "certifications": [
            "Google Ads Search Certification – 2022",
            "HubSpot Content Marketing Certification – 2021",
        ],
        "achievements": [],
        "other": ["Sneha Pillai", "Marketing Manager", "sneha.pillai@email.com"]
    },

    # ── Mechanical Engineer ────────────────────────────────────
    {
        "id":   "resume_me_001",
        "name": "Rohit Sharma",
        "skills": [
            "SolidWorks", "AutoCAD", "ANSYS FEA", "GD&T", "CNC machining",
            "product design", "thermal analysis", "material selection",
            "manufacturing processes", "FMEA", "root cause analysis",
            "project management", "BOM management", "PLM"
        ],
        "experience": [
            {
                "role_header": "Mechanical Design Engineer  ·  L&T  ·  2019–Present",
                "duties": [
                    "Designed sheet metal enclosures using SolidWorks; managed BOM.",
                    "Performed ANSYS FEA simulations to validate structural integrity.",
                    "Collaborated with manufacturing team to resolve DFM issues.",
                ]
            },
            {
                "role_header": "Graduate Engineer Trainee  ·  Bharat Forge  ·  2018–2019",
                "duties": [
                    "Supported CNC machining process planning and fixture design.",
                    "Conducted root cause analysis for production quality failures.",
                ]
            }
        ],
        "projects": [
            "Redesign of heat exchanger reducing weight by 15% with ANSYS optimisation.",
            "Jig and fixture design for high-volume automotive component assembly.",
        ],
        "education": [
            "B.Tech Mechanical Engineering – NIT Trichy – 2018"
        ],
        "certifications": [
            "SolidWorks Certified Professional (CSWP) – 2020",
        ],
        "achievements": [],
        "other": ["Rohit Sharma", "Mechanical Engineer", "rohit.sharma@email.com"]
    },

    # ── Deliberate Mismatch (Hospitality → SE JD) ─────────────
    {
        "id":   "resume_mismatch_001",
        "name": "Maria Costa",
        "skills": [
            "customer service", "front desk management", "hotel PMS",
            "team leadership", "event coordination", "food and beverage",
            "housekeeping management", "Opera PMS", "revenue management",
            "guest relations", "complaint resolution"
        ],
        "experience": [
            {
                "role_header": "Hotel Manager  ·  Taj Hotels  ·  2017–Present",
                "duties": [
                    "Managed 120-room property with 45-member team.",
                    "Achieved 94% guest satisfaction score for 3 consecutive years.",
                    "Oversaw F&B operations and banquet event coordination.",
                ]
            }
        ],
        "projects": [],
        "education": [
            "Bachelor of Hotel Management – IHM Mumbai – 2017"
        ],
        "certifications": [
            "Certified Hospitality Supervisor – AHLEI – 2019"
        ],
        "achievements": [],
        "other": ["Maria Costa", "Hotel Manager", "maria.costa@email.com"]
    },

]


# ═══════════════════════════════════════════════════════════════
# SAMPLE JDs  (parsed JD format)
# ═══════════════════════════════════════════════════════════════

SAMPLE_JDS = [

    # ── Data Analytics JD ─────────────────────────────────────
    {
        "id":    "jd_da_001",
        "title": "Data Analyst",
        "job_type": "data_analytics",
        "role": [
            "Analyse large datasets to generate business insights",
            "Build dashboards and reports in Tableau or Power BI",
            "Write complex SQL queries for data extraction and transformation",
            "Collaborate with stakeholders to define KPIs and metrics",
            "Automate ETL pipelines and data workflows using Python",
        ],
        "skills_required": [
            "Python", "SQL", "Tableau", "Power BI", "Excel",
            "data visualisation", "statistical analysis", "ETL",
            "Pandas", "business intelligence"
        ],
        "experience_required": "2+ years in a data analyst or BI role",
        "education_required":  "Bachelor's in Statistics, Mathematics, Computer Science, or related field",
    },

    # ── Software Engineering JD ───────────────────────────────
    {
        "id":    "jd_se_001",
        "title": "Software Engineer – Backend",
        "job_type": "software_engineering",
        "role": [
            "Design and develop scalable backend microservices",
            "Deploy and manage containerised applications on Kubernetes",
            "Build and maintain CI/CD pipelines",
            "Write clean, testable code with 85%+ test coverage",
            "Participate in Agile sprint ceremonies",
        ],
        "skills_required": [
            "Java", "Python", "Spring Boot", "REST APIs", "microservices",
            "Docker", "Kubernetes", "AWS", "CI/CD", "PostgreSQL", "Git"
        ],
        "experience_required": "3+ years backend software development",
        "education_required":  "B.Tech / B.E. in Computer Science or related field",
    },

    # ── Healthcare Data Analytics JD ──────────────────────────
    {
        "id":    "jd_hda_001",
        "title": "Healthcare Data Analyst",
        "job_type": "healthcare_analytics",
        "role": [
            "Analyse clinical and administrative healthcare data",
            "Build predictive models for patient outcomes and readmission",
            "Ensure compliance with HIPAA data privacy regulations",
            "Work with EHR systems including Epic and Cerner",
            "Collaborate with clinical teams to support data-driven decisions",
        ],
        "skills_required": [
            "Python", "SQL", "R", "Epic", "Cerner", "ICD-10",
            "HIPAA", "clinical data", "predictive modelling",
            "healthcare analytics", "scikit-learn"
        ],
        "experience_required": "2+ years in healthcare data or clinical informatics",
        "education_required":  "Bachelor's in Health Informatics, Biological Sciences, or related field",
    },

    # ── Marketing Manager JD ──────────────────────────────────
    {
        "id":    "jd_mm_001",
        "title": "Marketing Manager – Digital",
        "job_type": "marketing",
        "role": [
            "Plan and execute digital marketing campaigns across channels",
            "Manage paid search and social media advertising budgets",
            "Drive SEO strategy and organic growth",
            "Analyse campaign performance and report on ROI",
            "Lead brand partnerships and influencer collaborations",
        ],
        "skills_required": [
            "digital marketing", "SEO", "SEM", "Google Ads", "Meta Ads",
            "content strategy", "HubSpot", "brand management",
            "campaign analytics", "social media marketing"
        ],
        "experience_required": "3+ years in digital or performance marketing",
        "education_required":  "MBA or Bachelor's in Marketing, Communications, or related field",
    },

    # ── Mechanical Engineering JD ─────────────────────────────
    {
        "id":    "jd_me_001",
        "title": "Mechanical Design Engineer",
        "job_type": "mechanical_engineering",
        "role": [
            "Design mechanical components and assemblies using SolidWorks",
            "Perform FEA simulation and structural analysis using ANSYS",
            "Create detailed engineering drawings with GD&T",
            "Work with manufacturing teams on DFM and process planning",
            "Conduct FMEA and root cause analysis for product failures",
        ],
        "skills_required": [
            "SolidWorks", "AutoCAD", "ANSYS", "FEA", "GD&T",
            "CNC machining", "product design", "FMEA",
            "manufacturing processes", "BOM management"
        ],
        "experience_required": "2+ years in mechanical product design",
        "education_required":  "B.Tech Mechanical Engineering or related field",
    },

]


# ═══════════════════════════════════════════════════════════════
# GROUND TRUTH
# Format: (resume_id, jd_id, expected_label, (score_min, score_max))
# ═══════════════════════════════════════════════════════════════

GROUND_TRUTH = [

    # ── Ideal / strong matches ────────────────────────────────
    ("resume_da_001",  "jd_da_001",  "Strong Match",   (0.55, 1.00)),
    ("resume_se_001",  "jd_se_001",  "Strong Match",   (0.55, 1.00)),
    ("resume_hda_001", "jd_hda_001", "Strong Match",   (0.55, 1.00)),
    ("resume_mm_001",  "jd_mm_001",  "Strong Match",   (0.55, 1.00)),
    ("resume_me_001",  "jd_me_001",  "Strong Match",   (0.55, 1.00)),

    # ── Partial / cross-domain ────────────────────────────────
    ("resume_da_001",  "jd_hda_001", "Partial Match",  (0.30, 0.65)),
    ("resume_hda_001", "jd_da_001",  "Partial Match",  (0.30, 0.65)),
    ("resume_se_001",  "jd_da_001",  "Partial Match",  (0.25, 0.60)),

    # ── Mismatches ────────────────────────────────────────────
    ("resume_mismatch_001", "jd_se_001",  "Mismatch",  (0.00, 0.35)),
    ("resume_mismatch_001", "jd_da_001",  "Mismatch",  (0.00, 0.35)),
    ("resume_me_001",       "jd_se_001",  "Mismatch",  (0.00, 0.40)),
    ("resume_mm_001",       "jd_se_001",  "Mismatch",  (0.00, 0.35)),

]