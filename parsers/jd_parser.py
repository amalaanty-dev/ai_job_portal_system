
import re
import json
import os
import glob


# -----------------------------
# Skill Database
# -----------------------------

SKILLS_DB = [

# Programming
"python",
"r",
"sas",

# Databases
"sql",
"database management",

# Data Analysis
"data analysis",
"data mining",
"data modeling",
"data validation",
"data extraction",
"data interpretation",

# Visualization
"data visualization",
"tableau",
"power bi",
"dashboard development",
"visual analytics",

# Statistics
"statistics",
"statistical analysis",
"statistical modeling",
"predictive modeling",

# Machine Learning
"machine learning",
"deep learning",
"nlp",
"computer vision",
"ai",

# ML Frameworks
"tensorflow",
"pytorch",

# Cloud / Engineering
"aws",
"azure",
"gcp",
"etl",
"data engineering",
"mlops",

# Healthcare Domain
"healthcare analytics",
"health informatics",
"clinical data analysis",
"clinical research",
"ehr",
"emr",
"hl7",
"fhir",
"bioinformatics",

# Healthcare Business
"revenue cycle analysis",
"claims analysis",
"fraud detection",
"risk analysis",
"cost analysis",
"kpi analysis",

# Public Health
"epidemiology",
"public health analytics",
"disease surveillance",

# Business / Consulting
"business analysis",
"stakeholder communication",
"report writing",
"project management",

# Process / Operations
"process improvement",
"workflow optimization",
"lean",
"six sigma",

# Tools
"excel",

# Soft Skills
"analytical thinking",
"problem solving",
"attention to detail",
"communication skills",
"leadership"
]

# -----------------------------



# -----------------------------
# Role Database
# -----------------------------
ROLE_DB = [
    "healthcare data analyst (junior)",
    "clinical data analyst",
    "healthcare reporting analyst",
    "medical data analyst",
    "health information analyst",
    "data entry analyst (healthcare)",
    "public health data analyst (entry-level)",
    "ehr data analyst",
    "healthcare data analyst",
    "senior clinical data analyst",
    "healthcare business analyst",
    "population health analyst",
    "quality improvement analyst (healthcare)",
    "healthcare operations analyst",
    "revenue cycle data analyst",
    "healthcare performance analyst",
    "healthcare bi (business intelligence) analyst",
    "claims data analyst",
    "senior healthcare data analyst",
    "lead data analyst (healthcare)",
    "healthcare analytics manager",
    "healthcare data science manager",
    "director of healthcare analytics",
    "chief data officer",
    "head of health informatics",
    "healthcare data scientist",
    "clinical data scientist",
    "healthcare machine learning engineer",
    "ai specialist in healthcare analytics",
    "predictive analytics specialist",
    "healthcare statistician",
    "biostatistician",
    "clinical research data analyst",
    "clinical trials data manager",
    "epidemiologist",
    "healthcare outcomes analyst",
    "real world evidence (rwe) analyst",
    "health informatics specialist",
    "clinical informatics analyst",
    "healthcare data integration specialist",
    "ehr implementation analyst",
    "healthcare data architect",
    "health information systems analyst",
    "healthcare financial analyst",
    "medical billing data analyst",
    "insurance claims analyst",
    "revenue cycle analyst",
    "cost & utilization analyst",
    "public health analyst",
    "health policy analyst",
    "epidemiology data analyst",
    "healthcare program analyst",
    "global health data analyst",
    "digital health analyst",
    "telehealth data analyst",
    "healthcare ai analyst",
    "patient experience analyst",
    "healthcare risk analyst",
    "fraud & compliance analyst",
    "wearable health data analyst",
    "genomics data analyst",
    "freelance healthcare data analyst",
    "healthcare analytics consultant",
    "data analytics trainer",
    "healthcare dashboard developer",
    "remote clinical data analyst"
]


