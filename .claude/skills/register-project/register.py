import os
import sys
import hashlib
from datetime import datetime

# Shared modules live in the project root, three folders up
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import paths
import states
from email_store import parse_email, load_index, registered_email_ids, print_result

# ── Register an archived email as a record in the tracking spreadsheet ─
# Usage: python3 .claude/skills/register-project/register.py <email_id>
# Builds the record from the archived file itself, so the data can't be
# altered on the way. Prints one JSON object: "status": "registered", or "error".
COLUMNS = ["Record ID", "Email ID", "Trace Email Name", "Submitted By", "Subject",
           "Date", "Time", "Attachments", "Body Preview", "Registered Timestamp",
           "Analyst", "Assigned", "Purpose", "Priority", "State"]
BODY_PREVIEW_CHARS = 80

def _cell(text):
    """Make text safe for one markdown table cell: one line, no bare pipes."""
    return " ".join(str(text).split()).replace("|", "\\|")

def register_project(email_id):
    entry = next((e for e in load_index() if e["email_id"] == email_id), None)
    if entry is None:
        return {"error": f"No archived email with email_id '{email_id}'."}

    registered_ids = registered_email_ids()
    if email_id in registered_ids:
        return {"error": f"email_id '{email_id}' is already registered; the spreadsheet was not changed."}

    # Read the archived copy and confirm it still matches its checksum
    with open(os.path.join(paths.ARCHIVE_DIR, entry["trace_email_name"]), "rb") as f:
        raw = f.read()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        return {"error": f"Checksum mismatch for {entry['trace_email_name']}: the archive may have been altered."}
    fields = parse_email(raw)

    # ── Build and append the record ───────────────────────────────
    preview = " ".join(fields["body"].split())
    if len(preview) > BODY_PREVIEW_CHARS:
        preview = preview[:BODY_PREVIEW_CHARS].rstrip() + "…"
    row = [len(registered_ids) + 1, email_id, entry["trace_email_name"], fields["name"],
           fields["subject"], fields["date"], fields["time"],
           ", ".join(fields["attachments"]) or "(none)", preview,
           datetime.now().isoformat(timespec="seconds"),
           "", "", "", "",               # Analyst, Assigned, Purpose, Priority: set by analysts
           states.INITIAL_STATE]

    os.makedirs(paths.TRACKING_DIR, exist_ok=True)
    if not os.path.isfile(paths.SPREADSHEET):
        with open(paths.SPREADSHEET, "w", encoding="utf-8") as f:
            f.write("# Project Requests\n\n")
            f.write("| " + " | ".join(COLUMNS) + " |\n")
            f.write("|" + "---|" * len(COLUMNS) + "\n")
    with open(paths.SPREADSHEET, "a", encoding="utf-8") as f:
        f.write("| " + " | ".join(_cell(v) for v in row) + " |\n")

    return {"status": "registered", "record": dict(zip(COLUMNS, row))}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(print_result({"error": "Usage: register.py <email_id>"}))
    try:
        result = register_project(sys.argv[1].strip())
    except Exception as e:
        result = {"error": f"register failed: {type(e).__name__}: {e}"}
    sys.exit(print_result(result))
