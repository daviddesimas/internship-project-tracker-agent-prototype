# tiny-toy — Email Tracker (two implementations)

Each run takes one incoming email, archives it for audit, and records it as a
project request in a tracking spreadsheet. For now, emails come from
`mock_emails/`; phase 2 will connect to a real mailbox, and the mock emails
become golden test data for regression testing.

This is **one codebase with two separate trackers**. They do the same job,
write the same data folders, and are both started from `./run.sh`:

| | Tracker (API) | Tracker (Claude Code) |
|---|---|---|
| Start it with | `./run.sh api` (menu 3), or `./run.sh api-debug` (menu 5) for traces | `./run.sh cc` (menu 4), or `/track` inside Claude Code |
| Who runs the agent loop | Your code: `run_agent_loop()` in `agent_loop.py` | Claude Code (the CLI harness) |
| How it reaches Claude | `call_model.call_model(...)` → `client.messages.create(...)` | The `claude` CLI |
| How Claude learns the tools | JSON tool definitions in `tool_ingest.py`, `tool_register.py` | `SKILL.md` instructions in `.claude/skills/` |
| Who pays | Your Claude Console account (`ANTHROPIC_API_KEY`) | Your claude.ai plan (Pro) |

Either tracker can process the next staged email, and the duplicate check
works across both, because they share the archive index and spreadsheet.

## Tracker (API): your own agent loop

`tracker.py` → `agent_loop.run_agent_loop()` → `call_model.call_model()`. That
last call is the **only** place this tracker talks to Claude:

```python
response = call_model.call_model(api_client, api_system_prompt, api_user_prompt, api_model, agent_tools)
```

`run_agent_loop()` sends the system prompt, the conversation history and the
two tool definitions. When Claude asks for a tool, it runs it through
`tracker_tools.tool_dispatcher()`, sends the result back, and repeats until
Claude answers in text (at most 10 rounds). `api_helpers.get_client()` builds
the client from `ANTHROPIC_API_KEY`, so every call is billed to your Claude
Console account. After the loop, `tracker.py` checks the archive and
spreadsheet itself and clears `in/` only on success.

**Output.** `./run.sh api` (menu 3) prints only the summary: the email being
processed, Claude's short reply, and the result block (see **Run result block**
below). `./run.sh api-debug`
(menu 5) runs the same code and also prints every loop step as
`[TRACE hh:mm:ss]` lines: each API call, stop reason, token counts, tool
dispatch and result. Tracing is switched by `TRACKER_TRACE` in `utils.py`, so
`TRACKER_TRACE=1 python3 tracker.py` does the same outside `run.sh`.

## Run result block (both trackers)

Both trackers end every run with the same block, printed by Python from the
archive and spreadsheet, never written by Claude:

```
RESULT: NEW — registered as Record 1 (email_00001.eml)
  Email ID:    09b5b835-37fd-413c-8ca8-634c4b7c708b
  From:        Marcus Lee
  Subject:     New project request: Customer portal redesign
  Sent:        2026-11-11 at 09:15
  Attachments: portal_requirements.docx, current_portal_screens.zip
  State:       Registered (Analyst, Assigned, Purpose, Priority still blank)
RUN OK — marcus_01.txt is archived as email_00001.eml and registered; cleared it from in/.
```

For a duplicate, the first line is `RESULT: DUPLICATE — already registered as
Record 1 (email_00001.eml); nothing archived or registered`, followed by the
existing record's details. A failed run prints only `RUN FAILED — …` and
leaves the email in `in/`.

- **Tracker (API):** `tracker.py` prints the block after Claude's reply.
- **Tracker (Claude Code):** `finish_run.py` prints it, and `/track` tells
  Claude to end its reply with it copied exactly. If Claude skipped
  `finish_run.py`, `./run.sh cc` runs it, and the block comes straight from
  Python.

**NEW or DUPLICATE** is decided from file times, not from Claude: if the
archived `.eml` was created after the email was staged in `in/`, this staging
was archived (NEW, including a retry after a failed run); if it already
existed, the email is a DUPLICATE. This relies on `prepare.py` staging a fresh
copy, so don't stage with `cp -p` or `mv`, which keep the old file time.

Claude's own reply above the lines is kept to one or two lines by the same
reporting instruction in both trackers (`SYSTEM_PROMPT` in `tracker.py`, and
`.claude/commands/track.md`).

