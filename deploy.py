#!/usr/bin/env python3
"""
Automated deployment script for pabulib-checker to PyPI.
Reads API tokens from environment variables or .env file.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    print(
        "Warning: python-dotenv not installed. Install with: pip install python-dotenv"
    )
    print("Environment variables will only be read from system environment.")


def load_environment():
    """Load environment variables from .env file if it exists."""
    if HAS_DOTENV:
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
            print("✅ Loaded environment variables from .env file")
        else:
            print("ℹ️  No .env file found, using system environment variables")


def get_api_token(test_pypi=False):
    """Get the appropriate API token from environment variables."""
    token_name = "TEST_PYPI_API_TOKEN" if test_pypi else "PYPI_API_TOKEN"
    token = os.getenv(token_name)

    if not token:
        repository = "TestPyPI" if test_pypi else "PyPI"
        print(f"❌ Error: {token_name} not found in environment variables")
        print(f"Please set your {repository} API token:")
        print(f"export {token_name}=pypi-your-token-here")
        print(f"Or add it to your .env file:")
        print(f"{token_name}=pypi-your-token-here")
        return None

    return token


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}")
        print(f"Command: {command}")
        print(f"Exit code: {e.returncode}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def deploy_to_pypi(test_pypi=False, skip_build=False):
    """Deploy the package to PyPI or TestPyPI."""

    # Load environment variables
    load_environment()

    # Get API token
    token = get_api_token(test_pypi)
    if not token:
        return False

    repository = "TestPyPI" if test_pypi else "PyPI"
    print(f"🚀 Starting deployment to {repository}")

    if not skip_build:
        # Clean previous builds
        if not run_command(
            "rm -rf dist/ build/ *.egg-info", "Cleaning previous builds"
        ):
            return False

        # Install/upgrade build tools
        if not run_command(
            "pip install --upgrade build twine", "Installing/upgrading build tools"
        ):
            return False

        # Build the package
        if not run_command("python -m build", "Building package"):
            return False

        # Check the package
        if not run_command("twine check dist/*", "Checking package"):
            return False

    # Prepare upload command
    if test_pypi:
        upload_cmd = f"twine upload --repository testpypi dist/* --username __token__ --password {token}"
    else:
        upload_cmd = f"twine upload dist/* --username __token__ --password {token}"

    # Upload to PyPI
    print(f"📦 Uploading to {repository}...")
    try:
        result = subprocess.run(
            upload_cmd, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ Successfully uploaded to {repository}!")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error uploading to {repository}")
        print(f"Exit code: {e.returncode}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Deploy pabulib-checker to PyPI")
    parser.add_argument(
        "--test", action="store_true", help="Deploy to TestPyPI instead of PyPI"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip building and use existing dist/ files",
    )

    args = parser.parse_args()

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print(
            "❌ Error: pyproject.toml not found. Make sure you're in the project root directory."
        )
        sys.exit(1)

    success = deploy_to_pypi(test_pypi=args.test, skip_build=args.skip_build)

    if success:
        repository = "TestPyPI" if args.test else "PyPI"
        print(f"🎉 Deployment to {repository} completed successfully!")
        if not args.test:
            print("🔗 View your package at: https://pypi.org/project/pabulib-checker/")
        else:
            print(
                "🔗 View your package at: https://test.pypi.org/project/pabulib-checker/"
            )
    else:
        print("💥 Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
