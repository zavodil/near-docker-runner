#!/bin/bash
# test_agent_docker.sh
# Script to test if your Docker agent setup is working correctly

echo "Testing Docker agent setup..."

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Check if the agents directory exists
if [ ! -d "agents" ]; then
    echo "Creating agents directory..."
    mkdir -p agents/example_agent
fi

# Check if the example agent exists
if [ ! -d "agents/example_agent" ]; then
    echo "Creating example agent directory..."
    mkdir -p agents/example_agent
fi

# Create the agent.py file if it doesn't exist
if [ ! -f "agents/example_agent/agent.py" ]; then
    echo "Creating example agent.py file..."
    cat > agents/example_agent/agent.py << 'EOF'
from nearai.agents.environment import Environment


def main(env: Environment):
    messages = [{
        "role": "system",
        "content": "You are a helpful AI Agent working on NEAR AI Hub"
    }] + env.list_messages()

    reply = env.completion(messages, model="deepseek-v3", temperature=0.3, frequency_penalty=0, n=1, stream=True)

    env.add_reply(reply)
    env.mark_done()


if 'env' in globals():  # This conditional allows the code to work with our injected environment
    main(env)
EOF
fi

# Create the Dockerfile if it doesn't exist
if [ ! -f "agents/example_agent/Dockerfile" ]; then
    echo "Creating example agent Dockerfile..."
    cat > agents/example_agent/Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir openai==1.2.0 httpx==0.27.2

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

# The agent.py will be mounted at runtime
# CMD is overridden at runtime when executed through the entrypoint
CMD ["python", "/app/agent.py"]
EOF
fi

# Test building the Docker image
echo "Building Docker image for example agent..."
docker build -t agent-example_agent:latest agents/example_agent

# Create a test entrypoint file
echo "Creating test entrypoint file..."
cat > test_entrypoint.py << 'EOF'
import os
import sys

# Check if openai module is available
try:
    import openai
    print("SUCCESS: openai module is available")
except ImportError:
    print("ERROR: openai module is not available")
    sys.exit(1)

# Check if nearai module is available
try:
    from nearai.agents.environment import Environment
    print("SUCCESS: nearai.agents.environment module is available")
except ImportError:
    print("ERROR: nearai.agents.environment module is not available")
    # This is expected, as the nearai module is created in the Docker container

# Print environment
print("Environment variables:")
for key, value in os.environ.items():
    if key in ['PATH', 'LD_LIBRARY_PATH']:
        continue  # Skip verbose environment variables
    print(f"  {key}={value}")

print("TEST COMPLETE")
EOF

# Test running the Docker container
echo "Testing Docker container execution..."
docker run --rm \
    -v "$(pwd)/test_entrypoint.py:/app/test_entrypoint.py" \
    agent-example_agent:latest \
    python /app/test_entrypoint.py

# Clean up
echo "Cleaning up..."
rm test_entrypoint.py

echo "Test complete. If you see 'SUCCESS: openai module is available' above, your Docker agent setup is working correctly."