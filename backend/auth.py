# backend/auth.py

import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from models import LoginRequest

# Handle login and token generation
async def handle_login(request: LoginRequest, active_tokens, token_expiration, logger):
    """Simple login to obtain an access token"""
    logger.info(f"Login attempt for user: {request.username}")

    # Simple authentication for MVP
    if request.username == 'user' and request.password == 'password':
        # Generate token
        token = secrets.token_hex(16)
        expiration = datetime.now() + timedelta(hours=token_expiration)

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