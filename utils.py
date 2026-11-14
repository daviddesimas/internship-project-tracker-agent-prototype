import os
import time

# Debug tracing is off unless TRACKER_TRACE is set (to anything but "" or "0").
#   ./run.sh api        → summary only
#   ./run.sh api-debug  → full [TRACE] output (TRACKER_TRACE=1)
TRACE_ON = os.environ.get("TRACKER_TRACE", "") not in ("", "0")

def trace(label, data=None):
    """Simple tracer — shows flow with timing. Prints only when TRACE_ON."""
    if not TRACE_ON:
        return
    timestamp = time.strftime("%H:%M:%S")
    print(f"\n[TRACE {timestamp}] {label}")
    if data is not None:
        print(f"           {data}")
