# Email Tracker (tiny-toy, Claude Code version)

This project tracks incoming project-request emails. Each run takes the one
email staged in `in/`, archives it for audit, and records it in a tracking
spreadsheet. Run it with the `/track` command.

## Two trackers, separate code

This folder holds two independent implementations that share the same data
folders. Keep their code separate: a change to one does not go into the other
unless the developer asks.

- **Tracker (Claude Code)** — what `/track` runs: `.claude/commands/track.md`,
  `.claude/skills/*`, `email_store.py`, `finish_run.py`.
- **Tracker (API)** — `tracker.py`, `agent_loop.py`, `call_model.py`,
  `api_helpers.py`, `tracker_tools.py`, `tool_ingest.py`, `tool_register.py`,
  `utils.py`. It calls the Claude API itself. Never run `tracker.py` or any of
  these files during a `/track` run.
- Shared by both: `paths.py`, `states.py`, `prepare.py`, `reset.py`, `run.sh`,
  `choose_models.py`, `cc_output.py`.

## Folders

- `mock_emails/` — read-only source emails (golden test data). Never change.
- `in/` — staging area: exactly one email at the start of a run.
- `email_archive/` — write-once archive (`email_0000K.eml`) plus the
  append-only index `archive_index.jsonl`. Never edit, move or delete anything here.
- `tracking-data/spreadsheet.md` — the tracker. Never edit rows by hand.

## Rules

- Change `in/`, `email_archive/` and `tracking-data/` only by running the
  skill scripts and `finish_run.py`. Never with Edit, Write, `rm`, `mv` or `chmod`.
- Never compute checksums, GUIDs, record IDs or archive numbers yourself; the
  scripts do this exactly.
- Never run `reset.py`, `prepare.py`, `run.sh`, `tracker.py`, `choose_models.py` or `cc_output.py`.
  Those are for the developer.
- A unique email = sender name + body. Duplicates are never archived or registered.

## Record states

Each record is in exactly one state. Typical path:
Registered → Under Review → Reviewed → Active → Verified → Deployed.
Reviewed can also go to Deferred (backlog; may go to Active later) or
Rejected. Any open record can be Closed, and Closed is final. Records are
never deleted. The allowed moves are defined in `states.py`.
