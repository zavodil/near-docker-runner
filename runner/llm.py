import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()


def llm_completion(messages: List[Dict[str, Any]]) -> str:
    """
    Placeholder function for LLM API call.
    Will be implemented by the user.
    """
    # This will be implemented by you
    import openai

    # Get API credentials from environment
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    default_model_name = os.getenv("DEFAULT_MODEL_NAME")

    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    # Initialize the client with optional base URL
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    print("client_kwargs", client_kwargs)
    print("default_model_name", default_model_name)

    client = openai.OpenAI(**client_kwargs)

    response = client.chat.completions.create(
        model=default_model_name,
        messages=messages,
        temperature=0.2,  # Low temperature for more deterministic responses
    )

    print("response", response)

    # Convert the response to a dictionary for easier handling
    return response.choices[0].message.content


# Mock LLM for testing purposes
class MockLLM:
    """Mock LLM class for testing without actual API calls."""

    def complete(self, messages: List[Dict[str, str]]) -> str:
        return llm_completion(messages)