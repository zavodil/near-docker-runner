# LangChain Agent API Server

This project provides a Docker-based API server for running LangChain structured chat agents. It serves as a universal wrapper that allows you to expose any LangChain agent via a REST API.

## Features

- 🚀 Simple FastAPI server for LangChain agents
- 🔧 Supports custom tools configuration 
- 📦 Docker-ready deployment
- 🔐 API key authentication
- 📚 Automatic API documentation
- ⚙️ Configurable via input_schema.json

## How it works

This example uses [structured_chat agent](https://github.com/langchain-ai/langchain/tree/master/libs/langchain/langchain/agents/structured_chat) without any changes. Only a few additional files are added:

- `app.py`: The main FastAPI application.
- `Dockerfile`: The Dockerfile for building the API server.
- `docker-compose.yml`: The Docker Compose file for running the API server.
- `input_schema.json`: The schema for the input to the agent.
- `requirements.txt`: The Python dependencies for the API server.
- `README.md`: This file.


## Quick Start

1. Create a `.env` file based on the provided `.env.example` file. This file should contain your API key.

2. Build and run the Docker container:
   ```bash
   docker build -t langchain-agent-api .
   docker run -p 5005:5005 --env-file .env langchain-agent-api
   ```

   Alternatively, use Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. The API is now available at http://localhost:5005, and you can play with it on http://localhost:5005/docs

## API Usage

### Authentication

All endpoints (except `/health`) require an API key:

```bash
curl -H "X-API-Key: your-secure-api-key" http://localhost:5005/tools
```

### Available Endpoints

- `GET /`: API information
- `GET /health`: Health check
- `GET /api`: API endpoints information
- `GET /tools`: List available tools
- `POST /run`: Run the agent

### Example: Run Agent

```bash
curl -X POST "http://localhost:5005/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{
    "input": "What is the capital of France?"
  }'
```

You can also specify the tools you want to use in the request.
```bash
curl -X POST "http://localhost:5005/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{
    "input": "Calculate number of days in 2020-2024 years",
    "tools": [{
        "name": "calculator",
        "description": "Useful for calculations",
        "args_schema": {}
      }]
  }'
```

## Configuration

The agent behavior can be configured by editing `input_schema.json`. This file defines:

- Default LLM model and inference parameters
- Available tools
- Default parameters