import json
import sys

# ── Print the output of `claude -p "/track" --output-format json` ──
# Used by run.sh for Tracker (Claude Code). Reads the JSON on stdin and prints
# a header with the model(s) Claude Code actually used (modelUsage) and the
# staged email's name (passed by run.sh as the first argument, since finish_run.py
# clears in/ during the run), then Claude's reply text.
# Anything that isn't the expected JSON is printed as-is.

raw = sys.stdin.read()
try:
    data = json.loads(raw)
    models = ", ".join(data.get("modelUsage") or {}) or "unknown"
    print(f"Email Tracker (Claude Code) — model: {models}")
    if len(sys.argv) > 1 and sys.argv[1]:
        print(f"Processing {sys.argv[1]}")
    print()
    print(data.get("result", ""))
except (ValueError, AttributeError):
    print(raw, end="")
