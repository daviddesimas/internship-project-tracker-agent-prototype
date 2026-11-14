import os
import re
import json
import uuid
import hashlib
from datetime import datetime
from email import message_from_bytes
from email.utils import parseaddr, parsedate_to_datetime
import utils
import paths

# ── Tool definition (what Claude sees) ────────────────────────────
# Claude reads "description" to decide WHEN to call this tool, and
# "input_schema" to know WHAT arguments to send. There are no
# arguments: the run always stages exactly one email in in/.
INGEST_EMAIL_TOOL = {
    "name": "ingest_email",
    "description": (
        "Ingest the one email staged for this run. Parses it into the sender's name, subject, "
        "date, time, body, and attachment names, and checks whether the same email (same sender "
        "name and body) was already ingested. A new email is archived and given an email_id. "
        "Returns status 'new', 'duplicate' (already archived and registered), or "
        "'archived_not_registered' (archived by an earlier run that did not finish). "
        "Call this first in every run."
    ),
    "input_schema": {"type": "object", "properties": {}}
}

# ── Parsing, shared with register_project ─────────────────────────
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

# ── Run summary: printed by tracker.py, never by Claude ───────────
# (Tracker (Claude Code) has its own copy of these in email_store.py; keep them matching.)

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

# ── The function that actually runs when Claude calls the tool ────
def ingest_email():
    utils.trace(">>> ingest_email() CALLED")

    staged = paths.list_files(paths.IN_DIR)
    if len(staged) != 1:
        return {"error": f"Expected exactly one email in in/, found {len(staged)}: {staged}"}
    staged_file = staged[0]
    staged_path = os.path.join(paths.IN_DIR, staged_file)

    with open(staged_path, "rb") as f:
        raw = f.read()
    fields = parse_email(raw)
    key = unique_key(fields)

    # ── Duplicate check against the index (never scans the archive) ─
    index = load_index()
    existing = next((e for e in index if e["unique_key"] == key), None)
    if existing and existing["email_id"] not in registered_email_ids():
        # An earlier run archived it but never registered it — let this run finish the job
        utils.trace("ARCHIVED, NOT REGISTERED — earlier run did not finish", f"email_id={existing['email_id']}")
        return {"status": "archived_not_registered", "email_id": existing["email_id"],
                "trace_email_name": existing["trace_email_name"],
                "message": "Already archived by an earlier run but never registered. Register it now."}
    if existing:
        utils.trace("DUPLICATE — not archived", f"email_id={existing['email_id']}")
        return {"status": "duplicate", "email_id": existing["email_id"],
                "trace_email_name": existing["trace_email_name"],
                "message": "Same sender and body as an email already ingested and registered. Nothing was archived."}

    # ── Archive an exact copy; "xb" refuses to overwrite an existing file ─
    os.makedirs(paths.ARCHIVE_DIR, exist_ok=True)
    trace_email_name = f"email_{len(index) + 1:05d}.eml"
    archive_path = os.path.join(paths.ARCHIVE_DIR, trace_email_name)
    with open(archive_path, "xb") as f:
        f.write(raw)
    os.chmod(archive_path, 0o444)   # read-only: archive files are never modified

    entry = {
        "email_id": str(uuid.uuid4()),
        "trace_email_name": trace_email_name,
        "sha256": hashlib.sha256(raw).hexdigest(),   # lets an audit detect tampering
        "unique_key": key,
        "sender_name": fields["name"],
        "staged_file": staged_file,
        "archived_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(paths.ARCHIVE_INDEX, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    # The staged copy stays in in/; tracker.py clears it once the run is confirmed

    return {"status": "new", "email_id": entry["email_id"],
            "trace_email_name": trace_email_name, **fields}
