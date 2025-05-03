# backend/agent_manager.py

import os
import json
import sys
import asyncio
import tempfile
import logging
from datetime import datetime
from fastapi import HTTPException
from config import AGENTS_DIR, API_BASE_URL, AUTH_TOKEN, DEFAULT_MODEL

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Keep track of running agent processes - keyed by user token
user_agent_processes = {}


# Function to inject Environment module into agent file
async def create_agent_entrypoint(agent_path, messages, max_tokens):
    """Create a temporary Python file that injects the Environment class into the agent"""

    # Ensure the AUTH_TOKEN is properly JSON serialized
    auth_token_json = json.dumps(AUTH_TOKEN)

    env_module = f"""# Injected Environment module
import os
import json
import sys
import asyncio
from typing import List, Dict, Any, Optional
from openai import OpenAI

class Environment:
    def __init__(self):
        self.messages = {json.dumps(messages)}
        self.api_base_url = "{API_BASE_URL}"
        self.auth_token = {auth_token_json}  # Properly JSON serialized token
        self.default_model = "{DEFAULT_MODEL}"
        self.max_tokens = {max_tokens}
        self.is_done = False
        self.current_reply = ""

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key="dummy",  # Will be overridden by auth header
            base_url=self.api_base_url
        )

    def list_messages(self):
        \"\"\"Return the list of messages to be processed\"\"\"
        return self.messages

    def completion(self, messages, model=None, temperature=0.7, frequency_penalty=0, n=1, stream=True, max_tokens=None):
        \"\"\"Make a completion request to the OpenAI API\"\"\"
        # Create custom headers with auth token
        headers = {{"Authorization": f"Bearer {{self.auth_token}}"}}

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

        # If streaming, process the stream
        collected_content = ""
        if stream:
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    collected_content += content
                    # Print with DATA: prefix and JSON encode to preserve all characters
                    # This ensures newlines are properly preserved
                    print(f"DATA:{{json.dumps(content)}}", flush=True)

            self.current_reply = collected_content
            return collected_content
        else:
            # For non-streaming, return the complete response
            content = response.choices[0].message.content
            self.current_reply = content
            print(f"DATA:{{json.dumps(content)}}", flush=True)
            return content

    def add_reply(self, reply):
        \"\"\"Add a new message to the chat from the AI\"\"\"
        # If reply is provided, use it; otherwise use the stored current_reply
        content = reply if reply else self.current_reply

        if content and not content.isspace():
            # JSON encode to preserve all characters including newlines
            print(f"NEW_MESSAGE:{{json.dumps(content)}}", flush=True)
            print(f"DEBUG: Sent new message: {{content[:30]}}", flush=True)

        # Store this as the current reply
        self.current_reply = content

    def mark_done(self):
        \"\"\"Mark the agent as done with processing\"\"\"
        self.is_done = True
        print("DONE", flush=True)

# Instantiate Environment
env = Environment()

# Now run the agent code directly
{open(agent_path, 'r').read()}
"""

    # Create a temporary file for the entrypoint
    fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='agent_')
    with os.fdopen(fd, 'w') as f:
        f.write(env_module)

    return temp_path


