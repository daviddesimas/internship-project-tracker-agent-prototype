import tool_ingest
import tool_register

# ── agent_tools: the list of tool definitions sent to Claude ──────
TOOLS = [
    tool_ingest.INGEST_EMAIL_TOOL,
    tool_register.REGISTER_PROJECT_TOOL,
]

# ── Tool dispatcher ───────────────────────────────────────────────
# agent_loop.py calls this with (tool_name, tool_input, student_name).
# student_name is unused here but kept so agent_loop.py stays unchanged.
# A tool that crashes returns an error to Claude instead of stopping the run;
# tracker.py then sees the run didn't finish and leaves in/ for review.
def tool_dispatcher(tool_name, tool_input, student_name):
    try:
        if tool_name == "ingest_email":
            return tool_ingest.ingest_email()
        elif tool_name == "register_project":
            return tool_register.register_project(tool_input["email_id"])
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": f"{tool_name} failed: {type(e).__name__}: {e}"}