# -----------------------------
# Role Synonyms
# -----------------------------
ROLE_SYNONYMS = {

"healthcare data analyst (junior)": [
"junior healthcare data analyst",
"jr healthcare data analyst",
"entry level healthcare data analyst"
],

"clinical data analyst": [
"clinical analytics analyst",
"clinical trial data analyst"
],

"healthcare reporting analyst": [
"healthcare report analyst",
"reporting analyst healthcare"
],

"medical data analyst": [
"medical analytics analyst"
],

"health information analyst": [
"health information data analyst",
"health information systems analyst"
],

"data entry analyst (healthcare)": [
"healthcare data entry analyst"
],

"public health data analyst (entry-level)": [
"entry level public health data analyst"
],

"ehr data analyst": [
"electronic health record analyst",
"ehr analytics specialist"
],

"healthcare data analyst": [
"health data analyst"
],

"senior clinical data analyst": [
"sr clinical data analyst"
],

"healthcare business analyst": [
"healthcare ba",
"business analyst healthcare"
],

"population health analyst": [
"population health data analyst"
],

"quality improvement analyst (healthcare)": [
"healthcare quality analyst"
],

"healthcare operations analyst": [
"hospital operations analyst"
],

"revenue cycle data analyst": [
"revenue cycle analyst",
"rcm analyst"
],

"healthcare performance analyst": [
"hospital performance analyst"
],

"healthcare bi (business intelligence) analyst": [
"healthcare bi analyst",
"healthcare business intelligence analyst"
],

"claims data analyst": [
"insurance claims analyst"
],

"senior healthcare data analyst": [
"sr healthcare data analyst"
],

"lead data analyst (healthcare)": [
"lead healthcare data analyst"
],

"healthcare analytics manager": [
"manager healthcare analytics"
],

"healthcare data science manager": [
"healthcare ds manager"
],

"director of healthcare analytics": [
"healthcare analytics director"
],

"chief data officer": [
"cdo"
],

"head of health informatics": [
"health informatics head"
],

"healthcare data scientist": [
"healthcare ai data scientist"
],

"clinical data scientist": [
"clinical analytics scientist"
],

"healthcare machine learning engineer": [
"ml engineer healthcare"
],

"ai specialist in healthcare analytics": [
"healthcare ai engineer"
],

"predictive analytics specialist": [
"predictive healthcare analyst"
],

"healthcare statistician": [
"clinical statistician"
],

"biostatistician": [
"bio statistician"
],

"clinical research data analyst": [
"clinical research analyst"
],

"clinical trials data manager": [
"clinical trial data manager"
],

"epidemiologist": [
"public health epidemiologist"
],

"healthcare outcomes analyst": [
"health outcomes analyst"
],

"real world evidence (rwe) analyst": [
"rwe analyst"
],

"health informatics specialist": [
"health informatics analyst"
],

"clinical informatics analyst": [
"clinical informatics specialist"
],

"healthcare data integration specialist": [
"health data integration analyst"
],

"ehr implementation analyst": [
"ehr implementation specialist"
],

"healthcare data architect": [
"health data architect"
],

"health information systems analyst": [
"his analyst"
],

"healthcare financial analyst": [
"healthcare finance analyst"
],

"medical billing data analyst": [
"billing analytics analyst"
],

"insurance claims analyst": [
"claims analytics analyst"
],


"cost & utilization analyst": [
"cost utilization analyst"
],

"public health analyst": [
"public health analytics analyst"
],

"health policy analyst": [
"healthcare policy analyst"
],

"epidemiology data analyst": [
"epidemiology analyst"
],

"healthcare program analyst": [
"health program analyst"
],

"global health data analyst": [
"global health analyst"
],

"digital health analyst": [
"digital healthcare analyst"
],

"telehealth data analyst": [
"telemedicine data analyst"
],

"healthcare ai analyst": [
"ai healthcare analyst"
],

"patient experience analyst": [
"patient satisfaction analyst"
],

"healthcare risk analyst": [
"clinical risk analyst"
],

"fraud & compliance analyst": [
"fraud compliance analyst"
],

"wearable health data analyst": [
"wearable analytics analyst"
],

"genomics data analyst": [
"genomic data analyst",
"bioinformatics analyst"
],

"freelance healthcare data analyst": [
"contract healthcare data analyst"
],

"healthcare analytics consultant": [
"healthcare analytics advisor"
],

"data analytics trainer": [
"analytics instructor"
],

"healthcare dashboard developer": [
"healthcare bi dashboard developer"
],

"remote clinical data analyst": [
"virtual clinical data analyst"
]

}
SKILL_SYNONYMS = {

# Programming
"python": ["python3","python programming","python scripting"],
"r": ["r language","r programming"],
"sas": ["sas analytics","sas software"],

# SQL
"sql": [
    "structured query language",
    "mysql",
    "postgresql",
    "sql server",
    "oracle sql"
],

# Visualization
"power bi": [
    "powerbi",
    "power-bi",
    "microsoft power bi"
],

"tableau": [
    "tableau software",
    "tableau desktop",
    "tableau dashboards"
],

"data visualization": [
    "data viz",
    "data visualisation",
    "dashboard creation",
    "data visual analytics",
    "interactive analytics",
    "visual data analysis",
    "analytics visualization"
],

# Machine Learning
"machine learning": [
    "ml",
    "machine-learning",
    "predictive analytics",
    "ml algorithms"
],

"deep learning": [
    "neural networks",
    "deep neural networks",
    "dnn"
],

"nlp": [
    "natural language processing",
    "text analytics"
],

"computer vision": [
    "image recognition",
    "image processing"
],

# Frameworks
"tensorflow": ["tf"],
"pytorch": ["torch"],

# Cloud
"aws": ["amazon web services","aws cloud"],
"azure": ["microsoft azure","azure cloud"],
"gcp": ["google cloud","google cloud platform"],

# Healthcare systems
"ehr": [
    "electronic health records",
    "ehr systems",
    "ehr platforms"
],

"emr": [
    "electronic medical records",
    "emr systems"
],

"hl7": [
    "hl7 standards"
],

"fhir": [
    "fhir standard"
],

# Analytics
"data analysis": [
    "data analytics",
    "data examination",
    "data insights"
],

"statistical analysis": [
    "statistics",
    "statistical techniques"
],

"predictive modeling": [
    "predictive models",
    "forecast modeling"
],

# Finance / insurance
"claims analysis": [
    "claims analytics",
    "insurance claims analysis"
],

"fraud detection": [
    "fraud analytics",
    "fraud identification"
],
"revenue cycle analysis": [
    "rcm",
    "revenue cycle analytics"
],


# Business
"business analysis": [
    "business analytics",
    "business requirement analysis"
],

"process improvement": [
    "process optimization",
    "workflow improvement"
],

# Data engineering
"etl": [
    "extract transform load",
    "etl pipelines"
],

"data engineering": [
    "data pipeline development"
],

# Governance
"data governance": [
    "data policy management"
],

"data validation": [
    "data verification"
],

# Tools
"excel": [
    "ms excel",
    "microsoft excel"
],

"data mining": [
    "data mining techniques",
    "pattern discovery",
    "knowledge discovery",
    "data pattern analysis"
],

"data modeling": [
    "data modelling",
    "data model development",
    "database modeling",
    "data structure modeling"
],

"data extraction": [
    "data retrieval",
    "data collection",
    "data scraping",
    "data gathering"
],

"data interpretation": [
    "data interpretation techniques",
    "insight generation",
    "data insights",
    "analytical interpretation"
],

"dashboard development": [
    "dashboard creation",
    "dashboard design",
    "dashboard building",
    "analytics dashboard development"
],


"statistical modeling": [
    "statistical models",
    "stats modeling",
    "statistical predictive modeling",
    "quantitative modeling"
],

"risk analysis": [
    "risk analytics",
    "risk assessment",
    "risk evaluation",
    "risk modeling"
],

"cost analysis": [
    "cost analytics",
    "expense analysis",
    "cost evaluation",
    "cost optimization analysis"
],

"kpi analysis": [
    "kpi tracking",
    "key performance indicator analysis",
    "performance metrics analysis",
    "kpi monitoring"
],

"workflow optimization": [
    "workflow improvement",
    "process workflow optimization",
    "workflow efficiency improvement"
],

"lean": [
    "lean methodology",
    "lean management",
    "lean process improvement"
],

"six sigma": [
    "six sigma methodology",
    "six sigma process improvement",
    "six sigma quality management"
],

"analytical thinking": [
    "analytical mindset",
    "critical thinking",
    "logical thinking",
    "analytical reasoning"
],

"problem solving": [
    "problem resolution",
    "solution development",
    "analytical problem solving"
],

"attention to detail": [
    "detail oriented",
    "high attention to detail",
    "accuracy focused"
],

"communication skills": [
    "verbal communication",
    "written communication",
    "effective communication"
],

"leadership": [
    "team leadership",
    "leadership skills",
    "team management"
]
}


