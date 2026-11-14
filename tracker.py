import os
import sys
import agent_loop
import api_helpers
import tracker_tools
import paths
from tool_ingest import parse_email, unique_key, load_index, find_record, archived_this_staging, result_line

# Fallback model when run directly (python3 tracker.py). Through run.sh the model comes
# from TRACKER_API_MODEL, .models (menu 6) or default_models, in that order.
MODEL = os.environ.get("TRACKER_API_MODEL") or "claude-sonnet-5-5"

SYSTEM_PROMPT = """You are an email tracking assistant. Each run has exactly one staged email.
First call ingest_email. If it returns status 'new' or 'archived_not_registered', call
register_project with its email_id. If it returns 'duplicate', do not register it.
When done, report in one or two short lines: if newly registered, its Record ID, Email ID
and Trace Email Name; if a duplicate, the existing Email ID. Do not list the other record
fields: the tracker prints the full result itself."""

RUN_PROMPT = "Process the staged email."

# ── Step 2 of a run: process the email that prepare.py staged ─────
# Usage: python3 tracker.py

def main():
    staged = paths.list_files(paths.IN_DIR)
    if len(staged) != 1:
        print(f"Expected exactly one email in in/, found {len(staged)}: {staged}. "
              "Run prepare.py first.")
        sys.exit(1)
    staged_path = os.path.join(paths.IN_DIR, staged[0])
    with open(staged_path, "rb") as f:
        staged_key = unique_key(parse_email(f.read()))

    api_client = api_helpers.get_client()
    api_helpers.validate_model(api_client, MODEL)   # lists available models if MODEL is wrong

    print(f"Email Tracker (API) — model: {MODEL}\nProcessing {staged[0]}\n")

    # *** The call into the agent loop ***
    reply = agent_loop.run_agent_loop(
        api_client,                 # api_client
        MODEL,                      # api_model
        SYSTEM_PROMPT,              # api_system_prompt
        tracker_tools.tool_dispatcher,  # tool_dispatcher
        tracker_tools.TOOLS,        # agent_tools
        RUN_PROMPT,                 # prompt
        "Operator",                 # user_name (agent_loop prefixes "My name is Operator")
    )
    print(f"\nClaude: {reply}")

    # ── Check the outcome from the archive and spreadsheet, not from Claude's reply ─
    # The staged email must be archived AND have a spreadsheet record. Only then is
    # in/ cleared. The result block matches Tracker (Claude Code)'s finish_run.py.
    entry = next((e for e in load_index() if e["unique_key"] == staged_key), None)
    record = find_record(entry["email_id"]) if entry else None
    print()
    if record is not None:
        print(result_line(record, archived_this_staging(entry["trace_email_name"], staged_path)))
        os.remove(staged_path)
        print(f"RUN OK — {staged[0]} is archived as {entry['trace_email_name']} "
              f"and registered; cleared it from in/.")
    else:
        print(f"RUN FAILED — {staged[0]} is not both archived and registered; left in in/ for review.")
        sys.exit(1)

if __name__ == "__main__":
    main()
