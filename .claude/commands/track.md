---
description: Process the one email staged in in/ — ingest, register if new, then confirm and clear in/
allowed-tools: Skill, Bash(python3 .claude/skills/ingest-email/ingest.py), Bash(python3 .claude/skills/register-project/register.py:*), Bash(python3 finish_run.py)
---

Process the email staged for this run. Follow these steps in order, and run
each command from the project root.

1. Use the **ingest-email** skill.
2. If its `status` is `new` or `archived_not_registered`, use the
   **register-project** skill with its `email_id`. If it is `duplicate`, skip
   this step. If ingest returned an `error`, skip to step 3.
3. Always finish by running `python3 finish_run.py`, even if an earlier step
   failed. It checks the outcome and clears `in/` only on success.

When done, report in one or two short lines: if newly registered, its Record
ID, Email ID and Trace Email Name; if a duplicate, the existing Email ID. Do
not list the other record fields. Then end your reply with everything
`finish_run.py` printed (the `RESULT:` line, its indented detail lines, and the
`RUN OK` / `RUN FAILED` line), copied exactly as printed, line for line, with
no quotes, backticks or other formatting.
