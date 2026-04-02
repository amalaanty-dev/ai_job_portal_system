from utils.logger import log_event

log_event("System started")
print("AI Job Portal System Started")

print("AI Job Portal System Started")

from parsers.resume_text_extractor import process_resume_folder

input_folder = "data/resumes"
output_file = "data/extracted_text/resume_text.json"

process_resume_folder(input_folder, output_file)

print("Resume extraction completed")