#!/usr/bin/env python3
"""
LangChain Agent Deployer

This script automatically analyzes LangChain agent code and generates a standalone app.py
that can run the agent with command-line arguments and save outputs to files.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List

from llm import llm_completion
from agent_analyzer import AgentAnalyzer
from app_generator import AppGenerator

from dotenv import load_dotenv

load_dotenv()


def load_input_config(input_file: str = "input.json") -> Dict[str, Any]:
    """Load input configuration for the agent deployment."""

    default_model_name = os.getenv("DEFAULT_MODEL_NAME")
    print("default_model_name", default_model_name)

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {input_file} not found, using default configuration")
        return {
            "llm_model": default_model_name,
            "temperature": 0.7,
            "max_tokens": 2000,
            "default_tools": [],
            "default_input": "Hello, how can you help me?"
        }
    except json.JSONDecodeError as e:
        print(f"Error parsing {input_file}: {e}")
        sys.exit(1)


def save_deployment_config(output_data: Dict[str, Any], output_file: Path = "deployment.json") -> None:
    """Save deployment results to output file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print("output_data", output_data)
        print(f"Deployment results saved to {output_file}")
    except Exception as e:
        print(f"Error saving output file: {e}")


def copy_agent_files(source_path: Path, dest_path: Path) -> List[str]:
    """Copy all agent files to destination directory without modifications."""
    copied_files = []

    # Create destination directory if it doesn't exist
    dest_path.mkdir(parents=True, exist_ok=True)

    # Copy all Python files from source
    for file_path in source_path.rglob("*.py"):
        if file_path.is_file():
            relative_path = file_path.relative_to(source_path)
            dest_file = dest_path / relative_path

            # Create subdirectories if needed
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(file_path, dest_file)
            copied_files.append(str(relative_path))
            print(f"Copied: {relative_path}")

    return copied_files


def main():
    parser = argparse.ArgumentParser(
        description="Deploy LangChain agent with auto-generated app.py"
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Relative path to the agent directory"
    )

    args = parser.parse_args()

    # Setup paths
    agent_path = Path(args.agent).resolve()
    if not agent_path.exists() or not agent_path.is_dir():
        print(f"Error: Agent directory '{agent_path}' does not exist")
        sys.exit(1)

    agent_name = agent_path.name
    output_dir = Path(f"out_{agent_name}")

    print(f"Analyzing agent: {agent_path}")
    print(f"Output directory: {output_dir}")

    # Load configuration
    config = load_input_config()

    try:
        # Initialize components
        analyzer = AgentAnalyzer(llm_completion)
        generator = AppGenerator(llm_completion)

        # Analyze agent code
        print("Analyzing agent code...")
        analysis_result = analyzer.analyze_agent(agent_path)

        if not analysis_result["success"]:
            print(f"Error analyzing agent: {analysis_result['error']}")
            sys.exit(1)

        # Copy agent files to output directory
        print("Copying agent files...")
        copied_files = copy_agent_files(agent_path, output_dir)

        # Generate app.py
        print("Generating app.py...")
        app_generation_result = generator.generate_app(
            analysis_result["analysis"],
            config,
            agent_name
        )

        if not app_generation_result["success"]:
            print(f"Error generating app.py: {app_generation_result['error']}")
            sys.exit(1)

        # Save app.py to output directory
        app_py_path = output_dir / "app.py"
        with open(app_py_path, 'w', encoding='utf-8') as f:
            f.write(app_generation_result["app_code"])

        # Copy all files from /server to output directory
        server_path = Path(__file__).parent / "server"
        if server_path.exists() and server_path.is_dir():
            for file_path in server_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(server_path)
                    dest_file = output_dir / relative_path

                    # Create subdirectories if needed
                    dest_file.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    shutil.copy2(file_path, dest_file)
                    print(f"Copied server file: {relative_path}")


        print(f"Generated app.py at: {app_py_path}")

        # Prepare output data
        output_data = {
            "agent_name": agent_name,
            "agent_path": str(agent_path),
            "output_directory": str(output_dir),
            "copied_files": copied_files,
            "analysis": analysis_result["analysis"],
            "generation_success": True,
            "app_py_generated": True,
            "config_used": config
        }

        # Save output configuration
        save_deployment_config(output_data, output_dir / "deployment.json")

        print(f"Agent deployment completed successfully!")
        print(f"Output directory: {output_dir}")
        print(f"Run with: \ncd {output_dir} && python app.py")

    except Exception as e:
        print(f"Deployment failed: {e}")

        # Save error output
        error_output = {
            "agent_name": agent_name,
            "agent_path": str(agent_path),
            "generation_success": False,
            "error": str(e),
            "config_used": config
        }
        save_output_config(error_output)
        sys.exit(1)


if __name__ == "__main__":
    main()