---
name: register-project
description: Register an ingested email as a project request record in tracking-data/spreadsheet.md. Use after the ingest-email skill returns status "new" or "archived_not_registered", passing its email_id. Never use for a "duplicate".
---

# Register the email as a project record

Run this command from the project root, replacing `<email_id>` with the
`email_id` from the ingest-email result:

```bash
python3 .claude/skills/register-project/register.py <email_id>
```

Pass only the `email_id`. The script looks the email up in the archive index,
verifies the archived file's SHA-256 checksum, and builds the record from the
archived file itself, so the spreadsheet always matches the source. Never
write or edit spreadsheet rows yourself.

## What the result means

- `"status": "registered"` — one row was added; `record` shows it, including
  its `Record ID` and `State` (`Registered`).
- An `error` key — nothing was added (for example: unknown `email_id`,
  already registered, or a checksum mismatch). Stop, and report the error.
