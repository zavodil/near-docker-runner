# from nearai.agents.environment import Environment
#
#
# def main(env: Environment):
#     messages = [{
#         "role": "system",
#         "content": "You are a helpful AI Agent working on NEAR AI Hub"
#     }] + env.list_messages()
#
#     env.add_reply("Test")
#
#     env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct", temperature=0.3, frequency_penalty=0, n=1, stream=True)
#
#     env.mark_done()
#
#
# if 'env' in globals():  # This conditional allows the code to work with our injected environment
#     main(env)
import json

# agents/example_agent/agent.py

from nearai.agents.environment import Environment


def main(env: Environment):
    # Get user messages
    messages = [{
        "role": "system",
        "content": "You are a helpful AI Agent working on NEAR AI Hub"
    }] + env.list_messages()

    # Get the most recent user message
    user_message = None
    for msg in reversed(messages):
        if msg["role"] == "user":
            user_message = msg["content"]
            break

    # First response - this will be part of the initial streaming response

    env.add_reply("Processing your request...")

    env.add_reply(f"History: {json.dumps(messages)}")

    env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct",
                           temperature=0.3, frequency_penalty=0, n=1, stream=True)

    # # Optional: Add a second separate message based on the user question
    # if user_message and ("hello" in user_message.lower() or "hi" in user_message.lower()):
    #     env.add_reply("I'm happy to assist you today! Feel free to ask me any additional questions.")
    #
    # # Optional: Add a third separate message with some useful information
    # if "help" in user_message.lower():
    #     env.add_reply(
    #         "Here are some things I can help with:\n1. Answering questions\n2. Processing data\n3. Creative writing\n4. Code assistance")

    # Mark the interaction as complete
    env.mark_done()


if 'env' in globals():  # This conditional allows the code to work with our injected environment
    main(env)