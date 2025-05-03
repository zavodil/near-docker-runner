# agents/example_agent/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Pre-install the required packages globally to avoid reinstallation
RUN pip install --no-cache-dir openai==1.2.0 httpx==0.27.2 && \
    # Disable pip upgrade check to eliminate version warning
    pip config set global.disable-pip-version-check true

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONWARNINGS=ignore

# Create directory for the nearai module
RUN mkdir -p /app/nearai/agents

# Create a simple compatibility module for the environment
RUN echo 'from typing import List, Dict, Any\n\n\
class Environment:\n\
    def __init__(self):\n\
        pass\n\
    \n\
    def list_messages(self) -> List[Dict[str, str]]:\n\
        """Return the list of messages to be processed"""\n\
        pass\n\
    \n\
    def completion(self, messages, model=None, temperature=0.7, frequency_penalty=0, n=1, stream=True, max_tokens=None):\n\
        """Make a completion request to the API"""\n\
        pass\n\
    \n\
    def add_reply(self, reply):\n\
        """Store the reply"""\n\
        pass\n\
    \n\
    def mark_done(self):\n\
        """Mark the agent as done with processing"""\n\
        pass\n\
' > /app/nearai/agents/environment.py

# Create __init__.py files to make the modules importable
RUN touch /app/nearai/__init__.py
RUN touch /app/nearai/agents/__init__.py

# The entrypoint.py will be mounted at runtime
CMD ["python", "/app/entrypoint.py"]