## Tracker (Claude Code): skills in the Claude Code harness

`./run.sh cc` runs `claude -p "/track"`. Claude Code is the agent loop; your
code never calls the API. The pieces:

- **`.claude/commands/track.md`** — the `/track` command: the three steps of a
  run (plays the role of `SYSTEM_PROMPT`).
- **`.claude/skills/<name>/SKILL.md`** — a **skill** is plain-language
  instructions: which command to run, and what its JSON result means. It does
  not contain or wrap Python code itself.
- **`ingest.py`, `register.py`** (next to each `SKILL.md`) — the deterministic
  Python. Each ends with an `if __name__ == "__main__":` block, so Claude can
  run it from Bash and read one JSON object back. That block is the wrapper:
  it does the job that `tool_dispatcher()` and the JSON tool definitions do in
  the API tracker.
- **`finish_run.py`** — the last step of `/track`: confirms the email is
  archived *and* registered, then clears `in/`. If Claude ever skips it,
  `./run.sh cc` runs it.
- **`CLAUDE.md`** and **`.claude/track-settings.json`** — the project rules,
  and the locked-down permissions for `/track` runs.

## Shared code and cloned code

The two trackers do **not** run the same Python files. The ingest and
register logic exists in two copies, one per tracker:

| Job | Tracker (API) | Tracker (Claude Code) |
|---|---|---|
| Ingest (parse, dedup, archive) | `tool_ingest.py` | `.claude/skills/ingest-email/ingest.py` + `email_store.py` |
| Register (add the spreadsheet row) | `tool_register.py` | `.claude/skills/register-project/register.py` |
| Final check, clear `in/` | inside `tracker.py` | `finish_run.py` |
| Result block (`find_record`, `archived_this_staging`, `result_line`) | `tool_ingest.py` | `email_store.py` |

Each pair started out identical, but they are separate files and **can
drift apart**. To keep both trackers producing the same results, make any
change to the ingest or register rules (duplicate rule, columns, archive
naming…) in both copies.

Truly shared by both: `paths.py`, `states.py`, `prepare.py`, `reset.py`,
`run.sh`, and the data folders. The archive format, index, spreadsheet
columns, IDs and duplicate rule are identical, so the same golden emails
produce the same archive and spreadsheet content (apart from GUIDs and
timestamps).

## Which account pays: the API key

`ANTHROPIC_API_KEY` decides billing, but **`run.sh` handles it for you**.

**Recommended: keep the key in the macOS Keychain, not in your shell.** Store
it once (it prompts for the "password": paste the `sk-ant-...` key, twice):

```bash
security add-generic-password -a "$USER" -s anthropic-api-key -w
security add-generic-password -U -a "$USER" -s anthropic-api-key -w   # replace it later
```

`./run.sh api` reads it from the Keychain and passes it to `tracker.py` only,
so you never export it. The first read may show a macOS dialog asking to let
`security` use your keychain: choose **Always Allow**.

| How you run it | Key exported in your shell | Key only in the Keychain |
|---|---|---|
| `./run.sh api` | Claude Console account (exported key wins) | Claude Console account |
| `./run.sh cc` | Claude Pro plan (`run.sh` removes the key for this call) | Claude Pro plan |
| `claude` / `/track` started by you, outside `run.sh` | Claude Console account (API billing) | Claude Pro plan |

With neither, `./run.sh api` stops with a message saying how to add the key.
The Keychain setup keeps the split clean: only the API tracker uses the API
account. An exported key, by contrast, also wins over your claude.ai login in
any Claude Code session you start yourself. Run `/status` inside Claude Code
to see which one it is using.

## Folder layout

