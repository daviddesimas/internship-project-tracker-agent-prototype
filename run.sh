#!/bin/bash
# ── Development menu: pick reset, prepare or a tracker by number ──
# Usage: ./run.sh                    — show the menu (repeats until you quit)
#        ./run.sh prepare jane_01.txt — run one action directly, with its arguments
#        ./run.sh api                — Tracker (API):         python3 tracker.py, summary only
#        ./run.sh api-debug          — Tracker (API) with full [TRACE] debug output
#        ./run.sh cc                 — Tracker (Claude Code): claude -p /track
#        ./run.sh models             — choose the model for each tracker
#
# The two trackers are separate code that share the same data folders
# (in/, email_archive/, tracking-data/), so either one can process the next email.

cd "$(dirname "$0")" || exit 1

# Number of staged emails in in/ (same rule as paths.list_files: skips dotfiles)
staged_count() {
    python3 -c "import paths; print(len(paths.list_files(paths.IN_DIR)))"
}

# ── Model choices, saved by choose_models.py in .models (api=…, cc=…) ─
# From-scratch defaults are in default_models (committed). Order of precedence:
#   1. TRACKER_API_MODEL / TRACKER_CC_MODEL  (one run)
#   2. .models                               (your menu 6 choices, not committed)
#   3. default_models                        (project default)
model_setting() {   # model_setting api|cc [file]  → that file's model line (default .models)
    sed -n "s/^$1=//p" "${2:-.models}" 2>/dev/null | head -1
}
effective_model() {   # effective_model api|cc  → the model that tracker will use
    local override m
    if [ "$1" = api ]; then override="${TRACKER_API_MODEL:-}"; else override="${TRACKER_CC_MODEL:-}"; fi
    m="${override:-$(model_setting "$1")}"
    printf '%s' "${m:-$(model_setting "$1" default_models)}"
}

# ── Tracker (API): your own agent loop calling the Claude API ─────
# Billed to the Claude Console (API) account. The key comes from, in order:
#   1. ANTHROPIC_API_KEY, if exported in this shell
#   2. the macOS Keychain entry "anthropic-api-key", stored once with:
#        security add-generic-password -a "$USER" -s anthropic-api-key -w
# The Keychain key is passed to tracker.py only, never exported to your shell,
# so Claude Code sessions you start yourself stay on your claude.ai plan.
# (Not needed with AI_PROVIDER=bedrock or vertex.)
# First argument: 0 = summary only, 1 = full [TRACE] debug output (TRACKER_TRACE).
api_key() {   # the API key, from the environment or the Keychain (may be empty)
    local key="${ANTHROPIC_API_KEY:-}"
    [ -z "$key" ] && key="$(security find-generic-password -s anthropic-api-key -w 2>/dev/null)"
    printf '%s' "$key"
}

run_tracker_api() {
    local trace="$1"; shift
    local key="${ANTHROPIC_API_KEY:-}"
    if [ -z "$key" ] && [ "${AI_PROVIDER:-anthropic}" = "anthropic" ]; then
        key="$(api_key)"
        if [ -z "$key" ]; then
            echo "No API key: export ANTHROPIC_API_KEY, or store it in the Keychain with:"
            echo "  security add-generic-password -a \"\$USER\" -s anthropic-api-key -w"
            return 1
        fi
    fi
    local model; model="$(effective_model api)"
    TRACKER_API_MODEL="$model" TRACKER_TRACE="$trace" ANTHROPIC_API_KEY="$key" python3 tracker.py "$@"
}

# ── Tracker (Claude Code): /track with skills, on your Claude login ─
# ANTHROPIC_API_KEY is removed for this call only, so Claude Code always uses
# your claude.ai plan even if the key is exported for the API tracker.
# /track ends with finish_run.py, but that step is up to Claude. If an email is
# still in in/ afterwards, run finish_run.py here so the final check always happens.
# (If Claude already confirmed the run, in/ is empty and this is skipped.)
run_tracker_cc() {
    local model; model="$(effective_model cc)"
    local model_args=()
    [ -n "$model" ] && model_args=(--model "$model")
    # --output-format json lets cc_output.py show which model Claude Code actually used.
    # (The reply appears when the run finishes, not as it goes.)
    local out staged_name
    staged_name="$(python3 -c "import paths; print(', '.join(paths.list_files(paths.IN_DIR)))")"   # in/ is cleared during the run
    out="$(env -u ANTHROPIC_API_KEY claude -p "/track" --output-format json --settings .claude/track-settings.json "${model_args[@]}" "$@" < /dev/null)"
    local claude_status=$?
    printf '%s' "$out" | python3 cc_output.py "$staged_name"
    if [ "$(staged_count)" -gt 0 ]; then
        echo
        echo "run.sh: email still in in/ — running finish_run.py"
        python3 finish_run.py
        return $?
    fi
    return $claude_status
}

# Menu 6: pick a model for each tracker. Lists the API models your key can use.
choose_models() {
    ANTHROPIC_API_KEY="$(api_key)" python3 choose_models.py
}

# One line for the menu: which model each tracker will use
show_models() {
    echo "     now: API $(effective_model api) | Claude Code $(effective_model cc)"
}

run_action() {
    local action="$1"; shift
    case "$action" in
        reset|1)                 python3 reset.py "$@" ;;
        prepare|2)               python3 prepare.py "$@" ;;
        api|tracker-api|3)       run_tracker_api 0 "$@" ;;
        cc|tracker-cc|track|4)   run_tracker_cc "$@" ;;
        api-debug|tracker-api-debug|5) run_tracker_api 1 "$@" ;;
        models|6)                choose_models ;;
        *) echo "Unknown action: $action (use reset, prepare, api, cc, api-debug or models)"; return 1 ;;
    esac
}

# One action from the command line, then exit
if [ $# -gt 0 ]; then
    run_action "$@"
    exit $?
fi

while true; do
    echo
    echo "Email Tracker — dev actions"
    echo "  1) reset        empty in/, email_archive/, tracking-data/"
    echo "  2) prepare      stage one mock email in in/"
    echo "  3) tracker-api        process the staged email: Tracker (API), summary only"
    echo "  4) tracker-cc         process the staged email: Tracker (Claude Code), claude -p /track"
    echo "  5) tracker-api-debug  same as 3, with full [TRACE] debug output"
    echo "  6) models             choose the model for each tracker"
    show_models
    echo "  q) quit"
    read -r -p "Choose: " choice || break
    case "$choice" in
        q|Q|quit|"") break ;;
        *) echo; run_action "$choice" ;;
    esac
done
