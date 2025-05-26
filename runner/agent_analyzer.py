"""
Agent Analyzer Module

This module analyzes LangChain agent code to extract information needed
for generating a standalone app.py file.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Callable


class AgentAnalyzer:
    """Analyzes LangChain agent code to extract deployment information."""

    def __init__(self, llm_completion: Callable):
        self.llm_completion = llm_completion

    def analyze_agent(self, agent_path: Path) -> Dict[str, Any]:
        """
        Analyze agent directory and extract information for app generation.

        Args:
            agent_path: Path to agent directory

        Returns:
            Dictionary with analysis results
        """
        try:
            # Read all Python files
            python_files = self._read_python_files(agent_path)

            # Extract code structure
            code_structure = self._extract_code_structure(python_files)

            # Load analysis prompt
            analysis_prompt = self._load_prompt("analysis_prompt.txt")

            # Prepare context for LLM
            context = self._prepare_analysis_context(python_files, code_structure)

            # Get LLM analysis
            messages = [
                {"role": "system", "content": analysis_prompt},
                {"role": "user", "content": context}
            ]

            llm_response = self.llm_completion(messages)

            # Parse LLM response
            analysis = self._parse_llm_analysis(llm_response)

            return {
                "success": True,
                "analysis": analysis,
                "code_structure": code_structure,
                "files_analyzed": list(python_files.keys())
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _read_python_files(self, agent_path: Path) -> Dict[str, str]:
        """Read all Python files in the agent directory."""
        python_files = {}

        for file_path in agent_path.rglob("*.py"):
            if file_path.is_file():
                relative_path = file_path.relative_to(agent_path)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        python_files[str(relative_path)] = f.read()
                except Exception as e:
                    print(f"Warning: Could not read {relative_path}: {e}")

        return python_files

    def _extract_code_structure(self, python_files: Dict[str, str]) -> Dict[str, Any]:
        """Extract structural information from Python files using AST."""
        structure = {
            "classes": [],
            "functions": [],
            "imports": [],
            "constants": []
        }

        for file_path, content in python_files.items():
            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        structure["classes"].append({
                            "name": node.name,
                            "file": file_path,
                            "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                        })
                    elif isinstance(node, ast.FunctionDef) and not hasattr(node, 'parent_class'):
                        structure["functions"].append({
                            "name": node.name,
                            "file": file_path,
                            "args": [arg.arg for arg in node.args.args]
                        })
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            structure["imports"].append({
                                "module": alias.name,
                                "file": file_path
                            })
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            for alias in node.names:
                                structure["imports"].append({
                                    "module": f"{node.module}.{alias.name}",
                                    "file": file_path
                                })

            except SyntaxError as e:
                print(f"Warning: Could not parse {file_path}: {e}")

        return structure

    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt from text file."""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Return default prompt if file not found
            return self._get_default_analysis_prompt()

    def _get_default_analysis_prompt(self) -> str:
        """Default analysis prompt if file is not found."""
        return """
You are an expert Python developer specializing in LangChain agents. 
Analyze the provided agent code and extract the following information:

1. Main agent creation function or class
2. Required imports for running the agent
3. Required parameters (LLM, tools, prompts, etc.)
4. Example usage patterns from comments/docstrings
5. Input/output format
6. Any special configuration requirements

Provide your analysis in JSON format with the following structure:
{
    "main_function": "function_name",
    "main_class": "class_name_if_applicable",
    "required_imports": ["import1", "import2"],
    "required_parameters": {
        "llm": "description",
        "tools": "description",
        "prompt": "description"
    },
    "usage_example": "extracted_example_code",
    "input_format": "description",
    "output_format": "description",
    "special_requirements": ["requirement1", "requirement2"]
}
"""

    def _prepare_analysis_context(self, python_files: Dict[str, str], code_structure: Dict[str, Any]) -> str:
        """Prepare context for LLM analysis."""
        context = "AGENT CODE ANALYSIS REQUEST\n\n"
        context += "FILES TO ANALYZE:\n"

        for file_path, content in python_files.items():
            context += f"\n--- {file_path} ---\n"
            context += content
            context += "\n"

        context += "\nCODE STRUCTURE SUMMARY:\n"
        context += f"Classes found: {[cls['name'] for cls in code_structure['classes']]}\n"
        context += f"Functions found: {[func['name'] for func in code_structure['functions']]}\n"
        context += f"Key imports: {list(set([imp['module'] for imp in code_structure['imports']]))}\n"

        # Extract and highlight prompt requirements from docstrings/comments
        prompt_hints = self._extract_prompt_requirements(python_files)
        if prompt_hints:
            context += "\nEXTRACTED PROMPT REQUIREMENTS AND PATTERNS:\n"
            context += prompt_hints
            context += "\n*** CRITICAL: Use these prompt requirements in your analysis ***\n"

        return context

    def _extract_prompt_requirements(self, python_files: Dict[str, str]) -> str:
        """Extract prompt requirements from docstrings and comments."""
        requirements = []

        for file_path, content in python_files.items():
            lines = content.split('\n')

            # Look for prompt requirement patterns
            in_prompt_section = False
            prompt_section = []

            for i, line in enumerate(lines):
                line_lower = line.lower()

                # Detect start of prompt documentation
                if any(keyword in line_lower for keyword in ['prompt:', 'the prompt must', 'required variables', 'input keys']):
                    in_prompt_section = True
                    prompt_section = [line.strip()]
                    continue

                # Continue collecting prompt section
                if in_prompt_section:
                    # Stop if we hit another major section or function definition
                    if (line.strip().startswith('def ') or
                        line.strip().startswith('class ') or
                        line.strip().startswith('Args:') or
                        line.strip().startswith('Returns:') or
                        line.strip().startswith('Example:')):

                        if len(prompt_section) > 1:  # Only add if we collected meaningful content
                            requirements.append(f"From {file_path}:\n" + "\n".join(prompt_section))
                        in_prompt_section = False
                        prompt_section = []
                    else:
                        prompt_section.append(line.strip())

                # Look for specific patterns
                if any(pattern in line_lower for pattern in ['messagesplaceholder', 'input_variables', 'partial_variables']):
                    requirements.append(f"From {file_path}, line {i+1}: {line.strip()}")

        return "\n\n".join(requirements)

    def _parse_llm_analysis(self, llm_response: str) -> Dict[str, Any]:
        """Parse LLM response into structured analysis."""
        try:
            # Try to extract JSON from response
            import json

            # Look for JSON blocks in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Try to parse the entire response as JSON
                parsed = json.loads(llm_response)

            # Ensure prompt_requirements exists and has proper structure
            if 'prompt_requirements' not in parsed:
                parsed['prompt_requirements'] = {
                    "required_variables": [],
                    "variable_descriptions": {},
                    "special_placeholders": [],
                    "prompt_pattern": ""
                }

            return parsed

        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, return a structured response with the raw text
            return {
                "main_function": "unknown",
                "main_class": "unknown",
                "required_imports": [],
                "required_parameters": {},
                "prompt_requirements": {
                    "required_variables": [],
                    "variable_descriptions": {},
                    "special_placeholders": [],
                    "prompt_pattern": ""
                },
                "usage_example": "",
                "input_format": "text",
                "output_format": "text",
                "special_requirements": [],
                "raw_analysis": llm_response
            }