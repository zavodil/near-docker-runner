# agents/example_agent/agent.py

from nearai.agents.environment import Environment
import json

def main(env: Environment):
    # Get user messages
    messages = [{
        "role": "system",
        "content": "You are a helpful AI Agent working on NEAR AI Hub"
    }] + env.list_messages()

    env.add_reply(f"Agent history: {json.dumps(messages)}")

    reply = env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct",
                          temperature=0.3, frequency_penalty=0, n=1, stream=True)

    env.mark_done()


main(env)