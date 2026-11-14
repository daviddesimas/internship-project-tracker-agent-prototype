import os
import sys
import json
import uuid
import hashlib
from datetime import datetime

# Shared modules live in the project root, three folders up
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import paths
from email_store import parse_email, unique_key, load_index, registered_email_ids, staged_email, print_result

# ── Ingest the one staged email: dedup, then archive if new ───────
# Usage: python3 .claude/skills/ingest-email/ingest.py
# Prints one JSON object with "status": new | duplicate | archived_not_registered,
# or "error". Never deletes the staged email; finish_run.py does that.
def ingest_email():
    staged = staged_email()
    if staged is None:
        found = paths.list_files(paths.IN_DIR)
        return {"error": f"Expected exactly one email in in/, found {len(found)}: {found}"}
    staged_file, staged_path = staged

    with open(staged_path, "rb") as f:
        raw = f.read()
    fields = parse_email(raw)
    key = unique_key(fields)

    # ── Duplicate check against the index (never scans the archive) ─
    index = load_index()
    existing = next((e for e in index if e["unique_key"] == key), None)
    if existing and existing["email_id"] not in registered_email_ids():
        # An earlier run archived it but never registered it — let this run finish the job
        return {"status": "archived_not_registered", "email_id": existing["email_id"],
                "trace_email_name": existing["trace_email_name"],
                "message": "Already archived by an earlier run but never registered. Register it now."}
    if existing:
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

    return {"status": "new", "email_id": entry["email_id"],
            "trace_email_name": trace_email_name, **fields}

if __name__ == "__main__":
    try:
        result = ingest_email()
    except Exception as e:
        result = {"error": f"ingest failed: {type(e).__name__}: {e}"}
    sys.exit(print_result(result))
