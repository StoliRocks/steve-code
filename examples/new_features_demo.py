#!/usr/bin/env python3
"""Example demonstrating new features: retry logic, git integration, and progress indicators."""

import time
from pathlib import Path
from ai_code_assistant.bedrock_client import BedrockClient, ModelType, Message
from ai_code_assistant.git_integration import GitIntegration
from ai_code_assistant.file_context import FileContextManager
from ai_code_assistant.retry_utils import retry_with_backoff
from botocore.exceptions import ClientError

# Example 1: Automatic Retry Logic
print("=== Retry Logic Demo ===")
print("The BedrockClient now automatically retries on transient errors.")
print("This happens transparently - no code changes needed!\n")

client = BedrockClient(model_type=ModelType.CLAUDE_SONNET_4)

# The retry logic is already applied to send_message via decorator
messages = [Message(role="user", content="Hello! Tell me about retry logic.")]

try:
    # This will automatically retry up to 3 times if there are transient errors
    response = client.send_message(messages, stream=False)
    print("Response received successfully (with automatic retry if needed)")
except Exception as e:
    print(f"Failed after retries: {e}")

# Example 2: Git Integration
print("\n=== Git Integration Demo ===")

try:
    git = GitIntegration()
    
    # Show git status
    status = git.get_status()
    print(f"Current branch: {status.branch}")
    print(f"Modified files: {len(status.modified)}")
    print(f"Untracked files: {len(status.untracked)}")
    print(f"Repository is {'clean' if status.is_clean else 'dirty'}")
    
    # Show recent commits
    print("\nRecent commits:")
    log = git.get_log(limit=5)
    print(log)
    
    # Get diff (if any changes)
    if status.modified:
        print("\nSample diff:")
        diff = git.get_diff()
        print(diff[:500] + "..." if len(diff) > 500 else diff)
        
        # You could generate a commit message using AI
        print("\nTo generate a commit message in interactive mode, use: /git commit")
        
except RuntimeError as e:
    print(f"Git integration not available: {e}")

# Example 3: Progress Indicators
print("\n=== Progress Indicators Demo ===")

# Create multiple test files
test_files = []
for i in range(5):
    test_file = Path(f"test_file_{i}.txt")
    test_file.write_text(f"This is test file {i}\n" * 100)
    test_files.append(test_file)

try:
    # File reading with progress
    print("Reading multiple files with progress indicator:")
    file_manager = FileContextManager(show_progress=True)
    
    # This will show a progress bar when reading multiple files
    context = file_manager.create_context_from_files(test_files)
    print(f"\nSuccessfully read {len(test_files)} files")
    print(f"Context size: {len(context)} characters")
    
finally:
    # Clean up test files
    for f in test_files:
        f.unlink(missing_ok=True)

# Example 4: Custom retry logic for your own functions
print("\n=== Custom Retry Logic Example ===")

@retry_with_backoff(max_retries=3, backoff_factor=2)
def flaky_api_call():
    """Example function that might fail randomly."""
    import random
    if random.random() < 0.7:  # 70% chance of failure
        raise ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'operation'
        )
    return "Success!"

try:
    result = flaky_api_call()
    print(f"Result: {result}")
except Exception as e:
    print(f"Failed even after retries: {e}")

print("\n✨ All new features are integrated and ready to use!")
print("Try them out in interactive mode with 'sc -i'")