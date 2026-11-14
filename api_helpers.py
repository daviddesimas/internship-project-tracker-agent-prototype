import os

PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")  # defaults to "anthropic" if unset

def get_client():
    if PROVIDER == "anthropic":
        from anthropic import Anthropic
        return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    elif PROVIDER == "bedrock":
        from anthropic import AnthropicBedrock
        return AnthropicBedrock()
    elif PROVIDER == "vertex":
        from anthropic import AnthropicVertex
        return AnthropicVertex()
    else:
        raise ValueError(f"Unknown provider: {PROVIDER}")

def validate_model(client, model_id):
    available = {m.id for m in client.models.list().data}
    if model_id not in available:
        raise RuntimeError(
            f"Model '{model_id}' not available to this account. "
            f"Available: {sorted(available)}"
        )

def package_messages(user_message):
    """Wrap a message string into the Messages API's expected list format."""
    return [{"role": "user", "content": user_message}]