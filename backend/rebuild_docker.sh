#!/bin/bash
# Script to rebuild and clean up agent Docker containers and images

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Rebuilding all agent Docker containers${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    exit 1
fi

# Stop and remove all running agent containers
echo -e "${YELLOW}Stopping and removing all running agent containers...${NC}"
docker ps -a | grep "agent-" | awk '{print $1}' | xargs -r docker rm -f

# Remove agent images
echo -e "${YELLOW}Removing agent images...${NC}"
docker images | grep "agent-" | awk '{print $1":"$2}' | xargs -r docker rmi -f

# Check if agents directory exists
if [ ! -d "agents" ]; then
    echo -e "${RED}Error: The 'agents' directory does not exist${NC}"
    echo "Create the agents directory and agents first"
    exit 1
fi

# Find all agent directories
AGENT_DIRS=$(find agents -type d -depth 1)

if [ -z "$AGENT_DIRS" ]; then
    echo -e "${YELLOW}No agent directories found${NC}"
    exit 0
fi

# Iterate over each agent directory
for AGENT_DIR in $AGENT_DIRS; do
    AGENT_NAME=$(basename "$AGENT_DIR")

    echo -e "${YELLOW}Processing agent: ${AGENT_NAME}${NC}"

    # Check if a Dockerfile exists
    if [ ! -f "${AGENT_DIR}/Dockerfile" ]; then
        echo -e "${YELLOW}  - No Dockerfile found, skipping${NC}"
        continue
    fi

    # Build the new image
    echo -e "${YELLOW}  - Building new image: agent-${AGENT_NAME}:latest${NC}"
    if docker build -t agent-${AGENT_NAME}:latest "${AGENT_DIR}"; then
        echo -e "${GREEN}  - Image built successfully${NC}"
    else
        echo -e "${RED}  - Error building image${NC}"
    fi
done

echo -e "${GREEN}Process completed${NC}"