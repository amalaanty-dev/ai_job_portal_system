import os
import json

SECTIONED_FOLDER = "data/resumes/sectioned_resumes/"
LABEL_FOLDER = "data/resumes/labeled_sections/"

os.makedirs(LABEL_FOLDER, exist_ok=True)


def generate_labels():

    for file in os.listdir(SECTIONED_FOLDER):

        if not file.endswith("_sections.json"):
            continue

        file_path = os.path.join(SECTIONED_FOLDER, file)

        with open(file_path, "r", encoding="utf-8") as f:
            sections = json.load(f)

        labels = {}

        # check if section contains data
        for section, content in sections.items():

            if section == "other":
                continue

            if len(content) > 0:
                labels[section] = True
            else:
                labels[section] = False

        label_file = file.replace("_sections.json", "_labels.json")

        output_path = os.path.join(LABEL_FOLDER, label_file)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(labels, f, indent=4)

        print("Generated label:", label_file)


if __name__ == "__main__":
    generate_labels()