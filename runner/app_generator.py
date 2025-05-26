"""
App Generator Module

This module generates a standalone app.py file based on agent analysis results.
"""

import json
import re
from typing import Dict, Any, Callable


class AppGenerator:
    """Generates standalone app.py files for LangChain agents."""

    def __init__(self, llm_completion: Callable):
        self.llm_completion = llm_completion

    def generate_app(self, analysis: Dict[str, Any], config: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
        """
        Generate app.py code based on analysis results.

        Args:
            analysis: Agent analysis results
            config: Input configuration
            agent_name: Name of the agent

        Returns:
            Dictionary with generation results
        """
        try:
            # Load generation prompt
            generation_prompt = self._load_prompt("generation_prompt.txt")

            # Prepare context for LLM
            context = self._prepare_generation_context(analysis, config, agent_name)

            # Get LLM response
            messages = [
                {"role": "system", "content": generation_prompt},
                {"role": "user", "content": context}
            ]

            llm_response = self.llm_completion(messages)

            # Extract and clean the generated code
            app_code = self._extract_code_from_response(llm_response)

            return {
                "success": True,
                "app_code": app_code,
                "raw_response": llm_response
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt from text file."""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Return default prompt if file not found
            return self._get_default_generation_prompt()

    def _get_default_generation_prompt(self) -> str:
        """Default generation prompt if file is not found."""
        return """
You are an expert Python developer. Generate a complete, standalone app.py file for running a LangChain agent.

The app.py should:
1. Import all necessary modules (including from the agent files)
2. Set up command-line argument parsing
3. Initialize the agent with provided parameters
4. Run the agent with input from command line or file
5. Save output to a file
6. Handle errors gracefully

Requirements:
- Use argparse for command-line arguments
- Support --input for input text or file path
- Support --output for output file path (default: output.json)
- Support --config for configuration file
- Include proper error handling and logging
- Make it executable and well-documented

Generate ONLY the Python code for app.py, no explanations.
"""

    def _prepare_generation_context(self, analysis: Dict[str, Any], config: Dict[str, Any], agent_name: str) -> str:
        """Prepare context for app.py generation."""
        context = f"GENERATE APP.PY FOR AGENT: {agent_name}\n\n"

        context += "ANALYSIS RESULTS:\n"
        context += json.dumps(analysis, indent=2)
        context += "\n\n"

        context += "INPUT CONFIGURATION FROM input.json:\n"
        context += json.dumps(config, indent=2)
        context += "\n\n"

        context += "CRITICAL REQUIREMENTS:\n"
        context += "- ALWAYS include: from dotenv import load_dotenv\n"
        context += "- ALWAYS include: load_dotenv() call right after imports\n"
        context += "- Load input.json configuration file at startup\n"
        context += f"- Use model: os.getenv('DEFAULT_MODEL_NAME', config.get('llm_model', '{config.get('llm_model', 'gpt-3.5-turbo')}'))\n"
        context += f"- Use temperature: config.get('temperature', {config.get('temperature', 0.7)})\n"
        context += f"- Use max_tokens: config.get('max_tokens', {config.get('max_tokens', 2000)})\n"
        context += f"- Use default_tools: config.get('default_tools', {config.get('default_tools', [])})\n"
        context += f"- Use default_input: config.get('default_input', '{config.get('default_input', 'Hello')}')\n"
        context += "- MUST save output at the end with save_output() function call\n"
        context += "- Handle both text input and file input\n"
        context += "- NO markdown formatting in output - raw Python code only\n"
        context += "- NO empty lines at the start of the file\n"
        context += "- Complete main() function that actually saves the result\n"
        context += "\nPROMPT CREATION REQUIREMENTS:\n"
        prompt_reqs = analysis.get('prompt_requirements', {})
        required_vars = prompt_reqs.get('required_variables', [])
        context += f"- Required prompt variables: {required_vars}\n"
        context += f"- Variable descriptions: {prompt_reqs.get('variable_descriptions', {})}\n"
        context += f"- Special placeholders: {prompt_reqs.get('special_placeholders', [])}\n"
        context += f"- Prompt pattern: {prompt_reqs.get('prompt_pattern', 'Not specified')}\n"
        context += f"- Hub pull pattern: {prompt_reqs.get('hub_pull_pattern', 'None')}\n"
        context += "- CRITICAL: Prompt MUST have ALL required variables before agent creation\n"

        if 'tools' in required_vars and 'tool_names' in required_vars:
            context += "- MUST use prompt.partial(tools=tools_renderer(tools), tool_names=', '.join([t.name for t in tools]))\n"

        if 'agent_scratchpad' in required_vars:
            context += "- Include agent_scratchpad variable in prompt template\n"

        if 'hub.pull' in analysis.get('usage_example', ''):
            hub_pattern = re.search(r'hub\.pull\(["\']([^"\']+)["\']\)', analysis.get('usage_example', ''))
            if hub_pattern:
                context += f"- Use hub.pull('{hub_pattern.group(1)}') as shown in examples\n"

        context += "- Use MessagesPlaceholder for chat_history and agent_scratchpad if specified\n"
        context += "- Validate prompt variables match analysis requirements\n"
        context += "\nTOOL INITIALIZATION RULES:\n"
        context += "- NEVER use BaseTool() constructor directly - it's abstract\n"
        context += "- For 'search' tool: use DuckDuckGoSearchRun() from langchain_community.tools\n"
        context += "- For 'calculator' tool: use LLMMathChain.from_llm(llm) wrapped in Tool\n"
        context += "- Calculator is NOT in langchain_community.tools - use LLMMathChain instead\n"
        context += "- Always pass llm parameter to initialize_tools() function\n"
        context += "- Create individual if/elif blocks for each tool type\n"
        context += "- Import tools only when needed (inside the if blocks)\n"

        return context

    def _extract_code_from_response(self, llm_response: str) -> str:
        """Extract Python code from LLM response and clean it."""
        # Try to extract code from markdown code blocks
        code_match = re.search(r'```python\s*(.*?)\s*```', llm_response, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
        else:
            # If no code blocks found, use the entire response
            code = llm_response.strip()

        # Clean up the code
        lines = code.split('\n')

        # Remove empty lines at the beginning
        while lines and not lines[0].strip():
            lines.pop(0)

        # Remove markdown artifacts if any
        clean_lines = []
        for line in lines:
            # Skip lines that look like markdown
            if line.strip().startswith('```'):
                continue
            clean_lines.append(line)

        # Ensure the code ends properly
        final_code = '\n'.join(clean_lines)

        # Add missing save_output call if not present
        if 'save_output(' not in final_code and 'output' in final_code:
            # Find the last occurrence of output = and add save after it
            lines = final_code.split('\n')
            for i in range(len(lines) - 1, -1, -1):
                if 'output =' in lines[i] and 'execute_agent' in lines[i]:
                    # Insert save_output call after this line
                    indent = '        '  # Assuming it's in main() function
                    lines.insert(i + 1, f'{indent}# Save the output to file')
                    lines.insert(i + 2, f'{indent}save_output(output, args.output, config.get("include_metadata", True))')
                    break
            final_code = '\n'.join(lines)

        return final_code