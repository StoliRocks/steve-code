"""Command-line interface for AI Code Assistant."""

import os
import sys
import warnings

# Suppress tkinter warnings from pyautogui before any imports
warnings.filterwarnings("ignore", message=".*tkinter.*")
warnings.filterwarnings("ignore", message=".*MouseInfo.*")
warnings.filterwarnings("ignore", category=UserWarning, module="pyautogui")
warnings.filterwarnings("ignore", message=".*You must install tkinter.*")
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # Also hide pygame prompt if used

# Redirect stderr temporarily during imports to suppress pyautogui warnings
import io
import contextlib
stderr = sys.stderr
sys.stderr = io.StringIO()

from pathlib import Path
from typing import Optional, List
import logging

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

from . import __version__
from .bedrock_client import BedrockClient, ModelType, Message
from .interactive import InteractiveMode
from .conversation import ConversationHistory
from .code_extractor import CodeExtractor
from .file_context import FileContextManager
from .config import ConfigManager
from .update_checker import UpdateChecker, get_update_message

# Restore stderr after imports
sys.stderr = stderr

print("DEBUG: CLI module loaded")  # Debug

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)

console = Console()


@click.command()
@click.option(
    '-m', '--model',
    type=click.Choice(['sonnet-4', 'sonnet-3.7', 'opus-4'], case_sensitive=False),
    default=None,
    help='Claude model to use'
)
@click.option(
    '-r', '--region',
    default=None,
    help='AWS region for Bedrock'
)
@click.option(
    '-t', '--temperature',
    type=float,
    default=None,
    help='Model temperature (0-1)'
)
@click.option(
    '--max-tokens',
    type=int,
    default=None,
    help='Maximum tokens in response'
)
@click.option(
    '-i', '--interactive',
    is_flag=True,
    help='Force interactive mode (default when no prompt given)'
)
@click.option(
    '-f', '--file',
    'files',
    multiple=True,
    type=click.Path(exists=True),
    help='Include file(s) in context'
)
@click.option(
    '-o', '--output',
    type=click.Path(),
    help='Save response to file'
)
@click.option(
    '--save-code',
    type=click.Path(),
    help='Extract and save code blocks to directory'
)
@click.option(
    '-v', '--verbose',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--version',
    is_flag=True,
    help='Show version and exit'
)
@click.option(
    '--update',
    is_flag=True,
    help='Check for updates and install if available'
)
@click.option(
    '--check-update',
    is_flag=True,
    help='Check for updates without installing'
)
@click.argument('prompt', nargs=-1)
def main(
    model: str,
    region: str,
    temperature: float,
    max_tokens: int,
    interactive: bool,
    files: tuple,
    output: Optional[str],
    save_code: Optional[str],
    verbose: bool,
    version: bool,
    update: bool,
    check_update: bool,
    prompt: tuple
):
    """Steve Code - A self-contained AI code assistant using AWS Bedrock.
    
    Examples:
        # Interactive mode (default)
        steve-code
        
        # Single prompt
        steve-code "How do I implement a binary search in Python?"
        
        # Include files in context
        steve-code -f main.py -f utils.py "Review this code"
        
        # Save code blocks
        steve-code --save-code ./output "Write a fibonacci function"
    """
    print("DEBUG: main() function called")  # Debug
    
    if version:
        console.print(f"Steve Code v{__version__}")
        return
    
    if check_update:
        console.print("Checking for updates...")
        checker = UpdateChecker()
        update_info = checker.check_for_update(force=True)
        if update_info:
            latest_version, url = update_info
            console.print(f"[green]Update available: v{latest_version}[/green]")
            console.print(f"Current version: v{__version__}")
            console.print(f"Release: {url}")
            console.print("\nTo update, run: [yellow]steve-code --update[/yellow]")
        else:
            console.print(f"[green]You're up to date! (v{__version__})[/green]")
        return
    
    if update:
        checker = UpdateChecker()
        if checker.auto_update():
            return
        else:
            # auto_update returns False if user declined or if no updates
            # Check if there actually was an update available
            update_info = checker.check_for_update(force=True)
            if update_info:
                console.print("[yellow]Update cancelled[/yellow]")
            else:
                console.print("[yellow]No updates available[/yellow]")
            return
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("DEBUG: Checking AWS credentials")  # Debug
    
    # Check AWS credentials
    if not (os.environ.get('AWS_ACCESS_KEY_ID') or os.environ.get('AWS_PROFILE')):
        console.print(
            "[red]AWS credentials not found![/red]\n\n"
            "Please configure your AWS credentials:\n"
            "  • Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
            "  • Or run 'aws configure' to set up credentials\n"
            "  • Or use IAM roles if running on EC2"
        )
        sys.exit(1)
    
    print("DEBUG: AWS credentials found")  # Debug
    
    # Load configuration
    config_manager = ConfigManager()
    config_manager.load_from_env()  # Override with env vars if present
    
    # Use command-line args or fall back to config
    if model is None:
        model = config_manager.get('model', 'sonnet-3.7')
    if region is None:
        region = config_manager.get('region', 'us-east-1')
    if temperature is None:
        temperature = config_manager.get('temperature', 0.7)
    if max_tokens is None:
        max_tokens = config_manager.get('max_tokens', 128000)
    # Always use compact mode (collect full response before display)
    compact_mode = True
    
    # Map model names
    model_map = {
        'sonnet-4': ModelType.CLAUDE_SONNET_4,
        'sonnet-3.7': ModelType.CLAUDE_3_7_SONNET,
        'opus-4': ModelType.CLAUDE_OPUS_4,
        # Legacy aliases
        'sonnet-3.5-v2': ModelType.CLAUDE_3_5_SONNET_V2,
        'sonnet-3.5': ModelType.CLAUDE_3_5_SONNET,
        'opus-3': ModelType.CLAUDE_3_OPUS,
    }
    
    try:
        # Initialize Bedrock client
        bedrock_client = BedrockClient(
            model_type=model_map[model],
            region_name=region,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Interactive mode (default when no prompt provided)
        print(f"DEBUG: interactive={interactive}, prompt={prompt}")  # Debug
        if interactive or not prompt:
            print("DEBUG: Entering interactive mode block")  # Debug
            
            # Check for updates in background (non-blocking)
            try:
                update_msg = get_update_message()
                if update_msg:
                    console.print(update_msg)
                    console.print()
            except Exception as e:
                logging.debug(f"Update check failed: {e}")
            
            # Check if we're in a terminal that supports interactive mode
            # Only exit if explicitly not a TTY and not forced with -i
            if not sys.stdin.isatty() and not interactive:
                console.print("[yellow]Warning: Not in an interactive terminal.[/yellow]")
                # Try to continue anyway since interactive is the default
            
            try:
                console.print("[dim]Starting interactive mode...[/dim]")
                interactive_mode = InteractiveMode(
                    bedrock_client=bedrock_client,
                    compact_mode=compact_mode
                )
                interactive_mode.run()
            except KeyboardInterrupt:
                console.print("\n[yellow]Exiting...[/yellow]")
                sys.exit(0)
            except EOFError:
                console.print("\n[yellow]Exiting...[/yellow]")
                sys.exit(0)
            except Exception as e:
                from rich.markup import escape
                console.print(f"[red]Error in interactive mode: {escape(str(e))}[/red]")
                import traceback
                traceback.print_exc()
                sys.exit(1)
            return
        
        # Single command mode
        prompt_text = ' '.join(prompt)
        
        # Add file context if provided
        if files:
            file_manager = FileContextManager()
            file_paths = [Path(f) for f in files]
            context = file_manager.create_context_from_files(file_paths)
            prompt_text = f"{context}\n\n{prompt_text}"
        
        # Create conversation
        conversation = ConversationHistory()
        conversation.add_message("user", prompt_text)
        
        # Get response
        messages = [Message(role="user", content=prompt_text)]
        
        response_text = ""
        
        # Get appropriate system prompt for single command mode
        system_prompt = bedrock_client.get_default_system_prompt(interactive=False)
        
        # Always collect full response for proper processing
        for chunk in bedrock_client.send_message(messages, system_prompt=system_prompt, stream=True):
            response_text += chunk
        
        console.print(response_text)
        
        # Save response to file if requested
        if output:
            output_path = Path(output)
            output_path.write_text(response_text, encoding='utf-8')
            console.print(f"\n[green]Response saved to: {output_path}[/green]")
        
        # Extract and save code blocks if requested
        if save_code:
            code_extractor = CodeExtractor()
            code_blocks = code_extractor.extract_code_blocks(response_text)
            
            if code_blocks:
                save_dir = Path(save_code)
                saved_files = code_extractor.save_code_blocks(code_blocks, save_dir)
                
                console.print(f"\n[green]Extracted {len(code_blocks)} code block(s):[/green]")
                for file in saved_files:
                    console.print(f"  • {file}")
        
        # Add to conversation history
        conversation.add_message("assistant", response_text)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(0)
    except Exception as e:
        from rich.markup import escape
        console.print(f"[red]Error: {escape(str(e))}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()