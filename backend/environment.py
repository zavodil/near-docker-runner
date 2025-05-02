# backend/environment.py

import asyncio
import logging
from openai import OpenAI
from config import API_BASE_URL, AUTH_TOKEN, DEFAULT_MODEL

logger = logging.getLogger(__name__)


# Environment class to be injected into agent.py
class Environment:
    def __init__(self, messages=None, api_base_url=None, auth_token=None, default_model=None, max_tokens=4000):
        self.messages = messages or []
        self.api_base_url = api_base_url or API_BASE_URL
        self.auth_token = auth_token or AUTH_TOKEN
        self.default_model = default_model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.is_done = False
        self.current_reply = ""

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key="dummy",  # Will be overridden by auth header
            base_url=self.api_base_url
        )

    def list_messages(self):
        """Return the list of messages to be processed"""
        return self.messages

    def completion(self, messages, model=None, temperature=0.7, frequency_penalty=0, n=1, stream=True, max_tokens=None):
        """Make a completion request to the OpenAI API"""
        logger.info(f"Agent requesting completion with model: {model or self.default_model}")

        # Create custom headers with auth token
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        response = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            frequency_penalty=frequency_penalty,
            n=n,
            stream=stream,
            max_tokens=max_tokens or self.max_tokens,
            extra_headers=headers
        )

        # If streaming, process the stream and print tokens as they come
        collected_content = ""
        if stream:
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    collected_content += content
                    # Print content for streaming back to client
                    print(f"DATA:{content}", flush=True)
                    # Small delay to avoid overwhelming the pipe
                    asyncio.sleep(0.01)

            self.current_reply = collected_content
            return collected_content
        else:
            # For non-streaming, return the complete response
            content = response.choices[0].message.content
            self.current_reply = content
            print(f"DATA:{content}", flush=True)
            return content

    def add_reply(self, reply):
        """Store the reply (used by the agent)"""
        # If reply is provided, use it; otherwise use the stored current_reply
        content = reply if reply else self.current_reply

        # Print the message with the DATA prefix for streaming back to client
        if content and not content.isspace():
            # Only print if we haven't already printed in completion()
            if not self.current_reply or content != self.current_reply:
                print(f"DATA:{content}", flush=True)

        # Store this as the current reply
        self.current_reply = content

    def mark_done(self):
        """Mark the agent as done with processing"""
        self.is_done = True
        print("DONE", flush=True)