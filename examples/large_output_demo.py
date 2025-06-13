#!/usr/bin/env python3
"""Example demonstrating Steve Code's support for large outputs with 128k token limit."""

from ai_code_assistant.bedrock_client import BedrockClient, ModelType, Message

# Initialize with default 128k token limit
client = BedrockClient(
    model_type=ModelType.CLAUDE_SONNET_4,
    region_name="us-east-1"
    # max_tokens defaults to 128000 (128k)
)

# Example 1: Request a large, comprehensive response
large_request = Message(
    role="user",
    content="""Create a comprehensive Python web application with the following requirements:

1. FastAPI backend with:
   - User authentication (JWT)
   - Database models using SQLAlchemy
   - RESTful API endpoints for CRUD operations
   - Input validation with Pydantic
   - Error handling and logging
   - Unit tests with pytest

2. React frontend with:
   - User registration and login forms
   - Dashboard with data visualization
   - Responsive design with Tailwind CSS
   - State management with Redux
   - API integration with Axios

3. Docker configuration for both services

4. Complete documentation including:
   - API documentation
   - Setup instructions
   - Architecture overview

Please provide complete, production-ready code for all components."""
)

print("Requesting large code generation (using 128k token limit)...")
print("=" * 80)

response_text = ""
for chunk in client.send_message([large_request], stream=True):
    response_text += chunk
    print(chunk, end="", flush=True)

print(f"\n\nTotal response length: {len(response_text)} characters")

# Example 2: Adjusting token limit for smaller responses
print("\n" + "=" * 80)
print("Example with reduced token limit for comparison:")
print("=" * 80)

# Create a client with smaller token limit
small_client = BedrockClient(
    model_type=ModelType.CLAUDE_SONNET_4,
    region_name="us-east-1",
    max_tokens=1000  # Much smaller limit
)

small_request = Message(
    role="user",
    content="Write a Python function to calculate fibonacci numbers with memoization."
)

for chunk in small_client.send_message([small_request], stream=True):
    print(chunk, end="", flush=True)

print("\n\nNote: The 128k default ensures you won't hit token limits on complex tasks!")