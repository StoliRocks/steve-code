# Steve Code

A self-contained AI code assistant CLI tool that mimics Claude Code's functionality using AWS Bedrock for Claude model access.

> **Disclaimer**: This is a personal project and is not an official AWS product or service. It is not endorsed by or affiliated with Amazon Web Services.

## Features

- **Interactive Mode (Default)**: Chat-like interface with context persistence
- **Multiple Claude Models**: Support for Claude 4 Sonnet, 3.7 Sonnet, and 4 Opus
- **File Context**: Include files in your prompts for code review and analysis
- **Code Extraction**: Automatically detects and saves code blocks from responses
- **Conversation History**: Maintains context across interactions with save/load functionality
- **Command-line Interface**: Both interactive and single-command modes
- **Rich Formatting**: Syntax highlighting and markdown rendering in terminal
- **Git Integration**: View status, diffs, logs, and create commits with AI-generated messages
- **Automatic Retry Logic**: Handles transient AWS errors with exponential backoff
- **Progress Indicators**: Visual feedback during file reading and API calls
- **Dynamic File Discovery**: AI-powered file discovery based on your queries - no hardcoded patterns
- **Web Search**: Search the web for current information and documentation
- **Image/Screenshot Support**: Analyze images, screenshots, and visual content
- **Path Autocomplete**: Tab completion for file paths and commands
- **Auto-Detection**: Automatically fetches URLs and detects images in your prompts
- **Context Management**: Track token usage and auto-compact when nearing limits
- **Claude Code-style UI**: Clean collapsible output with status indicators and keyboard shortcuts
- **Auto-Update**: Check for updates and install new versions from the command line
- **Verbose Mode**: Control visibility of technical details and implementation info
- **Background Updates**: Automatic update checks every 30 minutes in interactive mode
- **Clean Output**: Technical details and file detection hidden by default for cleaner UX
- **Language Agnostic**: Works with any programming language or project structure

## Installation

### Prerequisites

- Python 3.8 or higher
- AWS account with Bedrock access
- AWS credentials configured

### Installation Options

#### Option 1: Using pipx (Recommended)
Best for installing as a standalone CLI tool:

```bash
# Install pipx if needed
sudo apt install pipx  # On Debian/Ubuntu
pipx ensurepath

# Clone and install
git clone https://github.com/StoliRocks/steve-code.git
cd steve-code
pipx install -e .

# Or with screenshot support
pipx install -e ".[screenshot]"
```

#### Option 2: Using Virtual Environment
For development or if you prefer venv isolation:

```bash
git clone https://github.com/StoliRocks/steve-code.git
cd steve-code
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .

# Create an alias for convenience (add to ~/.bashrc)
echo 'alias sc="~/projects/steve-code/venv/bin/sc"' >> ~/.bashrc
```

#### Option 3: Using UV (Modern Python Package Manager)
Fast alternative package manager:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/StoliRocks/steve-code.git
cd steve-code
uv pip install -e .
```

#### Option 4: System-wide Installation (Not Recommended)
Only if you understand the risks:

```bash
git clone https://github.com/StoliRocks/steve-code.git
cd steve-code
pip install -e . --user --break-system-packages
```

### Install from GitHub (Latest Release)

```bash
# Using pipx (recommended)
pipx install git+https://github.com/StoliRocks/steve-code.git

# With screenshot support
pipx install "steve-code[screenshot] @ git+https://github.com/StoliRocks/steve-code.git"

# Using pip with venv
python3 -m venv steve-env
source steve-env/bin/activate
pip install git+https://github.com/StoliRocks/steve-code.git
```

### Optional Dependencies

Steve Code has optional features that require additional system packages:

#### Screenshot Support (Linux)
For screenshot capture functionality on Linux, install tkinter:

```bash
# Debian/Ubuntu
sudo apt-get install python3-tk python3-dev

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

**Note**: Screenshot functionality is optional. Steve Code will work perfectly without it, and the `/screenshot` command will simply be unavailable.

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
AI_ASSISTANT_MAX_TOKENS=128000
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
   sc --model sonnet-4 --temperature 0.9
   ```

Priority order: Command-line args > Environment variables > Config file > Defaults

## Usage

### Interactive Mode (Default)

Start an interactive chat session:

```bash
steve-code

# Or use the short alias
sc

# With specific model
sc --model opus-4

# With verbose mode (show technical details)
sc --verbose
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
- `/settings` - Show current settings
- `/verbose` - Toggle verbose mode (show/hide technical details)
- `/update` - Check for and install updates
- `/set <key> <value>` - Modify settings (temperature, max_tokens, region, verbose)
- `/config` - Save current settings to config file
- `/git` - Show git status
- `/git diff` - Show unstaged changes
- `/git diff --staged` - Show staged changes
- `/git log` - Show recent commits
- `/git commit` - Create commit with AI-generated message
- `/search <query>` - Search the web for current information
- `/screenshot` - Take a screenshot for analysis
- `/image <path>` - Add image files for visual analysis

### Command-Line Options

```bash
Options:
  -m, --model [sonnet-4|sonnet-3.7|opus-4]  Claude model to use [default: sonnet-4]
  -r, --region TEXT                          AWS region for Bedrock [default: us-east-1]
  -t, --temperature FLOAT                    Model temperature (0-1) [default: 0.7]
  --max-tokens INTEGER                       Maximum tokens in response [default: 128000]
  -i, --interactive                          Start in interactive mode
  -f, --file PATH                           Include file(s) in context (multiple allowed)
  -o, --output PATH                         Save response to file
  --save-code PATH                          Extract and save code blocks to directory
  -v, --verbose                             Enable verbose logging
  --version                                 Show version and exit
  --update                                  Check for updates and install if available
  --check-update                            Check for updates without installing
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
sc
>>> Create a REST API using FastAPI for a blog system
>>> /code ./api_code  # Save generated code blocks
```

