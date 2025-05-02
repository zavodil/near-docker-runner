from nearai.agents.environment import Environment


def main(env: Environment):
    messages = [{
        "role": "system",
        "content": "You are a helpful AI Agent working on NEAR AI Hub"
    }] + env.list_messages()

    env.add_reply("Test")

    env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct", temperature=0.3, frequency_penalty=0, n=1, stream=True)

    env.mark_done()


if 'env' in globals():  # This conditional allows the code to work with our injected environment
    main(env)
