#!/usr/bin/env python3
"""
Lambda Invocation Harness for Local Testing

Usage:
    python invoke_lambda.py <lambda_name> <event_json_file>

Example:
    python invoke_lambda.py uploadSpineLambda test_events/uploadSpine.json
"""

import sys
import os
import json
import importlib.util
from pathlib import Path
from dotenv import load_dotenv
from mock_context import MockLambdaContext

# Load environment variables from .env.local
env_path = Path(__file__).parent.parent / '.env.local'
load_dotenv(dotenv_path=env_path)

# Add Python Lambda directory to path
lambda_python_dir = Path(__file__).parent.parent.parent / 'aws_lambdas' / 'python'
sys.path.insert(0, str(lambda_python_dir))


def load_lambda_module(lambda_name):
    """Dynamically import a Lambda module by name."""
    lambda_dir = Path(__file__).parent.parent.parent / 'aws_lambdas'

    # Try Python Lambdas first
    python_lambda_path = lambda_dir / 'python' / f'{lambda_name}.py'
    if python_lambda_path.exists():
        spec = importlib.util.spec_from_file_location(lambda_name, python_lambda_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # Try JavaScript Lambdas (would need Node.js integration)
    js_lambda_path = lambda_dir / 'javascript' / f'{lambda_name}.js'
    if js_lambda_path.exists():
        print(f"Error: JavaScript Lambda found but Node.js execution not implemented")
        print(f"Please run JavaScript Lambdas manually with Node.js")
        sys.exit(1)

    raise FileNotFoundError(f"Lambda not found: {lambda_name}")


def load_event(event_file):
    """Load event JSON from file."""
    with open(event_file, 'r') as f:
        return json.load(f)


def main():
    if len(sys.argv) != 3:
        print("Usage: python invoke_lambda.py <lambda_name> <event_json_file>")
        sys.exit(1)

    lambda_name = sys.argv[1]
    event_file = sys.argv[2]

    print(f"Loading Lambda: {lambda_name}")
    print(f"Loading event from: {event_file}")
    print("-" * 60)

    try:
        # Load the Lambda module
        lambda_module = load_lambda_module(lambda_name)

        # Load the event
        event = load_event(event_file)

        # Create mock context
        context = MockLambdaContext(function_name=lambda_name)

        # Invoke the Lambda handler
        print(f"\nInvoking {lambda_name}.lambda_handler()...\n")
        response = lambda_module.lambda_handler(event, context)

        # Print the response
        print("-" * 60)
        print("Response:")
        print(json.dumps(response, indent=2))
        print("-" * 60)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error invoking Lambda: {type(e).__name__}")
        print(f"Message: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
