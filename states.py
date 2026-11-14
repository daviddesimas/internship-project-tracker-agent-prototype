# ── Record states: a small state machine for the business analysts ─
# Each record is in exactly one state. Records are never deleted;
# Closed is the end state, and new-work views leave Closed records out.
#
# Typical path:
#   Registered -> Under Review -> Reviewed -> Active -> Verified -> Deployed
STATES = ["Registered", "Under Review", "Reviewed", "Active",
          "Verified", "Deployed", "Deferred", "Closed", "Rejected"]

INITIAL_STATE = "Registered"   # set when an ingested email is registered

# Forward moves from each state. Any open record can be Closed.
FORWARD = {
    "Registered":   ["Under Review", "Closed"],
    "Under Review": ["Reviewed", "Closed"],
    "Reviewed":     ["Active", "Deferred", "Rejected", "Closed"],
    "Active":       ["Verified", "Closed"],       # Active = assigned to a developer
    "Verified":     ["Deployed", "Closed"],       # complete and ready to ship
    "Deployed":     ["Closed"],                   # in production
    "Deferred":     ["Active", "Closed"],         # backlog; may be activated later
    "Rejected":     ["Closed"],
    "Closed":       [],                           # final: never reopens
}

# Backward moves: any open record may go back to an earlier state on the
# typical path (e.g. Verified -> Active when a check fails). Deferred and
# Rejected branch off Reviewed, so they can go back to Reviewed or earlier.
# Keeping these moves sensible is up to the spreadsheet admin.
PATH = ["Registered", "Under Review", "Reviewed", "Active", "Verified", "Deployed"]
_RANK = {state: i for i, state in enumerate(PATH)}
_RANK["Deferred"] = _RANK["Rejected"] = _RANK["Active"]

TRANSITIONS = {
    state: moves + [earlier for earlier in PATH if _RANK[earlier] < _RANK.get(state, -1)]
    for state, moves in FORWARD.items()
}

# TODO (planned): log every state change (who, when, from, to) for audit.
# The spreadsheet only holds the current state.

def can_transition(current, new):
    return new in TRANSITIONS.get(current, [])

def is_open(state):
    """True for records a new-work view should show."""
    return state != "Closed"
