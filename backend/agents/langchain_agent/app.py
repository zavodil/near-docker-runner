"""
FastAPI server for LangChain Agent API
"""
import os
import json
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Security, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from dotenv import load_dotenv

# Import your LangChain agent components
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool
from langchain.agents import AgentExecutor
from langchain_core.callbacks.stdout import StdOutCallbackHandler
from langchain.tools.render import render_text_description_and_args
from langchain_core.runnables import RunnablePassthrough
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents.output_parsers import JSONAgentOutputParser
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

# Import your agent code
from base import create_structured_chat_agent
from prompt import FORMAT_INSTRUCTIONS, PREFIX, SUFFIX

# Load environment variables
load_dotenv()

# Load schema file
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), 'input_schema.json')
try:
    with open(SCHEMA_FILE, 'r') as f:
        SCHEMA = json.load(f)
except Exception as e:
    print(f"Warning: Could not load schema file: {e}")
    SCHEMA = {"properties": {}}

# Initialize FastAPI app
app = FastAPI(
    title="LangChain Agent API",
    description="API for running LangChain Structured Chat Agent",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API security
API_KEY = os.getenv("API_KEY", "default-api-key")
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

# Models for API requests and responses
class ToolModel(BaseModel):
    name: str
    description: str
    args_schema: Dict[str, Any]


# Get tools from schema and convert them to ToolModel objects
def get_schema_tools():
    """Get tools from schema and convert to ToolModel objects"""
    schema_tools = get_schema_property("tools", [])
    return [ToolModel(**tool) for tool in schema_tools]

# Get properties from schema
def get_schema_property(property_name, default=None):
    """Get a property from the schema, or return default if not found"""
    return SCHEMA.get("properties", {}).get(property_name, {}).get("default", default)

# Get tools from schema
BUILTIN_TOOLS = get_schema_tools()

class AgentRunRequest(BaseModel):
    input: str
    tools: List[ToolModel] = []
    llm_model: Optional[str] = get_schema_property("defaultModel")
    stop_sequence: bool = get_schema_property("stopSequence", True)
    system_message: Optional[str] = None
    human_message: Optional[str] = None
    temperature: float = get_schema_property("temperature", 0.1)
    max_tokens: int = get_schema_property("maxTokens", 16384)
    max_iterations: int = get_schema_property("maxIterations", 5)
    intermediate_steps: Optional[List[Dict[str, Any]]] = None

class AgentRunResponse(BaseModel):
    output: str
    intermediate_steps: List[Dict[str, Any]] = []

# New response model for tools
class ToolsResponse(BaseModel):
    tools: List[ToolModel]

# Generate API endpoints JSON file
def generate_api_endpoints_json():
    """Generate a list with all available API endpoints"""
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    endpoints = []
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            endpoints.append({
                "path": path,
                "method": method.upper(),
                "description": operation.get("summary", operation.get("description", ""))
            })

    api_endpoints = {"apiEndpoints": endpoints}

    return api_endpoints

# Helper functions
def create_tools_from_model(tool_models: List[ToolModel]) -> List[BaseTool]:
    """Convert API tool models to LangChain BaseTool instances"""
    from langchain.tools import Tool

    tools = []
    for tool_model in tool_models:
        # Check if tool_model is a dict (from schema) and convert to ToolModel
        if isinstance(tool_model, dict):
            tool_model = ToolModel(**tool_model)

        # Create a simple tool function that returns its input
        tool_name = tool_model.name

        def tool_func(input_str, _tool_name=tool_name):
            return f"Tool {_tool_name} executed with input: {input_str}"

        # Create a Tool instance (which is a concrete implementation of BaseTool)
        tool = Tool(
            name=tool_name,
            description=tool_model.description or f"Tool for {tool_name} operations",
            func=tool_func,
        )
        tools.append(tool)
    return tools

def get_llm(model_name: str, temperature: float = None, max_tokens: int = None) -> BaseLanguageModel:
    """Create LLM based on model name"""
    # Example using OpenAI - replace with your actual LLM initialization
    from langchain_openai import ChatOpenAI

    # Use values from schema if not explicitly provided
    if temperature is None:
        temperature = get_schema_property("temperature", 0.1)

    if max_tokens is None:
        max_tokens = get_schema_property("maxTokens", 16384)

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL")
    )

# API endpoints
@app.get("/")
async def root():
    """Get API information including available endpoints"""
    api_endpoints = generate_api_endpoints_json()

    return {
        "message": "LangChain Agent API is running",
        "endpoints": api_endpoints.get("apiEndpoints", []),
        "schema": SCHEMA.get("title", "LangChain Agent API") + " - " + SCHEMA.get("description", "")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# Endpoint to get all available API
@app.get("/api")
async def get_api():
    """Get all available API for the agent"""
    return generate_api_endpoints_json()

# Endpoint to get all available tools
@app.get("/tools", response_model=ToolsResponse, dependencies=[Depends(verify_api_key)])
async def get_tools():
    """Get all available tools for the agent"""
    return ToolsResponse(tools=BUILTIN_TOOLS)

@app.post("/run", response_model=AgentRunResponse, dependencies=[Depends(verify_api_key)])
async def run_agent(request: AgentRunRequest):
    """Run the agent with specified input and tools"""
    try:
        # Create LLM
        llm = get_llm(request.llm_model, request.temperature, request.max_tokens)
        print("Requested LLM model:", request.llm_model)

        # Create tools - use tools from request or BUILTIN_TOOLS if empty
        if request.tools and len(request.tools) > 0:
            tools = create_tools_from_model(request.tools)
        else:
            # If no tools provided, use builtin tools
            tools = create_tools_from_model(BUILTIN_TOOLS)

        # Log for debugging
        print(f"Created {len(tools)} tools: {[tool.name for tool in tools]}")
        tool_names = ", ".join([tool.name for tool in tools])
        print("Available tool names:", tool_names)

        # Define the human message template using the template from the original agent
        human_message_template = "{input}\n\n{agent_scratchpad}"

        # Create the prompt using the original format instructions from the agent
        prefix = PREFIX
        suffix = SUFFIX
        format_instructions = FORMAT_INSTRUCTIONS.format(tool_names=tool_names)

        # Create a list of tool strings for the prompt
        tool_strings = []
        for tool in tools:
            tool_strings.append(f"{tool.name}: {tool.description}")
        formatted_tools = "\n".join(tool_strings)

        # Combine the components to create the full template
        template = "\n\n".join([prefix, formatted_tools, format_instructions, suffix])

        # Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(template),
            HumanMessagePromptTemplate.from_template(human_message_template),
        ])

        # Bind variables to the prompt
        prompt = prompt.partial(tools=render_text_description_and_args(tools), tool_names=tool_names)

        agent =  create_structured_chat_agent(
            llm=llm,
            tools=tools,
            prompt=prompt,
            stop_sequence=request.stop_sequence
        )

        # Create agent executor with specified max iterations
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            max_iterations=request.max_iterations,
            callbacks=[StdOutCallbackHandler()]
        )

        # Run agent
        result = agent_executor.invoke({"input": request.input})

        # Return result
        return AgentRunResponse(
            output=result["output"],
            intermediate_steps=[
                {"action": step[0].tool, "input": step[0].tool_input, "observation": step[1]}
                for step in result.get("intermediate_steps", [])
            ]
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error running agent: {str(e)}\n{error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running agent: {str(e)}"
        )


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5005, reload=False)