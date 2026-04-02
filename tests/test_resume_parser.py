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

import unittest
import os
from parsers.resume_text_extractor import process_resume_folder


class TestResumeParser(unittest.TestCase):

    def test_resume_processing(self):

        input_folder = "data/resumes"
        output_file = "data/extracted_text/test_output.json"

        process_resume_folder(input_folder, output_file)

        # Check if output file is created
        self.assertTrue(os.path.exists(output_file))


if __name__ == "__main__":
    unittest.main()