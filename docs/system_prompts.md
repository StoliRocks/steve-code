# System Prompts in Steve Code

Steve Code uses model-specific system prompts to optimize the behavior of each Claude model for coding assistance. These prompts are automatically applied based on the model you're using and whether you're in interactive mode.

## Default System Prompts

### Base Prompt (All Models)
All models share a base system prompt that:
- Defines the role as an expert coding assistant
- Sets formatting guidelines for code blocks
- Establishes behavioral guidelines for helpful responses
- Includes code safety recommendations
- Provides current date context

### Model-Specific Enhancements

#### Claude Sonnet 4 (Default)
- Optimized for rapid code generation and refactoring
- Focuses on practical, immediately useful solutions
- Balanced depth and speed in responses

#### Claude 3.7 Sonnet
- Enhanced Sonnet with improved capabilities
- Reliable code generation with well-tested approaches
- Clear, straightforward explanations

#### Claude Opus 4
- Enhanced for complex architectural design
- Deep technical explanations with structured thinking
- Multiple perspective analysis
- Uses XML tags for organizing complex responses
- Best for challenging problems requiring nuanced solutions

### Legacy Models
Legacy models (Claude 3.5 Sonnet v2, Claude 3.5 Sonnet, Claude 3 Opus) use prompts from their newer counterparts to ensure consistent behavior.

### Interactive Mode
When using interactive mode (`sc -i`), additional context is added:
- Awareness of conversation history
- Understanding of file context commands
- Adaptation to task switching

## Using Custom System Prompts

While Steve Code provides optimized defaults, you can use custom system prompts for specialized use cases:

```python
from ai_code_assistant.bedrock_client import BedrockClient, ModelType, Message

# Initialize client
client = BedrockClient(model_type=ModelType.CLAUDE_SONNET_4)

# Create a specialized prompt
security_prompt = """You are a security-focused code reviewer.
Focus on identifying vulnerabilities and suggesting secure alternatives."""

# Use with send_message
messages = [Message(role="user", content="Review this code...")]
response = client.send_message(messages, system_prompt=security_prompt)
```

## System Prompt Updates

The system prompts are:
- Automatically selected based on your chosen model
- Updated when switching models in interactive mode
- Designed to leverage each model's strengths
- Periodically refined based on usage patterns

## Best Practices

1. **Use Default Prompts**: The default prompts are optimized for general coding assistance
2. **Model Selection**: Choose Opus for complex architectural tasks, Sonnet for general coding
3. **Custom Prompts**: Create specialized prompts only for specific domain expertise
4. **Interactive Mode**: Leverages conversation context automatically

## Implementation Details

System prompts are defined in `src/ai_code_assistant/system_prompts.py` and include:
- Dynamic date injection
- Model-specific capabilities
- Structured response formatting
- Safety guidelines

The prompts follow Anthropic's best practices including:
- Clear role definition
- Specific behavioral guidelines
- Format specifications
- XML tag structuring for complex tasks