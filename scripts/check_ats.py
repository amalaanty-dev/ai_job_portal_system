import glob
import json

files = glob.glob("ats_results/ats_scores/*.json")

for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fp:
            d = json.load(fp)

        if "identifiers" not in d:
            print("NO IDENTIFIERS:", f)

        elif not d["identifiers"].get("resume_id"):
            print("NO RESUME_ID:", f)

    except Exception as e:
        print("BAD JSON:", f, e)

print("Check complete.")