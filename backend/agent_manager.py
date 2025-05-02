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
logger = logging.getLogger(__name__)

# Keep track of running agent processes
agent_processes = {}


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
                    # Print with DATA: prefix
                    print(f"DATA:{{content}}", flush=True)

            self.current_reply = collected_content
            return collected_content
        else:
            # For non-streaming, return the complete response
            content = response.choices[0].message.content
            self.current_reply = content
            print(f"DATA:{{content}}", flush=True)
            return content

    def add_reply(self, reply):
        \"\"\"Store the reply from the agent and send it to the client\"\"\"
        # If reply is provided, use it; otherwise use the stored current_reply
        content = reply if reply else self.current_reply

        # Print the message with the DATA prefix for streaming back to client
        if content and not content.isspace():
            # Only print if we haven't already printed in completion()
            if not self.current_reply or content != self.current_reply:
                print(f"DATA:{{content}}", flush=True)

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
async def start_agent_process(agent_name, messages, max_tokens):
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

        if use_docker:
            # Create a requirements.txt file with necessary packages
            req_fd, req_path = tempfile.mkstemp(suffix='.txt', prefix='agent_req_')
            with os.fdopen(req_fd, 'w') as f:
                f.write("openai==1.2.0\nhttpx==0.27.2\n")

            # Prepare Docker command - make sure to install required packages
            cmd = [
                "docker", "run", "--rm",
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

            # Add command to install packages and run the entrypoint
            cmd.extend([
                "bash", "-c",
                "pip install --quiet -r requirements.txt && python /app/entrypoint.py"
            ])

            logger.info(f"Starting Docker agent process: {' '.join(cmd)}")
        else:
            # Direct Python execution
            cmd = [sys.executable, entrypoint_path]
            logger.info(f"Starting direct agent process: {' '.join(cmd)}")

        # Start the process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Store reference to process with all temp files
        process_key = f"{agent_name}_{id(messages)}"
        agent_processes[process_key] = {
            "process": process,
            "entrypoint": entrypoint_path,
            "requirements": req_path if use_docker else None,
            "started_at": datetime.now()
        }

        return process_key

    except Exception as e:
        logger.error(f"Error starting agent process: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")


# Function to stream from agent process
async def stream_from_agent(agent_name, messages, max_tokens=4000):
    """
    Stream from the agent process with max length handling.

    Args:
        agent_name: Name of the agent to use
        messages: List of message objects to send to the agent
        max_tokens: Maximum number of tokens to generate
    """
    # Send debug event
    debug_msg = f"Starting agent {agent_name} with {len(messages)} messages"
    logger.info(debug_msg)
    yield f"event: debug\ndata: {debug_msg}\n\n"

    try:
        # Start agent process
        process_key = await start_agent_process(agent_name, messages, max_tokens)
        process_info = agent_processes[process_key]
        process = process_info["process"]

        # Process streaming output from agent
        total_chars = 0
        async for line in process.stdout:
            line_str = line.decode('utf-8').strip()

            # Simple protocol parsing
            if line_str.startswith('DATA:'):
                content = line_str[5:]

                # Update total characters count
                total_chars += len(content)

                # Log every 500 characters
                if total_chars % 500 < len(content):
                    logger.info(f"Streamed {total_chars} characters so far")

                # Send content in SSE format
                yield f"data: {json.dumps({'content': content})}\n\n"

            elif line_str == "DONE":
                logger.info(f"Agent marked task as done")

            # Small delay for client processing
            await asyncio.sleep(0.01)

        # Check stderr for any errors
        stderr_data = await process.stderr.read()
        if stderr_data:
            error_str = stderr_data.decode('utf-8')
            logger.error(f"Agent error: {error_str}")

            # Send error to client for certain types of errors
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

        # Wait for process to complete
        await process.wait()

        # Clean up temporary files
        if os.path.exists(process_info["entrypoint"]):
            os.unlink(process_info["entrypoint"])

        if process_info.get("requirements") and os.path.exists(process_info["requirements"]):
            os.unlink(process_info["requirements"])

        # Remove process from tracking
        del agent_processes[process_key]

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

    for key, info in agent_processes.items():
        # If process has been running for more than 30 minutes, kill it
        if (now - info["started_at"]).total_seconds() > 1800:  # 30 minutes
            logger.info(f"Killing old agent process: {key}")
            try:
                info["process"].kill()
                await info["process"].wait()

                # Clean up temporary files
                if os.path.exists(info["entrypoint"]):
                    os.unlink(info["entrypoint"])

                if info.get("requirements") and os.path.exists(info["requirements"]):
                    os.unlink(info["requirements"])

                to_remove.append(key)
            except Exception as e:
                logger.error(f"Error cleaning up process {key}: {str(e)}")

    # Remove processed keys
    for key in to_remove:
        del agent_processes[key]