### Learning and Documentation

```bash
# Get explanations
sc "Explain how async/await works in Python with examples"

# Export conversation for documentation
sc
>>> Explain the architecture of a microservices system
>>> /export markdown architecture_notes.md
```

### File Context in Interactive Mode

```bash
sc
>>> /files src/calculator.py tests/test_calculator.py
>>> How can I improve the test coverage for my calculator module?
>>> /tree src  # View project structure
```

### Git Integration

```bash
sc
>>> /git  # Check current status
>>> /git diff  # Review changes
>>> Make the error messages more descriptive
>>> /git commit  # AI generates commit message based on changes
```

### Web Search

```bash
sc
>>> /search python async best practices
>>> How do I implement the rate limiting pattern mentioned in result 2?
```

### Visual Analysis

```bash
sc
>>> /screenshot  # Capture current screen
>>> What's wrong with this error dialog?

>>> /image mockup.png screenshot.png
>>> Create HTML/CSS to match this design
```

### Smart File Context

When you include a file, Steve Code automatically includes related files:

```bash
sc
>>> /files src/main.py  # Also includes imports, tests, and config files
>>> Review this code and its dependencies
```

### Auto-Detection

Steve Code automatically detects and processes URLs and images in your messages:

```bash
sc
>>> Explain the rate limiting in https://api.example.com/docs/rate-limits
# Automatically fetches and includes the webpage content

>>> What's wrong with this error? screenshot.png
# Automatically includes the image for visual analysis

>>> Compare design.jpg with the implementation in index.html
# Includes both the image and file automatically
```

Control auto-detection with:
```bash
>>> /set auto_detect urls    # Toggle URL fetching
>>> /set auto_detect images  # Toggle image detection
>>> /set auto_detect all     # Enable all auto-detection
>>> /set auto_detect none    # Disable all auto-detection
```

### Context Management

Steve Code automatically tracks your conversation context and helps manage token limits:

```bash
sc
>>> /status  # View current token usage
# Shows: Tokens: 15,234/128,000 (11.9% used, 112,766 remaining)

# When context usage is high, the prompt shows remaining tokens:
(45,123 tokens left) >>> 

# Auto-compact automatically summarizes old messages when reaching 80% capacity
>>> /set auto_compact off  # Disable if you prefer manual management
```

### Verbose Mode

Control how much technical detail you see:

```bash
sc
>>> /verbose  # Toggle verbose mode
# Now file detection, XML blocks, and implementation details are shown

>>> /set verbose off  # Disable verbose mode
# Clean output - technical details hidden

# Start with verbose mode enabled
sc --verbose
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
│       ├── file_context.py      # File context handling
│       ├── git_integration.py   # Git operations
│       ├── web_search.py        # Web search capability
│       ├── image_handler.py     # Image/screenshot support
│       ├── related_files.py     # File relationship analysis
│       ├── query_analyzer.py    # Query analysis and file discovery
│       ├── execution_planner.py # AI-powered execution planning
│       ├── auto_detection.py    # Auto-detect URLs/images
│       ├── context_manager.py   # Token tracking & compaction
│       ├── update_checker.py    # Version update checking
│       ├── response_processor.py # Clean AI responses for display
│       ├── collapsible_output.py # Claude Code-style UI formatting
│       └── version.py           # Version information
├── tests/                      # Unit tests
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
├── .gitignore
└── README.md
```

## Supported Models

### Current Generation
- **Claude Sonnet 4** (`sonnet-4`): Latest Sonnet model, optimized for coding tasks
- **Claude 3.7 Sonnet** (`sonnet-3.7`): Enhanced Sonnet with improved capabilities
- **Claude Opus 4** (`opus-4`): Most powerful model for complex tasks

### Legacy Models
- **Claude 3.5 Sonnet v2** (`sonnet-3.5-v2`): Previous Sonnet version
- **Claude 3.5 Sonnet** (`sonnet-3.5`): Earlier Sonnet release
- **Claude 3 Opus** (`opus-3`): Previous Opus generation

All models use AWS Bedrock's load-balanced endpoints with the `.us.` prefix for optimal performance across regions.

### Token Limits

Steve Code defaults to 128,000 tokens (128k) for maximum response length, which is supported by all current Claude models. This generous limit ensures complete responses for complex tasks like:
- Large code generation projects
- Comprehensive code reviews
- Detailed architectural documentation
- Multi-file refactoring explanations

You can adjust the token limit using `--max-tokens` or by setting it in interactive mode with `/set max_tokens <value>`.

## Troubleshooting

### Installation Issues

If you encounter "externally-managed-environment" error on modern Linux systems:
- This is a protection mechanism to prevent breaking system Python
- Use one of the installation methods above (pipx recommended)
- See [PEP 668](https://peps.python.org/pep-0668/) for more details

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

## Updating

Steve Code can check for and install updates automatically:

```bash
# Check if updates are available
sc --check-update

# Update to the latest version
sc --update

# In interactive mode
>>> /update  # Check and install updates immediately
```

Updates are checked automatically:
- On startup when entering interactive mode
- Every 30 minutes while running in interactive mode
- The tool will notify you non-intrusively when a new version is available

Updates install to your Python environment (site-packages), not your working directory.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with AWS Bedrock for Claude model access
- Inspired by Claude Code's functionality
- Uses Rich for beautiful terminal formatting
- Uses Click for robust CLI handling