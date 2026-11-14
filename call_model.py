def call_model(api_client, api_system_prompt, api_user_prompt, api_model, agent_tools):
    response = api_client.messages.create(
        model=api_model,
        max_tokens=1000,
        system=api_system_prompt,
        tools=agent_tools,
        messages=api_user_prompt
    )
    return response