# backend/app.py

import os
import json
import secrets
import asyncio
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check for required environment variables
required_env_vars = ['API_BASE_URL', 'AUTH_TOKEN', 'DEFAULT_MODEL']
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
    logger.error(error_msg)
    raise EnvironmentError(error_msg)

# Import the OpenAI client
from openai import OpenAI

# Get environment variables
API_BASE_URL = os.environ.get('API_BASE_URL')
AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL')

# Initialize OpenAI client
client = OpenAI(
    api_key="dummy",  # Will be overridden by auth header
    base_url=API_BASE_URL
)

# Create FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
TOKEN_EXPIRATION = 24  # hours

# In-memory token storage (for MVP only)
active_tokens = {}


# Models
class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]


# Middleware to handle exceptions
@app.middleware("http")
async def exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"}
        )


# Login endpoint
@app.post("/api/login")
async def login(request: LoginRequest):
    """Simple login to obtain an access token"""
    logger.info(f"Login attempt for user: {request.username}")

    # Simple authentication for MVP
    if request.username == 'user' and request.password == 'password':
        # Generate token
        token = secrets.token_hex(16)
        expiration = datetime.now() + timedelta(hours=TOKEN_EXPIRATION)

        # Store token
        active_tokens[token] = {
            'username': request.username,
            'expiration': expiration
        }

        logger.info(f"Login successful for user: {request.username}")
        return {
            'token': token,
            'expires': expiration.isoformat()
        }

    logger.warning(f"Login failed for user: {request.username}")
    raise HTTPException(status_code=401, detail="Invalid credentials")


# POST endpoint for chat initialization
@app.post("/api/chat-stream")
async def chat_stream_post(request: Request):
    """Initialize streaming via POST request"""
    # Extract token from header
    auth_header = request.headers.get('Authorization')
    token = None

    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split('Bearer ')[1]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing token in Authorization header"
        )

    if token not in active_tokens:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    # Parse request body
    body = await request.json()
    messages = body.get("messages", [])

    if not messages:
        raise HTTPException(
            status_code=400,
            detail="No messages provided"
        )

    # Store messages in cache for GET endpoint
    active_tokens[token]['messages'] = messages

    return {"status": "ready", "token": token}


# Function to handle streaming with max length checking
async def stream_from_api(messages, max_tokens=4000):
    """
    Stream from the API with max length handling.

    Args:
        messages: List of message objects to send to the API
        max_tokens: Maximum number of tokens to generate
    """
    # Create custom headers with auth token
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # Send debug event
    debug_msg = f"Starting chat completion with {len(messages)} messages using model: {DEFAULT_MODEL}"
    logger.info(debug_msg)
    yield f"event: debug\ndata: {debug_msg}\n\n"

    try:
        # Create streaming completion using standard client
        stream = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,  # Add max tokens parameter
            extra_headers=headers
        )

        # Track total response length for debugging
        total_chars = 0

        # Process stream using the iterator
        for chunk in stream:
            # Check if chunk has content
            if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content

                # Update total characters count
                total_chars += len(content)

                # Log every 500 characters
                if total_chars % 500 < len(content):
                    logger.info(f"Streamed {total_chars} characters so far")

                # Send content in SSE format
                yield f"data: {json.dumps({'content': content})}\n\n"

                # Send debug info periodically (not for every token to reduce overhead)
                if total_chars % 200 < len(content):
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    debug_msg = f"[{timestamp}] Streamed {total_chars} characters total"
                    yield f"event: debug\ndata: {debug_msg}\n\n"

                # Small delay for client processing
                await asyncio.sleep(0.01)

        # Send completion event
        logger.info(f"Streaming completed successfully. Total characters: {total_chars}")
        yield f"event: completion\ndata: {json.dumps({'status': 'complete', 'total_chars': total_chars})}\n\n"

    except Exception as e:
        # Send error event
        error_message = str(e)
        logger.error(f"Error in streaming: {error_message}")
        yield f"event: error\ndata: {json.dumps({'error': error_message})}\n\n"


# GET endpoint for SSE streaming
@app.get("/api/chat-stream")
async def chat_stream_get(request: Request):
    """Stream chat completions using SSE"""
    # Get token from query params
    token = request.query_params.get('token')

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing token. Add 'token' as a query parameter"
        )

    if token not in active_tokens:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    # Get messages from cache
    messages = active_tokens[token].get('messages', [])
    if not messages:
        raise HTTPException(
            status_code=400,
            detail="No messages found for this token. Send a POST request first"
        )

    # Get max_tokens from query params or use default
    try:
        max_tokens = int(request.query_params.get('max_tokens', 4000))
    except ValueError:
        max_tokens = 4000

    # Return streaming response
    return StreamingResponse(
        stream_from_api(messages, max_tokens),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# Run when directly executed
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 5001))
    uvicorn.run("app:app", host="0.0.0.0", port=port)