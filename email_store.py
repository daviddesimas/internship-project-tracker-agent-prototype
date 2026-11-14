import os
import re
import json
import hashlib
from email import message_from_bytes
from email.utils import parseaddr, parsedate_to_datetime
import paths

# ── Shared, deterministic helpers used by the skill scripts and finish_run.py ─

def parse_email(raw_bytes):
    """Split a raw email into the fields the tracker uses."""
    msg = message_from_bytes(raw_bytes)

    # "Jane Doe <jane.doe@example.com>" -> "Jane Doe" (falls back to the address)
    sender_name, sender_address = parseaddr(msg.get("From", ""))

    # Split the Date header into separate date and time values
    date, time = "", ""
    if msg.get("Date"):
        try:
            sent = parsedate_to_datetime(msg["Date"])
            date, time = sent.strftime("%Y-%m-%d"), sent.strftime("%H:%M")
        except (TypeError, ValueError):
            date = msg["Date"]   # unparseable — pass it through as-is

    # The mock format lists attachments in a header: "Attachments: a.pdf, b.xlsx"
    attachments = [a.strip() for a in msg.get("Attachments", "").split(",") if a.strip()]

    return {
        "name": sender_name or sender_address,
        "subject": msg.get("Subject", ""),
        "date": date,
        "time": time,
        "body": msg.get_payload().strip(),
        "attachments": attachments,
    }

def unique_key(fields):
    """An email is unique by sender name + body (lightweight: just trimmed)."""
    text = fields["name"].strip() + "\n" + fields["body"].strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_index():
    """All archive index entries, oldest first."""
    if not os.path.isfile(paths.ARCHIVE_INDEX):
        return []
    with open(paths.ARCHIVE_INDEX, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def registered_email_ids():
    """Email IDs that have a spreadsheet record (column 2 of each data row)."""
    if not os.path.isfile(paths.SPREADSHEET):
        return []
    with open(paths.SPREADSHEET, encoding="utf-8") as f:
        rows = [line for line in f if line.startswith("| ") and not line.startswith("| Record ID")]
    return [row.split("|")[2].strip() for row in rows]

def staged_email():
    """(file name, path) of the one email in in/, or None if there isn't exactly one."""
    staged = paths.list_files(paths.IN_DIR)
    if len(staged) != 1:
        return None
    return staged[0], os.path.join(paths.IN_DIR, staged[0])

def print_result(result):
    """Skill scripts report back to Claude as one JSON object on stdout."""
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if "error" in result else 0

# ── Run summary: printed by finish_run.py, never by Claude ────────
# (Tracker (API) has its own copy of these in tool_ingest.py; keep them matching.)

def find_record(email_id):
    """The spreadsheet record for email_id as {column: value}, or None."""
    if not os.path.isfile(paths.SPREADSHEET):
        return None
    header = None
    with open(paths.SPREADSHEET, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("| "):
                continue
            # split on unescaped pipes only; cells escape "|" as "\|"
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if header is None:
                header = cells
                continue
            record = dict(zip(header, cells))
            if record.get("Email ID") == email_id:
                return record
    return None

def archived_this_staging(trace_email_name, staged_path):
    """True if the archived copy was created after the email was staged in in/:
    this run archived it (or an earlier, failed attempt on the same staging did).
    False if it was already in the archive, so the staged email is a duplicate.
    Uses file times, which are precise to well under a second: the archive file
    is written once and never modified, and prepare.py stages a fresh copy."""
    archived = os.path.getmtime(os.path.join(paths.ARCHIVE_DIR, trace_email_name))
    return archived >= os.path.getmtime(staged_path)

ANALYST_FIELDS = ["Analyst", "Assigned", "Purpose", "Priority"]

def result_line(record, is_new):
    """What this run did, built from the spreadsheet record: a RESULT line, then
    the record's details (for a duplicate, the existing record's)."""
    ref = f"Record {record['Record ID']} ({record['Trace Email Name']})"
    if is_new:
        head = f"RESULT: NEW — registered as {ref}"
    else:
        head = f"RESULT: DUPLICATE — already registered as {ref}; nothing archived or registered"
    sent = f"{record['Date']} at {record['Time']}" if record["Time"] else record["Date"]
    blank = [f for f in ANALYST_FIELDS if not record.get(f)]
    state = record["State"] + (f" ({', '.join(blank)} still blank)" if blank else "")
    details = [("Email ID", record["Email ID"]), ("From", record["Submitted By"]),
               ("Subject", record["Subject"]), ("Sent", sent),
               ("Attachments", record["Attachments"]), ("State", state)]
    return "\n".join([head] + [f"  {label + ':':<13}{value}" for label, value in details])
