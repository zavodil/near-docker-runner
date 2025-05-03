# backend/app.py

import os
import json
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import datetime

# Import from local modules
from models import LoginRequest, ChatRequest
from auth import handle_login
from agent_manager import stream_from_agent, cleanup_old_processes
from config import AGENTS_DIR, TOKEN_EXPIRATION

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory token storage (for MVP only)
active_tokens = {}

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
    return await handle_login(request, active_tokens, TOKEN_EXPIRATION, logger)


# New endpoint for chat completions with agent support
@app.post("/chat/completions")
async def chat_completions(request: ChatRequest, req: Request, background_tasks: BackgroundTasks):
    """Handle chat completions with agent support"""
    # Extract token from header
    auth_header = req.headers.get('Authorization')
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

    # Schedule cleanup of old processes
    background_tasks.add_task(cleanup_old_processes)

    # Get agent name and messages
    agent_name = request.agent_name
    messages = request.messages

    if not messages:
        raise HTTPException(
            status_code=400,
            detail="No messages provided"
        )

    if not agent_name:
        raise HTTPException(
            status_code=400,
            detail="No agent_name provided"
        )

    # Check if agent exists
    agent_path = os.path.join(AGENTS_DIR, agent_name, "agent.py")
    if not os.path.exists(agent_path):
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found"
        )

    # Store messages and agent in token data
    active_tokens[token]['messages'] = messages
    active_tokens[token]['agent_name'] = agent_name
    active_tokens[token]['max_tokens'] = request.max_tokens

    # If not streaming, run agent directly and return result
    if not request.stream:
        # TODO: Implement non-streaming mode
        raise HTTPException(
            status_code=501,
            detail="Non-streaming mode not implemented yet"
        )

    # Return streaming response, passing the token for persistent sessions
    return StreamingResponse(
        stream_from_agent(agent_name, messages, request.max_tokens, token),
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

    # Make sure agents directory exists
    if not os.path.exists(AGENTS_DIR):
        os.makedirs(AGENTS_DIR)

    port = int(os.environ.get("PORT", 5001))
    uvicorn.run("app:app", host="0.0.0.0", port=port)