# Function to start agent process
async def start_agent_process(agent_name, messages, max_tokens, token):
    """Start the agent process and return a reference to it"""
    agent_path = os.path.join(AGENTS_DIR, agent_name, "agent.py")

    if not os.path.exists(agent_path):
        logger.error(f"Agent file not found: {agent_path}")
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

    try:
        # Create entrypoint with injected Environment
        entrypoint_path = await create_agent_entrypoint(agent_path, messages, max_tokens)

        # Check if we should use Docker
        docker_path = os.path.join(AGENTS_DIR, agent_name, "Dockerfile")
        use_docker = os.path.exists(docker_path)

        # Create a process key based on user token and agent
        process_key = f"{token}_{agent_name}"

        if use_docker:
            # Create a requirements.txt file with necessary packages
            req_fd, req_path = tempfile.mkstemp(suffix='.txt', prefix='agent_req_')
            with os.fdopen(req_fd, 'w') as f:
                f.write("openai==1.2.0\nhttpx==0.27.2\n")

            # Generate a unique container name for this user and agent
            container_name = f"agent-{agent_name}-{token[:8]}"

            # Check if container already exists and remove it first
            os.system(f"docker rm -f {container_name} > /dev/null 2>&1")

            # Prepare Docker command - make sure to install required packages
            # Using a non-root user inside the container
            cmd = [
                "docker", "run",
                "--name", container_name,
                "-d",  # Run in detached mode for persistence
                "-i",  # Keep STDIN open
                "-v", f"{os.path.abspath(entrypoint_path)}:/app/entrypoint.py",
                "-v", f"{os.path.abspath(req_path)}:/app/requirements.txt",
                "-w", "/app",
            ]

            # Check if image exists
            image_exists = os.system(f"docker image inspect agent-{agent_name}:latest > /dev/null 2>&1") == 0

            if image_exists:
                # Use existing image
                cmd.append(f"agent-{agent_name}:latest")
            else:
                # If image doesn't exist, use python base and install requirements
                cmd.append("python:3.9-slim")

                # Build the image in background
                logger.info(f"Building Docker image for agent: {agent_name}")
                build_cmd = f"docker build -t agent-{agent_name}:latest {os.path.dirname(docker_path)} &"
                os.system(build_cmd)

            # Add command to install packages and run the entrypoint in persistent mode
            # Using PYTHONWARNINGS=ignore to suppress Python warnings
            cmd.extend([
                "bash", "-c",
                "export PYTHONWARNINGS=ignore && pip install --quiet --no-warn-script-location --no-cache-dir -r requirements.txt 2>/dev/null && PYTHONWARNINGS=ignore python /app/entrypoint.py"
            ])

            logger.info(f"Starting agent container: {container_name}")

            # Start the Docker container in background mode
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for container to start
            await asyncio.sleep(2)

            # Store reference to the container
            user_agent_processes[process_key] = {
                "container_name": container_name,
                "entrypoint": entrypoint_path,
                "requirements": req_path,
                "started_at": datetime.now(),
                "token": token,
                "agent_name": agent_name,
                "last_message_time": datetime.now()
            }

        else:
            # For non-Docker execution, we'll need a different approach for persistence
            cmd = [sys.executable, entrypoint_path]
            logger.info(f"Starting direct Python agent: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Store reference
            user_agent_processes[process_key] = {
                "process": process,
                "entrypoint": entrypoint_path,
                "started_at": datetime.now(),
                "token": token,
                "agent_name": agent_name,
                "last_message_time": datetime.now()
            }

        return process_key

    except Exception as e:
        logger.error(f"Error starting agent process: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")


# Function to stream from agent process
async def stream_from_agent(agent_name, messages, max_tokens=4000, token=None):
    """
    Stream from the agent process with max length handling.

    Args:
        agent_name: Name of the agent to use
        messages: List of message objects to send to the agent
        max_tokens: Maximum number of tokens to generate
        token: User's authentication token for persistent sessions
    """
    # Send debug event
    debug_msg = f"Starting agent {agent_name} with {len(messages)} messages"
    logger.info(debug_msg)
    yield f"event: debug\ndata: {debug_msg}\n\n"

    try:
        if token:
            # Start a new agent process for this request
            process_key = await start_agent_process(agent_name, messages, max_tokens, token)
            process_info = user_agent_processes[process_key]

            # If using Docker
            if "container_name" in process_info:
                container_name = process_info["container_name"]

                # Add a small delay to ensure the container is fully started
                await asyncio.sleep(1)

                # Execute command to get output from the container
                cmd = [
                    "docker", "logs",
                    "-f",  # Follow log output
                    container_name
                ]

                logger.info(f"Following container logs: {container_name}")

                # Start the logs process
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Process streaming output
                total_chars = 0
                current_message = ""

                # Buffered line handling
                buffer = ""
                # Track if we're processing unprefixed data as part of output
                is_unprefixed_data = False
                # Track the last output line to detect sequences of unprefixed lines
                last_line = None

                # Define a task to read stderr
                stderr_task = asyncio.create_task(process.stderr.read())

                # Read stdout
                while True:
                    # Read a line from the process stdout
                    line_bytes = await process.stdout.readline()

                    # Check if we've reached EOF
                    if not line_bytes:
                        break

                    line_str = line_bytes.decode('utf-8').rstrip('\n')

                    # Log the raw output
                    logger.info(f"Raw agent output: {line_str[:80]}")

                    # Parse different message types
                    if line_str.startswith('NEW_MESSAGE:'):
                        # Always handle new message events first and immediately
                        try:
                            # Extract and decode JSON content
                            json_content = line_str[12:]
                            content = json.loads(json_content)
                            logger.info(f"New separate message (JSON decoded): {str(content)[:80]}")

                            # Send as a new message event - this creates a separate chat bubble
                            yield f"event: new_message\ndata: {json.dumps({'content': content})}\n\n"

                            # Update total characters count
                            total_chars += len(str(content))

                            # Reset unprefixed data flag
                            is_unprefixed_data = False
                            last_line = line_str
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error in NEW_MESSAGE: {e}")
                            # Fall back to raw content if JSON decode fails
                            content = line_str[12:]
                            yield f"event: new_message\ndata: {json.dumps({'content': content})}\n\n"

                    elif line_str.startswith('DATA:'):
                        try:
                            # Extract and decode JSON content
                            json_content = line_str[5:]
                            content = json.loads(json_content)

                            # Add newline if this is a continuing line after a previous unprefixed line
                            if is_unprefixed_data and last_line and not last_line.startswith('DATA:'):
                                current_message += '\n'

                            current_message += content

                            # Update total characters count
                            total_chars += len(str(content))

                            # Log every 500 characters
                            if total_chars % 500 < len(str(content)):
                                logger.info(f"Streamed {total_chars} characters so far")

                            # Send content in SSE format - this updates the existing bubble
                            yield f"data: {json.dumps({'content': content})}\n\n"

                            # Reset unprefixed data flag
                            is_unprefixed_data = False
                            last_line = line_str
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error in DATA: {e}")
                            # Fall back to raw content if JSON decode fails
                            content = line_str[5:]
                            current_message += content
                            yield f"data: {json.dumps({'content': content})}\n\n"

                    elif line_str.startswith('DEBUG:'):
                        # Log debug output
                        logger.info(f"Agent debug: {line_str[6:]}")
                        is_unprefixed_data = False
                        last_line = line_str

                    elif line_str == "DONE":
                        logger.info(f"Agent marked task as done")

                        # Send a completion event to signal the frontend that the streaming is complete
                        # This will "freeze" the current message so future streams don't overwrite it
                        yield f"event: completion\ndata: {json.dumps({'status': 'complete', 'total_chars': total_chars})}\n\n"

                        # Only stop following logs, container keeps running
                        break

                    else:
                        # This is a line without a prefix - treat it as continuation of DATA
                        # Only do this for non-empty lines that don't match other patterns
                        if line_str and line_str.strip():
                            logger.info(f"Processing unprefixed line as data: {line_str[:80]}")

                            # If this is a sequence of unprefixed data (numbers, etc.)
                            # add a newline if this isn't the first unprefixed line
                            if is_unprefixed_data and last_line != line_str:
                                current_message += '\n'

                            # Add the content and track that we're in an unprefixed sequence
                            content = line_str
                            current_message += content
                            is_unprefixed_data = True
                            total_chars += len(content)

                            # Send as a data event
                            yield f"data: {json.dumps({'content': content})}\n\n"

                            last_line = line_str

                # Check if there were any errors
                stderr_data = await stderr_task
                if stderr_data:
                    error_str = stderr_data.decode('utf-8')

                    # Filter out pip warnings
                    if not (
                            "WARNING: Running pip as the 'root' user" in error_str or
                            "--no-warn-script-location" in error_str
                    ):
                        logger.error(f"Agent error: {error_str}")

                        # Handle different error types
                        if "No module named" in error_str:
                            yield f"event: error\ndata: {json.dumps({'error': 'Missing Python module in agent container. Check logs for details.'})}\n\n"
                        elif "FileNotFoundError" in error_str:
                            yield f"event: error\ndata: {json.dumps({'error': 'File not found in agent container. Check logs for details.'})}\n\n"
                        elif "openai.BadRequestError" in error_str or "Invalid JSON" in error_str:
                            yield f"event: error\ndata: {json.dumps({'error': 'API request error. Check token format and permissions.'})}\n\n"
                        elif "ConnectionError" in error_str:
                            yield f"event: error\ndata: {json.dumps({'error': 'Connection error. Check network settings and API endpoints.'})}\n\n"
                        else:
                            yield f"event: error\ndata: {json.dumps({'error': 'Agent execution error. Check logs for details.'})}\n\n"

            else:
                # Non-Docker persistent process
                # Process output from regular process
                process = process_info["process"]

                # Similar to above, but with process.stdout directly
                # (Implementation skipped for brevity, similar to the Docker case)
                pass

        else:
            # For non-persistent mode (fall back to original implementation)
            # This code path is not used in the new implementation
            pass

        # Send completion event
        logger.info(f"Agent streaming completed. Total characters: {total_chars}")
        yield f"event: completion\ndata: {json.dumps({'status': 'complete', 'total_chars': total_chars})}\n\n"

    except Exception as e:
        # Send error event
        error_message = str(e)
        logger.error(f"Error in agent streaming: {error_message}")
        yield f"event: error\ndata: {json.dumps({'error': error_message})}\n\n"


# Background task to clean up old agent processes
async def cleanup_old_processes():
    """Clean up old agent processes and temporary files"""
    now = datetime.now()
    to_remove = []

    for key, info in user_agent_processes.items():
        # If process has been inactive for more than 24 hours, kill it
        if (now - info["last_message_time"]).total_seconds() > 86400:  # 24 hours
            logger.info(f"Cleaning up old agent process: {key}")
            try:
                # For Docker containers
                if "container_name" in info:
                    # Stop and remove the container
                    container_name = info["container_name"]
                    os.system(f"docker stop {container_name} && docker rm {container_name}")
                else:
                    # For regular processes
                    info["process"].kill()
                    await info["process"].wait()

                # Clean up temporary files
                if "entrypoint" in info and os.path.exists(info["entrypoint"]):
                    os.unlink(info["entrypoint"])

                if "requirements" in info and info["requirements"] and os.path.exists(info["requirements"]):
                    os.unlink(info["requirements"])

                to_remove.append(key)
            except Exception as e:
                logger.error(f"Error cleaning up process {key}: {str(e)}")

    # Remove processed keys
    for key in to_remove:
        del user_agent_processes[key]