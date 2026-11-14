import os
import sys

# ── Choose the model for each tracker (run.sh menu 6) ─────────────
# Usage: ./run.sh models      (or python3 choose_models.py)
# Saves your choices in .models (git-ignored, one line per tracker):
#   api=claude-sonnet-5-5     used by Tracker (API) as TRACKER_API_MODEL
#   cc=sonnet                 used by Tracker (Claude Code) as: claude --model sonnet
# A tracker with no line uses the project default from default_models (committed).
# The environment variables TRACKER_API_MODEL and TRACKER_CC_MODEL override both
# files for one run.

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_FILE = os.path.join(HERE, ".models")
DEFAULTS_FILE = os.path.join(HERE, "default_models")

# Claude Code accepts these aliases (claude --help), or a model's full name.
CC_ALIASES = ["sonnet", "opus", "fable"]

def read_settings(path=MODELS_FILE):
    settings = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and value.strip():
                    settings[key.strip()] = value.strip()
    return settings

def write_settings(settings):
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        for key in ("api", "cc"):
            if key in settings:
                f.write(f"{key}={settings[key]}\n")

def api_models():
    """Model IDs your API key can use, newest first, or None if they can't be listed."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        return [m.id for m in anthropic.Anthropic().models.list(limit=100)]
    except Exception as e:
        print(f"  (could not list API models: {type(e).__name__}: {e})")
        return None

def pick(title, options, current, default_label):
    """Show a numbered list; return the new value, "" for the default, or None to keep."""
    print(f"\n{title}")
    print(f"  Current: {current or default_label}")
    print(f"   0) {default_label}")
    for i, option in enumerate(options, 1):
        mark = "  <- current" if option == current else ""
        print(f"  {i:>2}) {option}{mark}")
    answer = input("  Number, or type a model name; Enter keeps the current: ").strip()
    if not answer:
        return None
    if answer == "0":
        return ""
    if answer.isdigit() and 0 < int(answer) <= len(options):
        return options[int(answer) - 1]
    if answer.isdigit():
        print("  No such number; keeping the current model.")
        return None
    return answer

def main():
    settings = read_settings()
    defaults = read_settings(DEFAULTS_FILE)

    ids = api_models()
    if ids is None:
        print("API model list unavailable (no key, or the call failed): you can still type an ID.")
    choice = pick("Tracker (API) model", ids or [], settings.get("api"),
                  f"default ({defaults.get('api', 'MODEL in tracker.py')})")
    if choice is not None:
        settings.pop("api", None)
        if choice:
            settings["api"] = choice

    choice = pick("Tracker (Claude Code) model", CC_ALIASES, settings.get("cc"),
                  f"default ({defaults.get('cc', 'your /model setting')})")
    if choice is not None:
        settings.pop("cc", None)
        if choice:
            settings["cc"] = choice

    write_settings(settings)
    print("\nSaved." if settings else "\nBoth trackers use their defaults.")
    for key, label in (("api", "Tracker (API)"), ("cc", "Tracker (Claude Code)")):
        if key in settings:
            print(f"  {label}: {settings[key]}")
        else:
            print(f"  {label}: {defaults.get(key, 'default')} (default)")

if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; nothing changed.")
        sys.exit(1)
