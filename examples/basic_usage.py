#!/usr/bin/env python3
"""Basic usage examples for Steve Code."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_code_assistant.bedrock_client import BedrockClient, ModelType, Message
from ai_code_assistant.conversation import ConversationHistory
from ai_code_assistant.code_extractor import CodeExtractor
from ai_code_assistant.file_context import FileContextManager


def example_basic_chat():
    """Example: Basic chat interaction."""
    print("=== Basic Chat Example ===\n")
    
    # Initialize client
    client = BedrockClient(
        model_type=ModelType.CLAUDE_4_SONNET,
        region_name="us-east-1"
    )
    
    # Create a simple message
    messages = [
        Message(role="user", content="Write a Python function to calculate factorial")
    ]
    
    # Get response
    print("User: Write a Python function to calculate factorial\n")
    print("Assistant: ", end="", flush=True)
    
    response_text = ""
    for chunk in client.send_message(messages):
        print(chunk, end="", flush=True)
        response_text += chunk
    
    print("\n")
    return response_text


def example_code_extraction():
    """Example: Extract code blocks from response."""
    print("=== Code Extraction Example ===\n")
    
    # Sample response with code blocks
    response = """Here's a Python function to calculate factorial:

```python
def factorial(n):
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    elif n == 0 or n == 1:
        return 1
    else:
        return n * factorial(n - 1)
```

And here's an iterative version:

```python
def factorial_iterative(n):
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    
    result = 1
    for i in range(2, n + 1):
        result *= i
    
    return result
```

Both functions will give you the same result!"""
    
    # Extract code blocks
    extractor = CodeExtractor()
    code_blocks = extractor.extract_code_blocks(response)
    
    print(f"Found {len(code_blocks)} code blocks:\n")
    
    for i, block in enumerate(code_blocks, 1):
        print(f"Block {i} ({block.language}):")
        print("-" * 40)
        print(block.content)
        print("-" * 40)
        print()
    
    # Save code blocks
    output_dir = Path("./extracted_code")
    saved_files = extractor.save_code_blocks(code_blocks, output_dir)
    
    print(f"Saved {len(saved_files)} files:")
    for file in saved_files:
        print(f"  - {file}")


def example_file_context():
    """Example: Include files in context."""
    print("\n=== File Context Example ===\n")
    
    # Create a sample file
    sample_file = Path("sample_code.py")
    sample_file.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""")
    
    # Initialize file manager
    file_manager = FileContextManager()
    
    # Read file
    content = file_manager.read_file(sample_file)
    if content:
        print(f"Read file: {sample_file}")
        print(file_manager.format_file_content(sample_file, content))
    
    # Clean up
    sample_file.unlink()


def example_conversation_history():
    """Example: Manage conversation history."""
    print("\n=== Conversation History Example ===\n")
    
    # Initialize conversation
    conversation = ConversationHistory()
    
    # Add messages
    conversation.add_message("user", "What is Python?")
    conversation.add_message("assistant", "Python is a high-level, interpreted programming language...")
    conversation.add_message("user", "What are its main features?")
    conversation.add_message("assistant", "Python's main features include:\n1. Simple syntax\n2. Dynamic typing\n3. Extensive libraries")
    
    # Display conversation
    print("Conversation history:")
    for i, msg in enumerate(conversation.get_messages(), 1):
        print(f"\n{i}. {msg.role.title()}:")
        print(f"   {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
    
    # Export conversation
    export_path = Path("conversation_example.json")
    conversation.export_session(export_path, format="json")
    print(f"\nExported conversation to: {export_path}")
    
    # Clean up
    export_path.unlink()


def example_model_switching():
    """Example: Switch between different models."""
    print("\n=== Model Switching Example ===\n")
    
    # Initialize with one model
    client = BedrockClient(model_type=ModelType.CLAUDE_4_SONNET)
    print(f"Current model: {client.model_type.name}")
    
    # Switch to another model
    client.switch_model(ModelType.CLAUDE_3_7_SONNET)
    print(f"Switched to: {client.model_type.name}")
    
    # Switch to Opus
    client.switch_model(ModelType.CLAUDE_4_OPUS)
    print(f"Switched to: {client.model_type.name}")


if __name__ == "__main__":
    try:
        # Run examples
        print("Steve Code - Examples\n")
        
        # Note: Comment out examples that require AWS credentials if not configured
        
        # Example 1: Basic chat (requires AWS credentials)
        # response = example_basic_chat()
        
        # Example 2: Code extraction (no AWS needed)
        example_code_extraction()
        
        # Example 3: File context (no AWS needed)
        example_file_context()
        
        # Example 4: Conversation history (no AWS needed)
        example_conversation_history()
        
        # Example 5: Model switching (no AWS needed for demo)
        example_model_switching()
        
    except Exception as e:
        print(f"\nError: {e}")
        
    print("\nExamples completed!")