import os

# ── Folder layout for one end-to-end run ──────────────────────────
#   mock_emails/    read-only source emails (golden test data)
#   in/             staging area: exactly one email at the start of a run
#   email_archive/  write-once archive + append-only index
#   tracking-data/  the tracker spreadsheet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MOCK_EMAIL_DIR = os.path.join(BASE_DIR, "mock_emails")
IN_DIR = os.path.join(BASE_DIR, "in")
ARCHIVE_DIR = os.path.join(BASE_DIR, "email_archive")
ARCHIVE_INDEX = os.path.join(ARCHIVE_DIR, "archive_index.jsonl")
TRACKING_DIR = os.path.join(BASE_DIR, "tracking-data")
SPREADSHEET = os.path.join(TRACKING_DIR, "spreadsheet.md")

def list_files(folder):
    """Visible files in a folder (skips .DS_Store and other dotfiles)."""
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder)
                  if not f.startswith(".") and os.path.isfile(os.path.join(folder, f)))
