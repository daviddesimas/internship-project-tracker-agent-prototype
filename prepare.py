import os
import sys
import shutil
import paths

# ── Step 1 of a run: stage one mock email in in/ ──────────────────
# Usage: python3 prepare.py [mock_email_name]  — omit the name to pick from a list
# Then run: ./run.sh api   — Tracker (API)
#       or: ./run.sh cc    — Tracker (Claude Code), or /track inside Claude Code
# (In phase 2, a mailbox connector replaces this step.)

def stage_email(mock_name=None):
    """Copy exactly one mock email into in/. Returns its name, or None."""
    if paths.list_files(paths.IN_DIR):
        print(f"in/ is not empty: {paths.list_files(paths.IN_DIR)}. "
              "A previous run may not have finished; check it, then clear in/.")
        return None

    mocks = paths.list_files(paths.MOCK_EMAIL_DIR)
    if mock_name is None:
        for i, name in enumerate(mocks, 1):
            print(f"  {i}. {name}")
        choice = input("Stage which email? (number or name): ").strip()
        mock_name = mocks[int(choice) - 1] if choice.isdigit() and 0 < int(choice) <= len(mocks) else choice
    if mock_name not in mocks:
        print(f"No mock email named '{mock_name}'. Available: {mocks}")
        return None

    os.makedirs(paths.IN_DIR, exist_ok=True)
    shutil.copyfile(os.path.join(paths.MOCK_EMAIL_DIR, mock_name), os.path.join(paths.IN_DIR, mock_name))
    return mock_name

if __name__ == "__main__":
    staged = stage_email(sys.argv[1] if len(sys.argv) > 1 else None)
    if staged:
        print(f"\nStaged {staged} in in/. Next: ./run.sh api  (Tracker API) or ./run.sh cc  (Tracker Claude Code)")
    else:
        sys.exit(1)
