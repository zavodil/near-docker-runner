from dotenv import load_dotenv
load_dotenv()
import os
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List, Sequence, Union
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.tools.render import render_text_description
from langchain_core.prompts import MessagesPlaceholder
from langchain.agents import AgentExecutor, create_json_chat_agent
from langchain import hub
from langchain_core.messages import AIMessage, HumanMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path: str = "input.json") -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def initialize_llm(config: Dict[str, Any]) -> BaseLanguageModel:
    """Initialize the language model based on configuration."""
    model_name = os.getenv('DEFAULT_MODEL_NAME', config.get('llm_model', 'claude-opus-4-20250514'))
    temperature = config.get('temperature', 0.7)
    max_tokens = config.get('max_tokens', 2000)
    
    try:
        if 'gpt' in model_name.lower():
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif 'claude' in model_name.lower():
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
    except Exception as e:
        logger.error(f"Error initializing LLM: {e}")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(temperature=temperature, max_tokens=max_tokens)

def initialize_tools(config: Dict[str, Any], llm: BaseLanguageModel) -> List[BaseTool]:
    """Initialize tools based on configuration."""
    tools = []
    tool_config = config.get('tool_config', {})
    handle_errors = tool_config.get('handle_import_errors', True)
    warn_missing = tool_config.get('warn_on_missing_tools', True)
    
    for tool_name in config.get('default_tools', ['search', 'calculator']):
        try:
            if tool_name == "search":
                from langchain_community.tools import DuckDuckGoSearchRun
                tools.append(DuckDuckGoSearchRun())
                logger.info(f"Initialized tool: {tool_name}")
            elif tool_name == "calculator":
                from langchain.chains import LLMMathChain
                from langchain.tools import Tool
                llm_math = LLMMathChain.from_llm(llm)
                tools.append(Tool(
                    name="Calculator",
                    description="useful for mathematical calculations",
                    func=llm_math.run
                ))
                logger.info(f"Initialized tool: {tool_name}")
            else:
                if warn_missing:
                    logger.warning(f"Unknown tool: {tool_name}")
        except Exception as e:
            if handle_errors:
                logger.error(f"Failed to initialize tool {tool_name}: {e}")
            else:
                raise
    
    return tools

def create_prompt(tools: List[BaseTool]) -> ChatPromptTemplate:
    """Create the prompt template for the agent."""
    try:
        prompt = hub.pull("hwchase17/react-chat-json")
        logger.info("Successfully pulled prompt from hub")
        return prompt
    except Exception as e:
        logger.warning(f"Failed to pull prompt from hub: {e}, creating custom prompt")
        
        system = """You are a helpful AI assistant that can use tools to help answer questions.
You have access to the following tools:
{tools}

Tool names: {tool_names}

Always respond in valid JSON format. When you need to use a tool, respond with:
{{"action": "tool_name", "action_input": "input for the tool"}}

When you have a final answer, respond with:
{{"action": "Final Answer", "action_input": "your final answer here"}}"""

        human = "{input}"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", human),
            MessagesPlaceholder("agent_scratchpad")
        ])
        
        return prompt

def load_input(input_source: str) -> str:
    """Load input from file or return as string."""
    if os.path.isfile(input_source):
        with open(input_source, 'r') as f:
            return f.read().strip()
    return input_source

def save_output(result: Any, output_path: str, config: Dict[str, Any], error: str = None):
    """Save the output to a JSON file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "llm_model": config.get('llm_model', 'claude-opus-4-20250514'),
            "temperature": config.get('temperature', 0.7),
            "max_tokens": config.get('max_tokens', 2000),
            "tools": config.get('default_tools', ['search', 'calculator'])
        }
    }
    
    if error:
        output_data["error"] = error
        output_data["success"] = False
    else:
        output_data["success"] = True
        if isinstance(result, dict):
            output_data["result"] = result
        else:
            output_data["result"] = str(result)
    
    if config.get('include_metadata', True):
        output_data["metadata"] = {
            "agent_type": "json_chat",
            "execution_time": datetime.now().isoformat()
        }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Output saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Run LangChain JSON Chat Agent')
    parser.add_argument('--input', type=str, help='Input text or path to input file')
    parser.add_argument('--output', type=str, default='output.json', help='Output file path')
    parser.add_argument('--config', type=str, default='input.json', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Set up logging
    log_level = config.get('error_handling', {}).get('log_level', 'INFO')
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    try:
        # Initialize LLM
        llm = initialize_llm(config)
        
        # Initialize tools
        tools = initialize_tools(config, llm)
        
        if not tools:
            logger.warning("No tools initialized, agent may have limited functionality")
        
        # Create prompt
        prompt = create_prompt(tools)
        
        # Partial the prompt with tools information
        tools_renderer = render_text_description
        prompt = prompt.partial(
            tools=tools_renderer(tools),
            tool_names=', '.join([t.name for t in tools])
        )
        
        # Create agent
        agent = create_json_chat_agent(llm, tools, prompt)
        
        # Create agent executor
        agent_config = config.get('agent_config', {})
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=agent_config.get('verbose', True),
            max_iterations=agent_config.get('max_iterations', 10),
            early_stopping_method=agent_config.get('early_stopping_method', 'generate')
        )
        
        # Get input
        if args.input:
            input_text = load_input(args.input)
        else:
            input_text = config.get('default_input', 'Hello, how can you help me?')
        
        logger.info(f"Processing input: {input_text}")
        
        # Execute agent
        result = agent_executor.invoke({"input": input_text})
        
        # Save output
        save_output(result, args.output, config)
        
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        if config.get('error_handling', {}).get('save_errors_to_output', True):
            save_output(None, args.output, config, error=str(e))
        raise

if __name__ == "__main__":
    main()