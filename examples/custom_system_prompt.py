#!/usr/bin/env python3
"""Example of using Steve Code with custom system prompts."""

from ai_code_assistant.bedrock_client import BedrockClient, ModelType, Message
from ai_code_assistant.system_prompts import get_system_prompt

# Initialize the Bedrock client
client = BedrockClient(
    model_type=ModelType.CLAUDE_SONNET_4,
    region_name="us-east-1"
)

# Example 1: Use the default system prompt for the model
default_prompt = client.get_default_system_prompt(interactive=False)
print("Default Sonnet 4 System Prompt:")
print("-" * 50)
print(default_prompt[:500] + "...")  # Show first 500 chars
print()

# Example 2: Create a specialized system prompt for a specific use case
specialized_prompt = """You are an expert Python code reviewer focusing on security best practices.
When reviewing code, you should:
1. Identify potential security vulnerabilities
2. Check for proper input validation
3. Look for SQL injection risks
4. Verify proper authentication and authorization
5. Suggest secure alternatives for any issues found

Always format your responses with clear sections:
- Security Issues Found
- Recommendations
- Secure Code Examples
"""

# Example code to review
code_to_review = '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
    
def login(username, password):
    user = db.query(f"SELECT * FROM users WHERE name = '{username}' AND pass = '{password}'")
    if user:
        return {"status": "success", "user": user}
    return {"status": "failed"}
'''

# Send message with custom system prompt
messages = [Message(
    role="user",
    content=f"Please review this Python code for security issues:\n\n```python\n{code_to_review}\n```"
)]

print("Using specialized security review prompt:")
print("-" * 50)

response_text = ""
for chunk in client.send_message(messages, system_prompt=specialized_prompt, stream=True):
    response_text += chunk
    print(chunk, end="", flush=True)

print("\n")

# Example 3: Switch models and use their specific prompts
print("Switching to Opus 4 for complex analysis:")
print("-" * 50)

client.switch_model(ModelType.CLAUDE_OPUS_4)
opus_prompt = client.get_default_system_prompt(interactive=False)

# Opus excels at complex architectural discussions
architecture_question = Message(
    role="user",
    content="Design a microservices architecture for a high-traffic e-commerce platform with real-time inventory management"
)

# The Opus prompt includes structured thinking guidance
for chunk in client.send_message([architecture_question], system_prompt=opus_prompt, stream=True):
    print(chunk, end="", flush=True)