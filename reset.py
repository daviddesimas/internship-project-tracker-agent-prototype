import os
import sys
import shutil
import random
import paths

# ── TESTING ONLY: wipe all runtime data for a fresh run ───────────
# Clears in/, email_archive/ and tracking-data/. mock_emails/ is never touched.
# This deletes the write-once archive, so never point it at real data.
# Usage: python3 reset.py         — asks you to type a random 4-digit code
#        python3 reset.py --yes   — no prompt (for scripted regression tests)
RESET_DIRS = [paths.IN_DIR, paths.ARCHIVE_DIR, paths.TRACKING_DIR]

def contents(folder):
    """Everything in a folder, including dotfiles."""
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

def reset():
    for folder in RESET_DIRS:
        for name in contents(folder):
            path = os.path.join(folder, name)
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)   # works on read-only archive files; deletion depends on the folder

if __name__ == "__main__":
    found = {os.path.basename(d): contents(d) for d in RESET_DIRS}
    total = sum(len(names) for names in found.values())
    if total == 0:
        print("Nothing to reset: in/, email_archive/ and tracking-data/ are already empty.")
        sys.exit(0)

    print("TESTING ONLY — this permanently deletes:")
    for folder, names in found.items():
        print(f"  {folder}/: {len(names)} item(s)")
    if "--yes" not in sys.argv:
        # A fresh code each time, so confirming takes a deliberate effort
        code = str(random.randint(1000, 9999))
        if input(f"To confirm, type this code: {code}\n> ").strip() != code:
            print("Code did not match. Cancelled; nothing was deleted.")
            sys.exit(1)

    reset()
    print(f"Reset done: deleted {total} item(s). Folders are kept, now empty.")
