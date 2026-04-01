import unittest
from ats_engine.ats_scoring import ats_score

class TestATSEngine(unittest.TestCase):

    def test_skill_match(self):
        resume = ["Python", "SQL", "Machine Learning"]
        job = ["Python", "Machine Learning", "AWS"]

        score = ats_score(resume, job)

        self.assertGreater(score, 50)

    def test_no_match(self):
        resume = ["HTML", "CSS"]
        job = ["Python", "Machine Learning"]

        score = ats_score(resume, job)

        self.assertEqual(score, 0)

if __name__ == "__main__":
    unittest.main()