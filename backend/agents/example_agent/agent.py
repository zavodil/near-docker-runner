# agents/example_agent/agent.py

from nearai.agents.environment import Environment
import time  # Import time for delay
import json


def main(env: Environment):
    # Get user messages
    messages = [{
        "role": "system",
        "content": "You are a helpful AI Agent working on NEAR AI Hub"
    }] + env.list_messages()

    # First response - normal completion
    print("DEBUG: Starting completion...", flush=True)
    #reply = env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct",
    #                       temperature=0.3, frequency_penalty=0, n=1, stream=True)
    print("DEBUG: Completion finished.", flush=True)

    # Add a small delay to ensure messages are processed in order
    # time.sleep(1)

    # ALWAYS send a second message for testing
    print("DEBUG: Sending additional reply...", flush=True)

    env.add_reply("Processing your request...")

    env.add_reply(f"History: {json.dumps(messages)}")

    reply = env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct",
                          temperature=0.3, frequency_penalty=0, n=1, stream=True)

    # Add another small delay
    # time.sleep(1)

    # Debug info
    print("DEBUG: Messages processed successfully.", flush=True)

    # Mark the interaction as complete
    print("DEBUG: Marking done...", flush=True)
    env.mark_done()
    print("DEBUG: Agent completed.", flush=True)


if 'env' in globals():  # This conditional allows the code to work with our injected environment
    main(env)