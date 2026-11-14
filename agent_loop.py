import json
import time
import anthropic       # ← new import, needed for the exception classes
import utils
import call_model
import api_helpers

MAX_AGENT_ITERATIONS = 10

# ── The agentic loop ──────────────────────────────────────────────
def run_agent_loop(api_client, api_model, api_system_prompt, tool_dispatcher, agent_tools, prompt, student_name):
    """
    Runs the full tool-use loop:
    1. Send message to Claude
    2. If Claude wants to call a tool, run it  
    3. Send tool result back to Claude
    4. Repeat until Claude gives a final text response
    """

    # The messages list is our locally maintained conversation history.
    # We append user messages, Claude assistant messages, and tool-result messages to it.
    # On every client.messages.create() call, we send the full history so Claude has context.

    # The Messages API is stateless: the client must provide the conversation history again on each request.

    # The API call is stateless, so we include the same system prompt on every request.
    # It remains outside `messages`; the `messages` list holds the user/assistant conversation history.

    # -------------------------------------------------------------------------------------------------------

    # only once outside the loop:
    # messages = [{"role": "user", "content": user_message}]

    # this appends for each iteration in the loop:
    # messages.append({"role": "assistant", "content": response.content}).   <- Claude's requested tool call
    # messages.append({"role": "user", "content": tool_results})             <- Result of the tool call
    # -------------------------------------------------------------------------------------------------------

    # (1) Initial user message: "user", the implicit type is "text"
    # We could use an explicit packaging of the message with a "type": "text" field, but the API allows us to just use the
    # "user" role with a simple string for the content for messages that are not tool calls or tool results.


    # Locally maintained conversation history sent on every API call.
    prefixed_message = f"My name is {student_name}. {prompt}"
    api_user_prompt = api_helpers.package_messages(prefixed_message)

    iteration = 0
    while True:

        iteration += 1
        utils.trace(f"LOOP iteration {iteration} — sending {len(api_user_prompt)} messages to Claude")

        if iteration > MAX_AGENT_ITERATIONS:
            utils.trace("MAX AGENT ITERATIONS REACHED", f"limit={MAX_AGENT_ITERATIONS}")
            return "[Maximum agent iterations reached; the agent loop was stopped.]"

        # The Messages API is stateless, so every request includes the system prompt
        # and the complete locally maintained conversation history.

        # *** This is the API interface call to Claude. Study this carefully, the entire AI system hinges on this call ***
        try:

            response = call_model.call_model(api_client, api_system_prompt, api_user_prompt, api_model, agent_tools)

        except anthropic.RateLimitError as e:
            utils.trace("RATE LIMIT", str(e))
            return "[The Claude API rate limit was reached. Please wait a moment and try again.]"
        except anthropic.OverloadedError as e:
            utils.trace("OVERLOADED", str(e))
            return ("[The Claude API servers are currently overloaded and could not service "
                    "this request. Please wait and try again. Check status.claude.com for "
                    "current service status.]")
        except anthropic.APIConnectionError as e:
            utils.trace("CONNECTION ERROR", str(e))
            return "[Could not reach the Claude API — check your network connection and try again.]"
        except anthropic.APIStatusError as e:
            utils.trace("API ERROR", f"status_code={e.status_code}")
            return f"[The Claude API returned an error (status {e.status_code}). Please try again shortly.]"

        utils.trace(f"CLAUDE RESPONSE", f"stop_reason={response.stop_reason}, "
              f"blocks={len(response.content)}, "
              f"tokens_used={response.usage.input_tokens}in/{response.usage.output_tokens}out")

        # Claude finished with a text response — we're done
        if response.stop_reason == "end_turn":

            # Claude completed its turn — collect all text blocks and return one response string.
            text_parts = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                    utils.trace("Found text block during end_turn processing", f"{len(block.text)} characters")

            final_text = "".join(text_parts)

            if not final_text:
                utils.trace("WARNING — end_turn returned no text blocks")

            return final_text

        # Handle known non-tool stop reasons before entering the tool-use branch.
        # A tool-use response can contain one or more tool_use blocks.

        if response.stop_reason == "max_tokens":
            utils.trace("MAX TOKENS — response was truncated")
            text_parts = [block.text for block in response.content if block.type == "text"]
            partial_text = "".join(text_parts)
            if partial_text:
                return partial_text + "\n\n[Note: response was cut off — reached the token limit.]"
            return "[Claude reached the response token limit before generating any text.]"

        if response.stop_reason == "refusal":
            utils.trace("REFUSAL — Claude declined the request")
            return "[Claude declined to answer this request.]"

        if response.stop_reason == "stop_sequence":
            utils.trace("STOP SEQUENCE — generation stopped on a configured sequence")
            return "[Claude stopped on a configured stop sequence.]"

        if response.stop_reason == "tool_use":

            # First, preserve the request in the conversation history
            # Add Claude's response (with tool call) to the history
            # This records something like: “Claude requested get_student_progress with these arguments”

            # (2) Append Claude's assistant-side response, including its tool_use block(s).

            api_user_prompt.append({"role": "assistant", "content": response.content})
            utils.trace("TOOL USE — Claude wants to call a function")

            # Process each tool call
            # We process all tool calls in the response, and only the tool calls (block.type == "tool_use")
            # For each tool call, we execute the call to the named tool, append (accumulate)
            # the result from each tool call in the local array tool_results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":

                    utils.trace(f"DISPATCHING TOOL", f"name={block.name}, input={block.input}")
                    t_start = time.time()

                    # The local tool returns a Python dictionary.
                    # We later serialize it with json.dumps() for the tool_result content.
                    result = tool_dispatcher(block.name, block.input, student_name)

                    t_end = time.time()
                    utils.trace(f"TOOL RETURNED", f"in {(t_end-t_start)*1000:.1f}ms — {result}")

                    # This line converts the locally returned value into the Claude API’s expected tool-result format
                    # by wrapping the raw tool result in a JSON object with the tool_use_id and type,
                    # so that Claude can match the result to the tool call

                    # (3) Create a tool_result content block that resolves one prior tool_use request.

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # At this point, since we are in the response.stop_reason == "tool_use", we have at least one tool call
            # and we processed every tool call requested by Claude that was returned in the response.content.
            # We now have the array of results from N >= 1 tool calls stored in the local tool_results.

            # The key field in the tool_use_id in the tool_results (see the tool_results.append above)
            # is the same as the tool_use_id in the original tool call request from Claude (passed in as block.id).
            # This is a critical part of the packaging, this is how Claude matches the result to the tool call.

            # Now, we append the array of all tool results to the messages, which
            # sends this back in the conversation history.

            # (4) Add application-generated tool results as a user-side message for Claude

            api_user_prompt.append({"role": "user", "content": tool_results})
            utils.trace(f"SENDING TOOL RESULTS BACK — history now {len(api_user_prompt)} messages")

            # go back to the top of the while loop, send the updated messages to Claude,
            # and repeat until Claude returns a final text response
            continue

        # If we get here, we have an unhandled stop_reason
        utils.trace("UNHANDLED STOP REASON", response.stop_reason)
        return f"[Agent stopped unexpectedly: {response.stop_reason}]"


