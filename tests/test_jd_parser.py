import unittest
import os
import glob

from parsers.jd_parser import parse_job_description


class TestJDParser(unittest.TestCase):

    roles = [

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
    "Healthcare BI (Business Intelligence) Analyst",
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
    "Real-World Evidence (RWE) Analyst",
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

    def test_all_roles(self):

        for role in self.roles:

            jd = f"{role} with 2 years experience in Python and SQL. Bachelor's degree required."

            result = parse_job_description(jd)

            self.assertEqual(result["role"], role)


    def test_skill_extraction(self):

        jd = "Healthcare Data Analyst with Python, SQL and Tableau skills."

        result = parse_job_description(jd)

        self.assertIn("python", result["skills_required"])
        self.assertIn("sql", result["skills_required"])


    def test_experience_extraction(self):

        jd = "Healthcare Data Analyst with 5 years experience."

        result = parse_job_description(jd)

        self.assertEqual(result["experience_required"], "5 years")


    def test_education_extraction(self):

        jd = "Healthcare Data Analyst role. Master's degree required."

        result = parse_job_description(jd)

        self.assertEqual(result["education_required"], "master")

    def test_batch_parsing_from_files(self):
        """Optional: test parsing of all JD files in jd_samples folder"""
        jd_folder = "data/job_descriptions/jd_samples/"
        
        jd_files = glob.glob(os.path.join(jd_folder, "*.txt"))
        self.assertTrue(len(jd_files) > 0, "No JD files found for batch test")
        for jd_file in jd_files:
            with open(jd_file, "r", encoding="utf-8") as f:
                jd_text = f.read()
            parsed = parse_job_description(jd_text)
            self.assertNotEqual(parsed["role"], "Unknown", f"Role not found in {jd_file}")
            self.assertIsInstance(parsed["skills_required"], list)
            self.assertIn("experience_required", parsed)
            self.assertIn("education_required", parsed)


if __name__ == "__main__":
    unittest.main()
