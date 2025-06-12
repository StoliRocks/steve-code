"""Command-line interface for AI Code Assistant."""

import os
import sys
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
    help='Start in interactive mode'
)
@click.option(
    '-f', '--file',
    'files',
    multiple=True,
    type=click.Path(exists=True),
    help='Include file(s) in context'
)
@click.option(
    '-c', '--compact',
    is_flag=True,
    help='Use compact output mode'
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
    '--no-stream',
    is_flag=True,
    help='Disable response streaming'
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
@click.argument('prompt', nargs=-1)
def main(
    model: str,
    region: str,
    temperature: float,
    max_tokens: int,
    interactive: bool,
    files: tuple,
    compact: bool,
    output: Optional[str],
    save_code: Optional[str],
    no_stream: bool,
    verbose: bool,
    version: bool,
    prompt: tuple
):
    """Steve Code - A self-contained AI code assistant using AWS Bedrock.
    
    Examples:
        # Interactive mode
        steve-code -i
        
        # Single prompt
        steve-code "How do I implement a binary search in Python?"
        
        # Include files in context
        steve-code -f main.py -f utils.py "Review this code"
        
        # Save code blocks
        steve-code --save-code ./output "Write a fibonacci function"
    """
    if version:
        console.print(f"Steve Code v{__version__}")
        return
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
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
    
    # Load configuration
    config_manager = ConfigManager()
    config_manager.load_from_env()  # Override with env vars if present
    
    # Use command-line args or fall back to config
    if model is None:
        model = config_manager.get('model', 'sonnet-4')
    if region is None:
        region = config_manager.get('region', 'us-east-1')
    if temperature is None:
        temperature = config_manager.get('temperature', 0.7)
    if max_tokens is None:
        max_tokens = config_manager.get('max_tokens', 4096)
    if not compact:
        compact = config_manager.get('compact_mode', False)
    
    # Map model names
    model_map = {
        'sonnet-4': ModelType.CLAUDE_4_SONNET,
        'sonnet-3.7': ModelType.CLAUDE_3_7_SONNET,
        'opus-4': ModelType.CLAUDE_4_OPUS,
    }
    
    try:
        # Initialize Bedrock client
        bedrock_client = BedrockClient(
            model_type=model_map[model],
            region_name=region,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Interactive mode
        if interactive or not prompt:
            interactive_mode = InteractiveMode(
                bedrock_client=bedrock_client,
                compact_mode=compact
            )
            interactive_mode.run()
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
        
        if no_stream:
            # Non-streaming response
            response = bedrock_client.send_message(messages, stream=False)
            response_text = response.get('content', [{}])[0].get('text', '')
            console.print(response_text)
        else:
            # Streaming response
            for chunk in bedrock_client.send_message(messages, stream=True):
                response_text += chunk
                if not compact:
                    console.print(chunk, end="")
            
            if compact:
                console.print(response_text)
            else:
                console.print()  # New line after streaming
        
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
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()