```
tiny-toy/
├── CLAUDE.md                        project rules Claude always loads
├── .claude/
│   ├── track-settings.json          locked-down permissions for /track runs
│   ├── commands/track.md            /track: the run, step by step
│   └── skills/
│       ├── ingest-email/            SKILL.md + ingest.py
│       └── register-project/        SKILL.md + register.py
├── finish_run.py                    (Claude Code) confirms archived + registered, clears in/
├── email_store.py                   (Claude Code) parsing, uniqueness key, index, spreadsheet IDs
├── tracker.py                       (API) entry point: runs the loop, confirms, clears in/
├── agent_loop.py, call_model.py     (API) Messages API tool-use loop
├── api_helpers.py, utils.py         (API) client/provider setup; [TRACE] printing (off unless TRACKER_TRACE=1)
├── tracker_tools.py                 (API) tool list + dispatcher
├── tool_ingest.py, tool_register.py (API) the two tools: definitions + logic
├── paths.py, states.py              shared: folder locations; record states and moves
├── prepare.py, reset.py, run.sh     shared developer scripts (Claude never runs these)
├── choose_models.py                 shared: run.sh menu 6, saves model choices in .models
├── default_models                   shared: from-scratch default model for each tracker (committed)
├── cc_output.py                     shared: run.sh uses it to print the (Claude Code) reply and model
├── mock_emails/                     read-only source emails (golden test data)
├── in/                              staging area: exactly one email at the start of a run
├── email_archive/                   write-once: email_0000K.eml + archive_index.jsonl
└── tracking-data/spreadsheet.md     the tracker
```

`in/`, `email_archive/` and `tracking-data/` are created at runtime and are
not committed (see `.gitignore`).

## One run, end to end (Tracker (Claude Code))

Tracker (API) follows the same steps, with `tracker.py` and its tool loop in
place of `/track`, and its own outcome check in place of `finish_run.py`.

1. **Stage** — `prepare.py` copies one email from `mock_emails/` into `in/`.
   It refuses if `in/` isn't empty.
2. **`/track`** — Claude Code follows `.claude/commands/track.md`:
   1. **ingest-email skill** → runs `ingest.py`, which parses the staged
      email and returns JSON with a status:
      - `new` — archived as a read-only `email_0000K.eml`, with a GUID email
        ID and an index line holding the file's SHA-256.
      - `duplicate` — same sender and body as an email already archived and
        registered; nothing archived.
      - `archived_not_registered` — an earlier run archived it but failed
        before registering; this run registers it.
   2. **register-project skill** (for `new` / `archived_not_registered`) →
      runs `register.py <email_id>`, which verifies the checksum and builds the
      record from the archived file — Claude never writes spreadsheet rows.
   3. **`finish_run.py`** — checks the index and spreadsheet itself. If the
      email is archived *and* registered: the `RESULT:` line, `RUN OK`, and
      `in/` is cleared.
      Otherwise: `RUN FAILED`, and the email stays in `in/`, so `prepare.py`
      refuses the next run until someone looks.

If Claude ever skipped `finish_run.py`, `./run.sh cc` notices the email still
in `in/` and runs `finish_run.py` itself, so the final check always happens.

## Guardrails

- **`.claude/track-settings.json`** is loaded only for `/track` runs (via
  `--settings`). It allows just the three scripts and denies `rm`, `mv`,
  `chmod`, `reset.py`, `prepare.py`, `run.sh`, `tracker.py`, and any edit inside `in/`, `email_archive/`,
  `tracking-data/` and `mock_emails/`. It is deliberately *not*
  `.claude/settings.json`, which would lock down every Claude Code session in
  this folder, including development.
- **`CLAUDE.md`** states the rules: write-once archive, no hand edits, never
  compute checksums or IDs, never run the developer scripts.
- Exact work (dedup, GUIDs, SHA-256, numbering, record building) is always
  done by the scripts, never by the model.

## IDs and the audit trail

| ID | Example | Where it lives | Purpose |
|---|---|---|---|
| Record ID | `1`, `2`, `3`… | spreadsheet | The tracker's row number |
| Email ID | GUID `47d2a7ee-…` | spreadsheet, index | Permanent identity of the email |
| Trace Email Name | `email_00001.eml` | spreadsheet, index | The archived file |

**Unique email** = sender name + body (both trimmed). The index stores a
SHA-256 of that pair as `unique_key`.

**Audit:** spreadsheet row → Email ID → index line → `email_0000K.eml` →
recompute its SHA-256 and compare with the index.

**Spreadsheet columns:** Record ID, Email ID, Trace Email Name, Submitted By,
Subject, Date, Time, Attachments, Body Preview (first 80 characters),
Registered Timestamp, Analyst, Assigned, Purpose, Priority, State. New records
start in state `Registered`; Analyst, Assigned, Purpose and Priority start
blank for the business analysts.

## Record states

Each record is in exactly one state. Records are never deleted: `Closed` is
the end state. Defined in `states.py`.

```
Registered → Under Review → Reviewed → Active → Verified → Deployed
```

