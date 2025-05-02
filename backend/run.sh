#!/bin/bash
# run.sh - Script to set up and run the backend

# Make sure the script stops on errors
set -e

# Display colored output for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up AI Agent Backend${NC}"

# Step 1: Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    echo "Please install Docker and try again."
    exit 1
fi

# Step 2: Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running${NC}"
    echo "Please start the Docker daemon and try again."
    exit 1
fi

# Step 3: Create the agents directory structure if it doesn't exist
if [ ! -d "agents/example_agent" ]; then
    echo -e "${YELLOW}Creating agents directory structure...${NC}"
    mkdir -p agents/example_agent
fi

# Step 4: Create or update the agent.py file
echo -e "${YELLOW}Setting up example agent...${NC}"
cat > agents/example_agent/agent.py << 'EOF'
from nearai.agents.environment import Environment


def main(env: Environment):
    messages = [{
        "role": "system",
        "content": "You are a helpful AI Agent working on NEAR AI Hub"
    }] + env.list_messages()

    reply = env.completion(messages, model="fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct", temperature=0.3, frequency_penalty=0, n=1, stream=True)

    env.add_reply(reply)
    env.mark_done()


if 'env' in globals():  # This conditional allows the code to work with our injected environment
    main(env)
EOF

# Step 5: Create or update the Dockerfile
echo -e "${YELLOW}Setting up agent Dockerfile...${NC}"
cat > agents/example_agent/Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# Install dependencies - we pre-install these to speed up agent startup
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

# The entrypoint.py will be mounted at runtime
CMD ["python", "/app/entrypoint.py"]
EOF

# Step 6: Build the Docker image for the agent
echo -e "${YELLOW}Building Docker image for the agent...${NC}"
docker build -t agent-example_agent:latest agents/example_agent

# Step 7: Check if Python dependencies are installed
echo -e "${YELLOW}Checking Python dependencies...${NC}"
if ! pip freeze | grep -q "fastapi=="; then
    echo -e "${YELLOW}Installing required Python packages...${NC}"
    pip install fastapi==0.103.1 uvicorn==0.23.2 pydantic==2.3.0 openai==1.2.0 httpx==0.27.2 python-dotenv==1.0.0 python-multipart==0.0.6
fi

# Step 8: Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file with default values...${NC}"
    cat > .env << EOF
API_BASE_URL=https://api.near.ai/v1/
AUTH_TOKEN={"account_id":"zavodil.near","public_key":"ed25519:HFd5upW3ppKKqwmNNbm56JW7VHXzEoDpwFKuetXLuNSq","signature":"bUI7OI3xAdK5e40r3LT3Js9jY9uIff822EUCMbiYJyE62X0yEVjrwYdJFTyosNwfyisK44BT9TD75PH+ERiyCQ==","callback_url":"http://localhost:54737/capture","message":"Welcome to NEAR AI","recipient":"ai.near","nonce":"1738426448240"}
DEFAULT_MODEL=fireworks::accounts/fireworks/models/llama-v3p3-70b-instruct
PORT=5001
EOF
fi

# Step 9: Start the backend
echo -e "${GREEN}Starting the AI Agent Backend...${NC}"
echo -e "${GREEN}The backend will be available at http://localhost:5001${NC}"
python app.py