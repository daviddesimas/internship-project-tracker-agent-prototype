---
name: ingest-email
description: Ingest the one email staged in in/ for an email tracker run. Parses it, checks whether the same email (same sender name and body) was already ingested, and archives it if new. Use this first in every /track run.
---

# Ingest the staged email

Run exactly this command from the project root, with no arguments:

```bash
python3 .claude/skills/ingest-email/ingest.py
```

It prints one JSON object. Do not read, parse, copy or archive the email
yourself: the script does all of it, including the checksum and the GUID.

## What the result means

| `status` | Meaning | Next step |
|---|---|---|
| `new` | Archived as `trace_email_name` with a new `email_id` | Register it with the **register-project** skill, using `email_id` |
| `archived_not_registered` | An earlier run archived it but never registered it | Register it with the **register-project** skill, using `email_id` |
| `duplicate` | Same sender and body as an email already archived and registered | Do not register it |
| (`error` key instead) | Nothing was archived | Stop, and report the error |

For `new`, the result also has the parsed fields: `name`, `subject`, `date`,
`time`, `body`, `attachments`.
