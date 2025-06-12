# Steve Code

A self-contained AI code assistant CLI tool that mimics Claude Code's functionality using AWS Bedrock for Claude model access.

## Features

- **Interactive Mode**: Chat-like interface with context persistence
- **Multiple Claude Models**: Support for Claude 4 Sonnet, 3.7 Sonnet, and 4 Opus
- **File Context**: Include files in your prompts for code review and analysis
- **Code Extraction**: Automatically detects and saves code blocks from responses
- **Conversation History**: Maintains context across interactions with save/load functionality
- **Command-line Interface**: Both interactive and single-command modes
- **Rich Formatting**: Syntax highlighting and markdown rendering in terminal

## Installation

### Prerequisites

- Python 3.8 or higher
- AWS account with Bedrock access
- AWS credentials configured

### Install from source

```bash
git clone https://github.com/yourusername/steve-code.git
cd steve-code
pip install -e .
```

### Install dependencies only

```bash
pip install -r requirements.txt
```

## Configuration

### AWS Credentials

The tool requires AWS credentials with access to Amazon Bedrock. Configure your credentials using one of these methods:

1. **Environment variables**:
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **AWS CLI configuration**:
   ```bash
   aws configure
   ```

3. **IAM roles** (when running on EC2)

### Environment Variables

Create a `.env` file in your project directory (optional):

```bash
AWS_DEFAULT_REGION=us-east-1
AI_ASSISTANT_MODEL=sonnet-4
AI_ASSISTANT_TEMPERATURE=0.7
AI_ASSISTANT_MAX_TOKENS=4096
AI_ASSISTANT_COMPACT_MODE=false
```

### Configuration Management

The assistant supports persistent configuration through multiple methods:

1. **Configuration File**: Settings are automatically saved to `~/.steve_code/config.json`
   ```bash
   # In interactive mode
   >>> /set temperature 0.8
   >>> /set max_tokens 8192
   >>> /config  # Save settings to config file
   ```

2. **Environment Variables**: Override config file settings
   ```bash
   export AI_ASSISTANT_MODEL=opus-4
   export AI_ASSISTANT_TEMPERATURE=0.5
   ```

3. **Command-line Arguments**: Override all other settings
   ```bash
   sc -i --model sonnet-4 --temperature 0.9
   ```

Priority order: Command-line args > Environment variables > Config file > Defaults

## Usage

### Interactive Mode

Start an interactive chat session:

```bash
steve-code -i

# Or use the short alias
sc -i

# With specific model
sc -i --model opus-4

# With compact mode
sc -i --compact
```

### Single Command Mode

Get a one-time response:

```bash
# Simple prompt
sc "How do I implement a binary search in Python?"

# Include files for context
sc -f main.py -f utils.py "Review this code for potential improvements"

# Save response to file
sc -o response.md "Explain the SOLID principles"

# Extract and save code blocks
sc --save-code ./output "Write a Python function to calculate fibonacci numbers"
```

### Interactive Commands

When in interactive mode, you can use these commands:

- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/exit` or `/quit` - Exit the assistant
- `/save [filename]` - Save current conversation
- `/load <filename>` - Load a previous conversation
- `/files <path1> [path2...]` - Add files to context
- `/status` - Show current status
- `/model <model-name>` - Switch model (sonnet-4, sonnet-3.7, opus-4)
- `/export <format> <filename>` - Export conversation (json/markdown)
- `/code [directory]` - Extract and save code blocks from last response
- `/tree [path]` - Show directory tree
- `/compact` - Toggle compact display mode
- `/settings` - Show current settings
- `/set <key> <value>` - Modify settings (temperature, max_tokens, region)
- `/config` - Save current settings to config file

### Command-Line Options

```bash
Options:
  -m, --model [sonnet-4|sonnet-3.7|opus-4]  Claude model to use [default: sonnet-4]
  -r, --region TEXT                          AWS region for Bedrock [default: us-east-1]
  -t, --temperature FLOAT                    Model temperature (0-1) [default: 0.7]
  --max-tokens INTEGER                       Maximum tokens in response [default: 4096]
  -i, --interactive                          Start in interactive mode
  -f, --file PATH                           Include file(s) in context (multiple allowed)
  -c, --compact                             Use compact output mode
  -o, --output PATH                         Save response to file
  --save-code PATH                          Extract and save code blocks to directory
  --no-stream                               Disable response streaming
  -v, --verbose                             Enable verbose logging
  --version                                 Show version and exit
  --help                                    Show this message and exit
```

## Examples

### Code Review

```bash
# Review a Python file
sc -f app.py "Review this Flask application for security issues and best practices"

# Review multiple files
sc -f src/main.py -f src/utils.py -f tests/test_main.py "Are my tests comprehensive?"
```

### Code Generation

```bash
# Generate code with automatic extraction
sc --save-code ./generated "Create a Python class for managing a todo list with SQLite"

# Interactive coding session
sc -i
>>> Create a REST API using FastAPI for a blog system
>>> /code ./api_code  # Save generated code blocks
```

### Learning and Documentation

```bash
# Get explanations
sc "Explain how async/await works in Python with examples"

# Export conversation for documentation
sc -i
>>> Explain the architecture of a microservices system
>>> /export markdown architecture_notes.md
```

### File Context in Interactive Mode

```bash
sc -i
>>> /files src/calculator.py tests/test_calculator.py
>>> How can I improve the test coverage for my calculator module?
>>> /tree src  # View project structure
```

## Project Structure

```
steve-code/
├── src/
│   └── ai_code_assistant/
│       ├── __init__.py
│       ├── bedrock_client.py    # AWS Bedrock integration
│       ├── cli.py               # Command-line interface
│       ├── interactive.py       # Interactive mode
│       ├── conversation.py      # Conversation history management
│       ├── code_extractor.py    # Code block extraction
│       └── file_context.py      # File context handling
├── examples/                    # Example scripts and usage
├── tests/                      # Unit tests
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
├── .gitignore
└── README.md
```

## Supported Models

- **Claude 4 Sonnet** (`sonnet-4`): Latest and most capable model
- **Claude 3.7 Sonnet** (`sonnet-3.7`): Previous generation Sonnet
- **Claude 4 Opus** (`opus-4`): Most powerful model for complex tasks

## Troubleshooting

### AWS Credentials Error

If you see "AWS credentials not found", ensure you have:
1. Set up AWS credentials using `aws configure`
2. Or exported AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
3. Or are running on an EC2 instance with appropriate IAM role

### Model Access Error

If you see "Access denied to model", ensure:
1. Your AWS account has access to Amazon Bedrock
2. The requested model is enabled in your Bedrock console
3. You're using the correct AWS region

### File Encoding Issues

If you encounter encoding errors with files:
1. Ensure files are saved in UTF-8 encoding
2. The tool attempts multiple encodings automatically
3. Binary files are automatically excluded

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with AWS Bedrock for Claude model access
- Inspired by Claude Code's functionality
- Uses Rich for beautiful terminal formatting
- Uses Click for robust CLI handling