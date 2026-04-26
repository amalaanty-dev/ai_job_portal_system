import unittest
from scoring.decision_engine import final_decision

class TestScoringEngine(unittest.TestCase):

    def test_strong_hire(self):
        self.assertEqual(final_decision(85), "Strong Hire")

    def test_consider(self):
        self.assertEqual(final_decision(60), "Consider")

    def test_reject(self):
        self.assertEqual(final_decision(30), "Reject")

if __name__ == "__main__":
    unittest.main()