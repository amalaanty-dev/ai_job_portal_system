import os
import json

PREDICTED_FOLDER = "data/resumes/sectioned_resumes/"
LABELED_FOLDER = "data/resumes/labeled_sections/"
REPORT_FILE = "datasets/section_detection_reports/section_accuracy_report.txt"

os.makedirs("data/datasets/section_detection_reports/", exist_ok=True)


SECTIONS = [
    "skills",
    "experience",
    "education",
    "projects",
    "certifications"
]


def evaluate():

    total = 0
    correct = 0

    results = []

    for file in os.listdir(LABELED_FOLDER):

        if not file.endswith(".json"):
            continue

        label_path = os.path.join(LABELED_FOLDER, file)

        predicted_file = file.replace("_labels.json", "_sections.json")
        predicted_path = os.path.join(PREDICTED_FOLDER, predicted_file)

        if not os.path.exists(predicted_path):
            print("Missing prediction for:", file)
            continue

        with open(label_path, "r") as f:
            labels = json.load(f)

        with open(predicted_path, "r") as f:
            predicted = json.load(f)

        for section in SECTIONS:

            actual = labels.get(section, False)
            detected = len(predicted.get(section, [])) > 0

            if actual == detected:
                correct += 1

            total += 1

            results.append({
                "file": file,
                "section": section,
                "actual": actual,
                "detected": detected
            })

    accuracy = (correct / total) * 100 if total > 0 else 0

    report = f"""
Resume Section Detection Accuracy Report
---------------------------------------

Total Section Checks: {total}
Correct Predictions: {correct}

Overall Accuracy: {accuracy:.2f} %

"""

    with open(REPORT_FILE, "w") as f:
        f.write(report)

    print(report)
    print("Report saved to:", REPORT_FILE)


if __name__ == "__main__":
    evaluate()