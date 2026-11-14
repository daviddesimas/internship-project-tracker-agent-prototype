import os
import sys
from email_store import parse_email, unique_key, load_index, staged_email, find_record, archived_this_staging, result_line

# ── Last step of /track: confirm the outcome, then clear in/ ──────
# Usage: python3 finish_run.py
# Checks the archive index and spreadsheet, not Claude's account of the run:
# the staged email must be archived AND registered. Only then is in/ cleared.
# Otherwise the email stays in in/, and prepare.py refuses the next run.
#
# Prints the run's result from the data itself, in the same format as
# Tracker (API)'s tracker.py:
#   RESULT: NEW — registered as Record N · email_0000N.eml · Email ID … · sender · "subject"
#   RUN OK — <file> is archived as email_0000N.eml and registered; cleared it from in/.

def main():
    staged = staged_email()
    if staged is None:
        print("RUN FAILED — expected exactly one email in in/; nothing to confirm.")
        return 1
    staged_file, staged_path = staged

    with open(staged_path, "rb") as f:
        key = unique_key(parse_email(f.read()))
    entry = next((e for e in load_index() if e["unique_key"] == key), None)
    record = find_record(entry["email_id"]) if entry else None

    if record is not None:
        print(result_line(record, archived_this_staging(entry["trace_email_name"], staged_path)))
        os.remove(staged_path)
        print(f"RUN OK — {staged_file} is archived as {entry['trace_email_name']} "
              f"and registered; cleared it from in/.")
        return 0
    print(f"RUN FAILED — {staged_file} is not both archived and registered; left in in/ for review.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
