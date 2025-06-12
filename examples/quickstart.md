# Steve Code - Quick Start Guide

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/steve-code.git
cd steve-code

# Install the package
pip install -e .

# Or just install dependencies
pip install -r requirements.txt
```

## First Time Setup

1. **Configure AWS Credentials**

   ```bash
   # Option 1: Use AWS CLI
   aws configure
   
   # Option 2: Set environment variables
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **Verify Bedrock Access**
   
   Ensure your AWS account has access to Amazon Bedrock and the Claude models are enabled in your region.

## Quick Examples

### 1. Interactive Chat

Start an interactive session:

```bash
steve-code -i
```

In interactive mode:
```
>>> How do I sort a list in Python?
>>> /files my_code.py    # Add file to context
>>> Can you review this code?
>>> /exit
```

### 2. One-Time Query

Get a quick answer:

```bash
steve-code "What is a decorator in Python?"
```

### 3. Code Review

Review code files:

```bash
steve-code -f app.py -f tests.py "Review my Flask app for best practices"
```

### 4. Generate Code

Generate and save code:

```bash
steve-code --save-code ./output "Create a Python script that downloads files from URLs"
```

### 5. Export Conversation

In interactive mode:
```
>>> Explain microservices architecture
>>> What are the main patterns?
>>> /export markdown notes.md
```

## Common Workflows

### Debugging Help

```bash
# Include error output
steve-code -f error.log -f app.py "Help me debug this error"
```

### Learning New Concepts

```bash
# Interactive learning session
steve-code -i --model opus-4
>>> Explain React hooks step by step
>>> Show me a practical example
>>> /code examples/  # Save code examples
```

### Code Generation

```bash
# Generate with specific requirements
steve-code --save-code ./src "Create a REST API for a todo app using FastAPI with SQLAlchemy"
```

### Documentation

```bash
# Generate documentation
steve-code -f src/*.py "Generate API documentation for these modules" -o API_DOCS.md
```

## Tips

1. **Use `/help` in interactive mode** to see all available commands
2. **Include multiple files** with `-f` for better context
3. **Use `--model opus-4`** for complex tasks
4. **Save conversations** with `/save` for future reference
5. **Extract code** with `--save-code` or `/code` command

## Troubleshooting

If you encounter issues:

1. Check AWS credentials: `aws sts get-caller-identity`
2. Verify Bedrock access in AWS console
3. Use `-v` flag for verbose output
4. Check the `~/.steve_code/history/` for saved sessions

## Next Steps

- Explore more examples in the `examples/` directory
- Read the full README for advanced features
- Customize settings in your `.env` file