# -----------------------------
# Education Database
# -----------------------------

EDUCATION_DB = [
"bachelor",
"master",
"phd",
"degree",
"life sciences",
"pharmacy",
"healthcare management",
"public health",
"epidemiology",
"health informatics",
"bioinformatics",
"finance",
"insurance",
"public policy"
]


# -----------------------------
# Normalize JD text
# -----------------------------
def normalize_text(text):

    text = text.lower()

    text = text.replace("-", " ")

    text = re.sub(r"[^\w\s]", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text




# Extract Role
# -----------------------------
def extract_role(text):
    roles_found = []

    for role in ROLE_DB:
        normalized_role = normalize_text(role)

        if re.search(r"\b" + re.escape(normalized_role) + r"\b", text):
            roles_found.append(role)

        elif role in ROLE_SYNONYMS:
            for variation in ROLE_SYNONYMS[role]:
                normalized_variation = normalize_text(variation)
                if re.search(r"\b" + re.escape(normalized_variation) + r"\b", text):
                    roles_found.append(role)
                    break

    if not roles_found:
        return ["Unknown"]

    # Remove duplicates
    roles_found = list(set(roles_found))

    # Sort by length descending (longer = more specific)
    roles_found.sort(key=len, reverse=True)

    # Remove generic roles that are substrings of a more specific role
    final_roles = []
    for role in roles_found:
        normalized_role = normalize_text(role)
        if not any(
            normalize_text(existing) != normalized_role and
            normalized_role in normalize_text(existing)
            for existing in final_roles
        ):
            final_roles.append(role)

    return final_roles




# -----------------------------
# Extract Skills
# -----------------------------

def extract_skills(text):

    skills_found = set()

    for skill in SKILLS_DB:

        if re.search(r"\b" + re.escape(skill) + r"\b", text):                           #if skill in text:
            skills_found.add(skill)

        if skill in SKILL_SYNONYMS:

            for synonym in SKILL_SYNONYMS[skill]:

                if re.search(r"\b" + re.escape(synonym) + r"\b", text):            #if synonym in text:
                    skills_found.add(skill)

    return sorted(list(skills_found))

# -----------------------------
# Extract Experience
# -----------------------------
def extract_experience(text):

    match = re.search(r"(\d+)\+?\s*(years|year|yrs|yr)",text)

    if match:
        return match.group(1) + " years"

    return "Not specified"


# -----------------------------
# Extract Education
# -----------------------------
def extract_education(text):

    for edu in EDUCATION_DB:
        if re.search(r"\b" + re.escape(edu) + r"\b", text):                 # if edu in text:
            return edu

    return "Not specified"


# -----------------------------
# Parse JD
# -----------------------------
def parse_job_description(jd_text):

    jd_text = normalize_text(jd_text)

    job_object = {
        "role": extract_role(jd_text),
        "skills_required": extract_skills(jd_text),
        "experience_required": extract_experience(jd_text),
        "education_required": extract_education(jd_text)
    }

    return job_object


# -----------------------------
# Run Parser for all JD files
# -----------------------------
if __name__ == "__main__":

    jd_folder = "data/job_descriptions/jd_samples/"
    output_folder = "data/job_descriptions/parsed_jd/"

    # ✅ ADD THIS — Clear old parsed files before writing fresh ones
    if os.path.exists(output_folder):
        for old_file in glob.glob(os.path.join(output_folder, "*.json")):
            os.remove(old_file)
        print("Cleared old parsed files.")

    os.makedirs(output_folder, exist_ok=True)
    # Get list of all .txt JD files
    jd_files = glob.glob(os.path.join(jd_folder, "*.txt"))

    if not jd_files:
        print("No JD files found!")
        exit()
    # Process each JD file
    for jd_file in jd_files:

        with open(jd_file, "r", encoding="utf-8") as f:
            jd_text = f.read()

        parsed_jd = parse_job_description(jd_text)

        # Use filename to avoid overwriting files
        file_name = os.path.basename(jd_file).replace(".txt", "")

        output_file = os.path.join(output_folder, f"{file_name}_parsed_jd.json")
       #  Save parsed JD
        with open(output_file, "w", encoding="utf-8") as outfile:
          json.dump(parsed_jd, outfile, indent=4)

        print(f"Parsed JD saved: {output_file}")