| State | Meaning | Can move forward to | Can move back to |
|---|---|---|---|
| Registered | Email ingested and recorded | Under Review, Closed | (none) |
| Under Review | Being reviewed by an analyst | Reviewed, Closed | Registered |
| Reviewed | Review finished; decision pending | Active, Deferred, Rejected, Closed | Registered, Under Review |
| Active | Assigned to a developer | Verified, Closed | Registered … Reviewed |
| Verified | Complete and ready to ship | Deployed, Closed | Registered … Active |
| Deployed | In production | Closed | Registered … Verified |
| Deferred | Not proceeding now; backlog item | Active, Closed | Registered … Reviewed |
| Rejected | Review decided not to do it | Closed | Registered … Reviewed |
| Closed | Done; kept for the record. Final. | (none) | (none) |

## Setup

- Python 3.
- **Tracker (API):** the `anthropic` package (`pip install anthropic`) and an
  API key, in the Keychain or exported (see **Which account pays**), or
  `AI_PROVIDER=bedrock` / `vertex`.
  The default model is in `default_models`; see **Choosing the model**.
- **Tracker (Claude Code):** Claude Code, signed in. Standard library only.

Billing for each tracker: see **Which account pays** above.

## Choosing the model

Each tracker has its own model setting, set from the menu with **6) models**
(`./run.sh models`). It lists the models your API key can use (live, from the
Models API) for Tracker (API), and the Claude Code aliases (`sonnet`, `opus`,
`fable`) for Tracker (Claude Code). You can also type any model name. Your
choices are saved in `.models`, a local file that is **not committed**:

```
api=claude-sonnet-4-6     Tracker (API): must be an exact API model ID
cc=sonnet                 Tracker (Claude Code): passed as: claude --model sonnet
```

The from-scratch defaults are in `default_models`, which **is** committed, so a
fresh clone starts on the same models. Both are Sonnet 5.5:

```
api=claude-sonnet-5-5
cc=claude-sonnet-5-5
```

Each run uses the first of these that is set, per tracker:

| Order | Source | Applies to |
|---|---|---|
| 1 | `TRACKER_API_MODEL=… ./run.sh api` / `TRACKER_CC_MODEL=… ./run.sh cc` | that one run |
| 2 | `.models` (menu 6) | this machine |
| 3 | `default_models` | everyone |

So Tracker (Claude Code) is always pinned: with no choice saved it runs
`--model claude-sonnet-5-5`, and it no longer follows your `/model` setting.
Choose **0) default** in the picker to remove a saved choice. The main menu
shows what each tracker will use, and every run prints the model it actually used on its
first line (`Email Tracker (API) — model: …`, `Email Tracker (Claude Code) —
model: …`). For Claude Code that comes from the model usage `claude` reports,
so it is what really ran. A wrong API model ID stops the run before any work,
with a list of the valid IDs. The saved choice applies only when you start a tracker
through `run.sh`; `python3 tracker.py` on its own uses `TRACKER_API_MODEL` or
`MODEL` in `tracker.py`. Typing `/track` in your own Claude Code session uses that
session's model.

## Run

```bash
./run.sh                      # menu: 1) reset  2) prepare  3) tracker-api  4) tracker-cc  5) tracker-api-debug  6) models  q) quit
./run.sh prepare jane_01.txt  # or run one action directly
./run.sh api                  # Tracker (API):         python3 tracker.py, summary only
./run.sh api-debug            # Tracker (API) with full [TRACE] debug output (TRACKER_TRACE=1)
./run.sh cc                   # Tracker (Claude Code): claude -p "/track" --settings .claude/track-settings.json
./run.sh models               # choose the model for each tracker
```

Or open Claude Code in this folder and type `/track` (that session uses your
normal permissions, not `track-settings.json`).

To start over (development only): `./run.sh reset` — empties `in/`,
`email_archive/` and `tracking-data/` after you type a random 4-digit code.
Never use it on real data.

## Mock email format

```
From: Marcus Lee <marcus.lee@example.com>
To: Operator <operator@example.com>
Subject: New project request: Customer portal redesign
Date: Wed, 11 Nov 2026 09:15:00 -0800
Attachments: portal_requirements.docx, current_portal_screens.zip

Hello,
...
```

`date` and `time` come from the `Date:` header, in the sender's time zone.

## Planned

- **State change log:** record every state change (who, when, from, to).
- **Separate test and live data** before any real email is processed, with
  `reset.py` refusing to run against live data.
