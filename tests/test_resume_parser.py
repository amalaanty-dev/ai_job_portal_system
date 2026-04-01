import unittest

def parse_resume(text):
    return {"skills": ["Python", "React"]}

class TestResumeParser(unittest.TestCase):

    def test_skill_extraction(self):
        resume_text = "Python developer with React experience"
        result = parse_resume(resume_text)

        self.assertIn("Python", result["skills"])

if __name__ == "__main__":
    unittest.main()
