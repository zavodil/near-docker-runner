# backend/config.py

import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Check for required environment variables
required_env_vars = ['API_BASE_URL', 'AUTH_TOKEN', 'DEFAULT_MODEL']
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
    logging.error(error_msg)
    raise EnvironmentError(error_msg)

# Configuration constants
API_BASE_URL = os.environ.get('API_BASE_URL')
AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL')
TOKEN_EXPIRATION = 24  # hours
AGENTS_DIR = "agents"

# Initialize OpenAI client
client = OpenAI(
    api_key="dummy",  # Will be overridden by auth header
    base_url=API_BASE_URL
)