from dotenv import load_dotenv
load_dotenv()
import os
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Sequence
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool
from langchain_core.prompts import PromptTemplate
from langchain.agents import AgentExecutor
from langchain.agents.conversational.base import ConversationalAgent
from langchain.agents.conversational.prompt import PREFIX, SUFFIX, FORMAT_INSTRUCTIONS
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_path: str = "input.json") -> Dict[str, Any]:
    """Load configuration from JSON file"""
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
    """Initialize the language model based on configuration"""
    model_name = os.getenv('DEFAULT_MODEL_NAME', config.get('llm_model', 'claude-opus-4-20250514'))
    temperature = config.get('temperature', 0.7)
    max_tokens = config.get('max_tokens', 2000)
    
    logger.info(f"Initializing LLM: {model_name}")
    
    try:
        if 'gpt' in model_name.lower():
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif 'claude' in model_name.lower():
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            logger.warning(f"Unknown model type: {model_name}, defaulting to ChatOpenAI")
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
    except Exception as e:
        logger.error(f"Error initializing LLM: {e}")
        raise

def initialize_tools(config: Dict[str, Any], llm: BaseLanguageModel) -> List[BaseTool]:
    """Initialize tools based on configuration"""
    tools = []
    tool_config = config.get('tool_config', {})
    handle_errors = tool_config.get('handle_import_errors', True)
    warn_missing = tool_config.get('warn_on_missing_tools', True)
    
    for tool_name in config.get('default_tools', ['search', 'calculator']):
        try:
            if tool_name == "search":
                from langchain_community.tools import DuckDuckGoSearchRun
                tools.append(DuckDuckGoSearchRun())
                logger.info("Initialized search tool")
            elif tool_name == "calculator":
                from langchain.chains import LLMMathChain
                from langchain.tools import Tool
                llm_math = LLMMathChain.from_llm(llm)
                tools.append(Tool(
                    name="Calculator",
                    description="useful for mathematical calculations",
                    func=llm_math.run
                ))
                logger.info("Initialized calculator tool")
            else:
                if warn_missing:
                    logger.warning(f"Unknown tool: {tool_name}")
        except ImportError as e:
            if handle_errors:
                logger.warning(f"Could not import tool {tool_name}: {e}")
            else:
                raise
        except Exception as e:
            logger.error(f"Error initializing tool {tool_name}: {e}")
            if not handle_errors:
                raise
    
    return tools

def create_agent(llm: BaseLanguageModel, tools: Sequence[BaseTool], config: Dict[str, Any]) -> tuple:
    """Create the conversational agent and executor"""
    try:
        # Create the agent using from_llm_and_tools
        agent = ConversationalAgent.from_llm_and_tools(
            llm=llm,
            tools=tools,
            prefix=PREFIX,
            suffix=SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
            ai_prefix="AI",
            human_prefix="Human"
        )
        
        # Create memory for conversation history
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=False
        )
        
        # Create the agent executor
        agent_config = config.get('agent_config', {})
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=agent_config.get('verbose', True),
            max_iterations=agent_config.get('max_iterations', 10),
            early_stopping_method=agent_config.get('early_stopping_method', 'generate')
        )
        
        return agent_executor, memory
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise

def load_input(input_source: str) -> str:
    """Load input from file or return as string"""
    if os.path.isfile(input_source):
        with open(input_source, 'r') as f:
            return f.read().strip()
    return input_source

def save_output(output_data: Dict[str, Any], output_path: str = "output.json"):
    """Save output to JSON file"""
    try:
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        logger.info(f"Output saved to {output_path}")
    except Exception as e:
        logger.error(f"Error saving output: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Run LangChain Conversational Agent')
    parser.add_argument('--input', type=str, help='Input text or file path')
    parser.add_argument('--output', type=str, default='output.json', help='Output file path')
    parser.add_argument('--config', type=str, default='input.json', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Set up logging
    log_level = config.get('error_handling', {}).get('log_level', 'INFO')
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Initialize components
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'config': config,
        'success': False
    }
    
    try:
        # Initialize LLM
        llm = initialize_llm(config)
        
        # Initialize tools
        tools = initialize_tools(config, llm)
        output_data['tools_loaded'] = [tool.name for tool in tools]
        
        # Create agent
        agent_executor, memory = create_agent(llm, tools, config)
        
        # Get input
        if args.input:
            input_text = load_input(args.input)
        else:
            input_text = config.get('default_input', 'Hello, how can you help me?')
        
        output_data['input'] = input_text
        
        # Execute agent
        logger.info(f"Executing agent with input: {input_text}")
        result = agent_executor.invoke({"input": input_text})
        
        # Process result
        output_data['success'] = True
        output_data['result'] = result.get('output', '')
        output_data['chat_history'] = memory.chat_memory.messages if hasattr(memory, 'chat_memory') else []
        
        if config.get('include_metadata', True):
            output_data['metadata'] = {
                'model': os.getenv('DEFAULT_MODEL_NAME', config.get('llm_model', 'claude-opus-4-20250514')),
                'temperature': config.get('temperature', 0.7),
                'max_tokens': config.get('max_tokens', 2000),
                'tools_used': [tool.name for tool in tools],
                'execution_time': datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        output_data['error'] = str(e)
        if config.get('error_handling', {}).get('save_errors_to_output', True):
            output_data['error_details'] = {
                'type': type(e).__name__,
                'message': str(e)
            }
    
    # Save output
    save_output(output_data, args.output)

if __name__ == "__main__":
    main()