# backend/models.py

from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Models for API requests and responses
class LoginRequest(BaseModel):
    username: str
    password: str

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    agent_name: str
    stream: bool = True
    max_tokens: Optional[int] = 4000