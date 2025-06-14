"""Interactive mode for the AI Code Assistant."""

import sys
import os
import subprocess
import logging
import time
import random
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from .bedrock_client import BedrockClient, ModelType, Message
from .conversation import ConversationHistory
from .code_extractor import CodeExtractor
from .file_context import FileContextManager
from .config import ConfigManager
from .git_integration import GitIntegration, GitStatus
from .web_search import WebSearcher, SmartWebSearch
from .image_handler import ImageHandler, ScreenshotCapture
from .command_completer import CommandCompleter
from .auto_detection import AutoDetector
from .context_manager import ContextManager, ContextStats
from .smart_context_v2 import SmartContextV2

logger = logging.getLogger(__name__)


class InteractiveMode:
    """Interactive chat mode for the AI assistant."""
    
    # Fun verbs for different query types
    FUN_VERBS = {
        'debug': ['🐛 Debugging', '🔍 Investigating', '🕵️ Sleuthing', '🔬 Analyzing'],
        'implement': ['🔨 Building', '🏗️ Constructing', '⚡ Creating', '🎨 Crafting'],
        'test': ['🧪 Testing', '🔧 Verifying', '✅ Checking', '🎯 Validating'],
        'refactor': ['♻️ Refactoring', '🛠️ Improving', '✨ Polishing', '🔄 Restructuring'],
        'explain': ['📚 Explaining', '🎓 Teaching', '💡 Illuminating', '🗣️ Clarifying'],
        'review': ['👀 Reviewing', '📋 Examining', '🔎 Inspecting', '📝 Evaluating'],
        'general': ['🤔 Thinking', '💭 Pondering', '🧠 Processing', '⚙️ Computing'],
    }
    
    # Interactive commands
    COMMANDS = {
        '/help': 'Show this help message',
        '/clear': 'Clear conversation history',
        '/exit': 'Exit the assistant',
        '/quit': 'Exit the assistant',
        '/save': 'Save the current conversation',
        '/load': 'Load a previous conversation',
        '/files': 'Add files to context',
        '/status': 'Show current status',
        '/model': 'Switch model (sonnet-4, sonnet-3.7, opus-4)',
        '/export': 'Export conversation (json/markdown)',
        '/project': 'Show project analysis',
        '/autodiscover': 'Toggle automatic file discovery',
        '/bash': 'Execute bash command (use /bash <command>)',
        '/!': 'Shortcut for bash command (use /! <command>)',
        '/run': 'Run the last code block or command from assistant response',
        '/code': 'Extract and save code blocks',
        '/tree': 'Show directory tree',
        '/todo': 'Show task list extracted from conversation',
        '/compact': 'Toggle compact mode',
        '/settings': 'Show or modify settings (use /settings <key> <value>)',
        '/set': 'Set a configuration value (temperature, max_tokens, region, auto_detect)',
        '/config': 'Save current settings to config file',
        '/git': 'Show git status',
        '/git diff': 'Show git diff of unstaged changes',
        '/git diff --staged': 'Show git diff of staged changes',
        '/git log': 'Show recent git commits',
        '/git commit': 'Create a git commit with AI-generated message',
        '/search': 'Search the web for current information',
        '/screenshot': 'Take a screenshot for analysis',
        '/image': 'Add image files for analysis',
    }
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        history_dir: Optional[Path] = None,
        compact_mode: bool = False
    ):
        """Initialize interactive mode.
        
        Args:
            bedrock_client: Bedrock client instance
            history_dir: Directory for conversation history
            compact_mode: Whether to use compact display mode
        """
        self.bedrock_client = bedrock_client
        self.conversation = ConversationHistory(history_dir)
        self.code_extractor = CodeExtractor()
        self.file_manager = FileContextManager()
        self.console = Console()
        self.compact_mode = compact_mode
        self.config_manager = ConfigManager()
        
        # File context
        self.context_files: List[Path] = []
        
        # Prompt session with history and completion
        history_file = Path.home() / ".steve_code" / "prompt_history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create custom completer
        self.completer = CommandCompleter(self.COMMANDS)
        
        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            style=self._create_prompt_style(),
            completer=self.completer,
            complete_while_typing=True
        )
        
        # System prompt - use model-specific prompt for interactive mode
        self.system_prompt = self.bedrock_client.get_default_system_prompt(interactive=True)
        
        # Initialize git integration (may fail if not in git repo)
        try:
            self.git = GitIntegration()
        except RuntimeError:
            self.git = None
            self.console.print("[yellow]Note: Not in a git repository. Git commands unavailable.[/yellow]")
        
        # Initialize web search
        self.web_searcher = WebSearcher()
        self.smart_search = SmartWebSearch(self.web_searcher, self.bedrock_client)
        
        # Initialize image handling
        self.image_handler = ImageHandler()
        self.screenshot_capture = ScreenshotCapture()
        self.context_images: List[Path] = []  # Images to include in context
        
        # Initialize auto-detection
        self.auto_detector = AutoDetector(
            auto_fetch_urls=True,
            auto_detect_images=True,
            auto_detect_files=False  # Can be enabled via settings
        )
        
        # Initialize context manager
        self.context_manager = ContextManager(
            max_tokens=self.bedrock_client.max_tokens,
            compact_threshold=0.8,  # Auto-compact at 80%
            warning_threshold=0.7   # Warn at 70%
        )
        self.auto_compact_enabled = True
        
        # Initialize smart context v2 for automatic file discovery
        try:
            self.smart_context = SmartContextV2()
            self.auto_discover_files = True  # Enable by default
        except Exception as e:
            logger.warning(f"Failed to initialize smart context: {e}")
            self.smart_context = None
            self.auto_discover_files = False
    
    def _create_prompt_style(self) -> Style:
        """Create prompt style."""
        return Style.from_dict({
            'prompt': '#00aa00 bold',
        })
    
    def run(self):
        """Run the interactive mode."""
        try:
            self._show_welcome()
        except Exception as e:
            self.console.print(f"[red]Error showing welcome: {e}[/red]")
            logger.error(f"Welcome screen error: {e}", exc_info=True)
        
        while True:
            try:
                # Get context info for prompt
                messages = self._prepare_api_messages()
                stats = self.context_manager.get_context_stats(messages)
                
                # Build context status line
                context_percent = 100 - stats.usage_percentage
                context_color = "green" if context_percent > 30 else "yellow" if context_percent > 20 else "red"
                context_status = f"[{context_color}]Context: {context_percent}% available[/{context_color}]"
                
                # Show context status if getting full
                if stats.usage_percentage >= 50:
                    self.console.print(f"\n{context_status} (auto-compact at 20%)")
                
                # Build prompt
                prompt_text = "\n>>> "
                
                # Get user input
                user_input = self.session.prompt(
                    prompt_text,
                    multiline=False,
                    style=self._create_prompt_style()
                )
                
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    if not self._handle_command(user_input):
                        break
                    continue
                
                # Process regular message
                self._process_message(user_input)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /exit to quit[/yellow]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
    
    def _show_welcome(self):
        """Show welcome message."""
        welcome = Panel(
            Text.from_markup(
                "[bold blue]Steve Code[/bold blue]\n\n"
                "Interactive mode with AWS Bedrock\n"
                f"Model: [green]{self.bedrock_client.model_type.name}[/green]\n\n"
                "Type [yellow]/help[/yellow] for available commands\n"
                "Type [yellow]/exit[/yellow] to quit"
            ),
            title="Welcome",
            border_style="blue"
        )
        self.console.print(welcome)
    
    def _handle_command(self, command: str) -> bool:
        """Handle interactive commands.
        
        Args:
            command: Command string
            
        Returns:
            True to continue, False to exit
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in ['/exit', '/quit']:
            self.console.print("[yellow]Goodbye![/yellow]")
            return False
        
        elif cmd == '/help':
            self._show_help()
        
        elif cmd == '/clear':
            self.conversation.clear()
            self.console.print("[green]Conversation cleared[/green]")
        
        elif cmd == '/status':
            self._show_status()
        
        elif cmd == '/settings':
            if args:
                self._modify_settings(args)
            else:
                self._show_settings()
        
        elif cmd == '/set':
            if args:
                self._modify_settings(args)
            else:
                self.console.print("[yellow]Usage: /set <key> <value>[/yellow]")
                self.console.print("[yellow]Keys: temperature, max_tokens, region[/yellow]")
        
        elif cmd == '/compact':
            self.compact_mode = not self.compact_mode
            mode = "enabled" if self.compact_mode else "disabled"
            self.console.print(f"[green]Compact mode {mode}[/green]")
        
        elif cmd == '/model':
            self._switch_model(args)
        
        elif cmd == '/files':
            self._add_files(args)
        
        elif cmd == '/tree':
            self._show_tree(args)
        
        elif cmd == '/save':
            self._save_conversation(args)
        
        elif cmd == '/load':
            self._load_conversation(args)
        
        elif cmd == '/export':
            self._export_conversation(args)
        
        elif cmd == '/code':
            self._extract_code(args)
        
        elif cmd == '/config':
            self._save_config()
        
        elif cmd.startswith('/git'):
            self._handle_git_command(user_input)
        
        elif cmd == '/search':
            self._handle_search(args)
        
        elif cmd == '/screenshot':
            self._handle_screenshot()
        
        elif cmd == '/image':
            self._add_images(args)
        
        elif cmd == '/project':
            self._show_project_info()
        
        elif cmd == '/autodiscover':
            self._toggle_autodiscover()
        
        elif cmd == '/bash' or cmd == '/!':
            self._execute_bash(args)
        
        elif cmd == '/run':
            self._run_last_command()
        
        elif cmd == '/todo':
            self._show_todos()
        
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("Type /help for available commands")
        
        return True
    
    def _show_help(self):
        """Show help message."""
        help_text = "[bold]Available Commands:[/bold]\n\n"
        for cmd, desc in self.COMMANDS.items():
            help_text += f"  [cyan]{cmd:<12}[/cyan] {desc}\n"
        
        self.console.print(Panel(help_text, title="Help", border_style="blue"))
    
    def _show_status(self):
        """Show current status."""
        # Get context statistics
        messages = self._prepare_api_messages()
        stats = self.context_manager.get_context_stats(messages)
        
        # Determine context color based on usage
        if stats.usage_percentage >= 80:
            context_color = "red"
        elif stats.usage_percentage >= 70:
            context_color = "yellow"
        else:
            context_color = "green"
        
        status = f"""[bold]Current Status:[/bold]

Model: [green]{self.bedrock_client.model_type.name}[/green]
Messages: [yellow]{len(self.conversation.messages)}[/yellow]
Context Files: [yellow]{len(self.context_files)}[/yellow]
Context Images: [yellow]{len(self.context_images)}[/yellow]
Compact Mode: [yellow]{'On' if self.compact_mode else 'Off'}[/yellow]

[bold]Context Usage:[/bold]
Tokens: [{context_color}]{stats.formatted_status}[/{context_color}]
{self.context_manager.get_auto_compact_status(self.auto_compact_enabled, stats)}

Session ID: [dim]{self.conversation.session_id}[/dim]"""
        
        if self.context_files:
            status += "\n\n[bold]Context Files:[/bold]"
            for file in self.context_files:
                status += f"\n  • {file}"
        
        if self.context_images:
            status += "\n\n[bold]Context Images:[/bold]"
            for img in self.context_images:
                status += f"\n  • {img.name}"
        
        self.console.print(Panel(status, title="Status", border_style="blue"))
    
    def _show_settings(self):
        """Show current settings."""
        settings = f"""[bold]Current Settings:[/bold]

Model: [green]{self.bedrock_client.model_type.value}[/green]
Region: [yellow]{self.bedrock_client.region_name}[/yellow]
Max Tokens: [yellow]{self.bedrock_client.max_tokens}[/yellow]
Temperature: [yellow]{self.bedrock_client.temperature}[/yellow]
Compact Mode: [yellow]{'Enabled' if self.compact_mode else 'Disabled'}[/yellow]
Auto-detect URLs: [yellow]{'Enabled' if self.auto_detector.auto_fetch_urls else 'Disabled'}[/yellow]
Auto-detect Images: [yellow]{'Enabled' if self.auto_detector.auto_detect_images else 'Disabled'}[/yellow]
Auto-detect Files: [yellow]{'Enabled' if self.auto_detector.auto_detect_files else 'Disabled'}[/yellow]
Auto-discover Files: [yellow]{'Enabled' if self.auto_discover_files else 'Disabled'}[/yellow]
Auto-compact: [yellow]{'Enabled' if self.auto_compact_enabled else 'Disabled'}[/yellow]

[dim]History: {self.conversation.history_dir}[/dim]

[dim]Use /set <key> <value> to modify settings[/dim]"""
        
        self.console.print(Panel(settings, title="Settings", border_style="blue"))
    
    def _modify_settings(self, args: str):
        """Modify runtime settings."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            self.console.print("[yellow]Usage: /set <key> <value>[/yellow]")
            self.console.print("[yellow]Available keys:[/yellow]")
            self.console.print("  • temperature (0.0-1.0)")
            self.console.print("  • max_tokens (1-100000)")
            self.console.print("  • region (aws region name)")
            return
        
        key = parts[0].lower()
        value = parts[1]
        
        try:
            if key == "temperature":
                temp = float(value)
                if 0.0 <= temp <= 1.0:
                    self.bedrock_client.temperature = temp
                    self.console.print(f"[green]Temperature set to {temp}[/green]")
                else:
                    self.console.print("[red]Temperature must be between 0.0 and 1.0[/red]")
            
            elif key == "max_tokens":
                tokens = int(value)
                if 1 <= tokens <= 128000:
                    self.bedrock_client.max_tokens = tokens
                    self.console.print(f"[green]Max tokens set to {tokens}[/green]")
                else:
                    self.console.print("[red]Max tokens must be between 1 and 128000[/red]")
            
            elif key == "region":
                # Update the bedrock client's region
                self.bedrock_client.region_name = value
                # Recreate the boto3 client with new region
                import boto3
                self.bedrock_client.client = boto3.client(
                    service_name='bedrock-runtime',
                    region_name=value
                )
                self.console.print(f"[green]Region set to {value}[/green]")
            
            elif key == "auto_detect":
                # Parse auto-detection settings
                if value.lower() in ['urls', 'url']:
                    self.auto_detector.auto_fetch_urls = not self.auto_detector.auto_fetch_urls
                    self.console.print(f"[green]URL auto-detection {'enabled' if self.auto_detector.auto_fetch_urls else 'disabled'}[/green]")
                elif value.lower() in ['images', 'image']:
                    self.auto_detector.auto_detect_images = not self.auto_detector.auto_detect_images
                    self.console.print(f"[green]Image auto-detection {'enabled' if self.auto_detector.auto_detect_images else 'disabled'}[/green]")
                elif value.lower() in ['files', 'file']:
                    self.auto_detector.auto_detect_files = not self.auto_detector.auto_detect_files
                    self.console.print(f"[green]File auto-detection {'enabled' if self.auto_detector.auto_detect_files else 'disabled'}[/green]")
                elif value.lower() in ['all', 'on']:
                    self.auto_detector.auto_fetch_urls = True
                    self.auto_detector.auto_detect_images = True
                    self.auto_detector.auto_detect_files = True
                    self.console.print("[green]All auto-detection enabled[/green]")
                elif value.lower() in ['none', 'off']:
                    self.auto_detector.auto_fetch_urls = False
                    self.auto_detector.auto_detect_images = False
                    self.auto_detector.auto_detect_files = False
                    self.console.print("[green]All auto-detection disabled[/green]")
                else:
                    self.console.print("[yellow]Usage: /set auto_detect [urls|images|files|all|none][/yellow]")
            
            elif key == "auto_compact":
                # Toggle auto-compact
                self.auto_compact_enabled = not self.auto_compact_enabled
                self.console.print(f"[green]Auto-compact {'enabled' if self.auto_compact_enabled else 'disabled'}[/green]")
            
            elif key == "auto_discover":
                # Toggle auto-discover
                self.auto_discover_files = not self.auto_discover_files
                self.console.print(f"[green]Auto-discover files {'enabled' if self.auto_discover_files else 'disabled'}[/green]")
                if self.auto_discover_files:
                    self.console.print("[dim]I will automatically find relevant files based on your queries[/dim]")
                else:
                    self.console.print("[dim]Use /files to manually add files to context[/dim]")
            
            else:
                self.console.print(f"[red]Unknown setting: {key}[/red]")
                self.console.print("[yellow]Available keys: temperature, max_tokens, region, auto_detect, auto_compact, auto_discover[/yellow]")
        
        except ValueError as e:
            self.console.print(f"[red]Invalid value: {e}[/red]")
    
    def _save_config(self):
        """Save current settings to configuration file."""
        # Map model type to string
        model_map_reverse = {
            ModelType.CLAUDE_SONNET_4: 'sonnet-4',
            ModelType.CLAUDE_3_7_SONNET: 'sonnet-3.7',
            ModelType.CLAUDE_OPUS_4: 'opus-4',
            ModelType.CLAUDE_3_5_SONNET_V2: 'sonnet-3.5-v2',
            ModelType.CLAUDE_3_5_SONNET: 'sonnet-3.5',
            ModelType.CLAUDE_3_OPUS: 'opus-3',
        }
        
        # Update config manager with current settings
        self.config_manager.update_config(
            model=model_map_reverse.get(self.bedrock_client.model_type, 'sonnet-4'),
            region=self.bedrock_client.region_name,
            temperature=self.bedrock_client.temperature,
            max_tokens=self.bedrock_client.max_tokens,
            compact_mode=self.compact_mode,
            history_dir=str(self.conversation.history_dir)
        )
        
        self.console.print(f"[green]Settings saved to {self.config_manager.config_file}[/green]")
        self.console.print("[dim]These settings will be loaded on next startup[/dim]")
    
    def _switch_model(self, model_name: str):
        """Switch to a different model."""
        model_map = {
            'sonnet-4': ModelType.CLAUDE_SONNET_4,
            'sonnet-3.7': ModelType.CLAUDE_3_7_SONNET,
            'opus-4': ModelType.CLAUDE_OPUS_4,
            # Legacy aliases
            'sonnet-3.5-v2': ModelType.CLAUDE_3_5_SONNET_V2,
            'sonnet-3.5': ModelType.CLAUDE_3_5_SONNET,
            'opus-3': ModelType.CLAUDE_3_OPUS,
        }
        
        if not model_name:
            self.console.print("[yellow]Available models: sonnet-4, sonnet-3.7, opus-4[/yellow]")
            self.console.print("[dim]Legacy models: sonnet-3.5-v2, sonnet-3.5, opus-3[/dim]")
            return
        
        model_type = model_map.get(model_name.lower())
        if model_type:
            self.bedrock_client.switch_model(model_type)
            # Update system prompt for new model
            self.system_prompt = self.bedrock_client.get_default_system_prompt(interactive=True)
            self.console.print(f"[green]Switched to {model_type.name}[/green]")
        else:
            self.console.print(f"[red]Unknown model: {model_name}[/red]")
    
    def _add_files(self, file_paths: str):
        """Add files to context."""
        if not file_paths:
            self.console.print("[yellow]Usage: /files <path1> [path2] ...[/yellow]")
            return
        
        paths = file_paths.split()
        added = []
        
        # Use progress for multiple files
        if len(paths) > 1:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Adding {len(paths)} files...", total=len(paths))
                
                for i, path_str in enumerate(paths):
                    path = Path(path_str).resolve()
                    progress.update(task, advance=1, description=f"Reading {path.name}...")
                    
                    if path.exists() and path.is_file():
                        if path not in self.context_files:
                            self.context_files.append(path)
                            added.append(path)
                    else:
                        self.console.print(f"[red]File not found: {path_str}[/red]")
        else:
            # Single file, no progress needed
            for path_str in paths:
                path = Path(path_str).resolve()
                if path.exists() and path.is_file():
                    if path not in self.context_files:
                        self.context_files.append(path)
                        added.append(path)
                else:
                    self.console.print(f"[red]File not found: {path_str}[/red]")
        
        if added:
            self.console.print(f"[green]Added {len(added)} file(s) to context[/green]")
    
    def _show_tree(self, path: str):
        """Show directory tree."""
        root = Path(path) if path else Path.cwd()
        
        try:
            tree = self.file_manager.get_directory_tree(root)
            self.console.print(Panel(tree, title=f"Directory Tree: {root}", border_style="blue"))
        except Exception as e:
            self.console.print(f"[red]Error showing tree: {e}[/red]")
    
    def _save_conversation(self, filename: str):
        """Save current conversation."""
        try:
            if filename:
                path = Path(filename)
                self.conversation.export_session(path, format="json")
            else:
                path = self.conversation.session_file
            
            self.console.print(f"[green]Conversation saved to: {path}[/green]")
        except Exception as e:
            self.console.print(f"[red]Error saving conversation: {e}[/red]")
    
    def _load_conversation(self, filename: str):
        """Load a previous conversation."""
        if not filename:
            # Show available sessions
            sessions = self.conversation.list_sessions()
            if not sessions:
                self.console.print("[yellow]No saved sessions found[/yellow]")
                return
            
            self.console.print("[bold]Available Sessions:[/bold]")
            for i, session in enumerate(sessions[:10]):
                timestamp = session['timestamp']
                count = session['message_count']
                self.console.print(f"  {i+1}. {timestamp} ({count} messages)")
            
            self.console.print("\n[yellow]Use: /load <filename> to load a specific session[/yellow]")
            return
        
        try:
            path = Path(filename)
            if self.conversation.load_session(path):
                self.console.print(f"[green]Loaded conversation from: {path}[/green]")
            else:
                self.console.print(f"[red]Failed to load conversation[/red]")
        except Exception as e:
            self.console.print(f"[red]Error loading conversation: {e}[/red]")
    
    def _export_conversation(self, args: str):
        """Export conversation."""
        parts = args.split()
        if len(parts) < 2:
            self.console.print("[yellow]Usage: /export <format> <filename>[/yellow]")
            self.console.print("[yellow]Formats: json, markdown[/yellow]")
            return
        
        format_type = parts[0].lower()
        filename = parts[1]
        
        if format_type not in ['json', 'markdown']:
            self.console.print(f"[red]Unknown format: {format_type}[/red]")
            return
        
        try:
            path = Path(filename)
            self.conversation.export_session(path, format=format_type)
            self.console.print(f"[green]Exported to: {path}[/green]")
        except Exception as e:
            self.console.print(f"[red]Error exporting: {e}[/red]")
    
    def _extract_code(self, output_dir: str):
        """Extract code blocks from the last assistant message."""
        if not self.conversation.messages:
            self.console.print("[yellow]No messages to extract code from[/yellow]")
            return
        
        # Find last assistant message
        assistant_msg = None
        for msg in reversed(self.conversation.messages):
            if msg.role == "assistant":
                assistant_msg = msg
                break
        
        if not assistant_msg:
            self.console.print("[yellow]No assistant messages found[/yellow]")
            return
        
        # Extract code blocks
        code_blocks = self.code_extractor.extract_code_blocks(assistant_msg.content)
        
        if not code_blocks:
            self.console.print("[yellow]No code blocks found[/yellow]")
            return
        
        # Save code blocks
        output_path = Path(output_dir) if output_dir else Path.cwd() / "extracted_code"
        saved_files = self.code_extractor.save_code_blocks(code_blocks, output_path)
        
        self.console.print(f"[green]Extracted {len(code_blocks)} code block(s)[/green]")
        for file in saved_files:
            self.console.print(f"  • {file}")
    
    def _process_message(self, user_input: str):
        """Process a user message."""
        # Auto-detect content in the input
        detections = self.auto_detector.extract_all(user_input)
        
        # Show what was detected
        summary = self.auto_detector.format_detection_summary(detections)
        if summary:
            self.console.print(f"[dim]{summary}[/dim]")
        
        # Prepare content parts
        content_parts = []
        
        # Auto-discover relevant files based on query if enabled
        discovered_files = []
        if self.auto_discover_files and not self.context_files and self.smart_context:
            # Only auto-discover if no files were manually added
            with self.console.status("[dim]Analyzing query and discovering relevant files...[/dim]", spinner="dots"):
                discovered_files = self.smart_context.get_relevant_files(user_input, max_files=10)
            
            if discovered_files:
                self.console.print(f"[dim]Auto-discovered {len(discovered_files)} relevant files[/dim]")
                # Show first few files
                for f in discovered_files[:3]:
                    try:
                        rel_path = f.relative_to(self.smart_context.project_analyzer.root_path)
                    except:
                        rel_path = f.name
                    self.console.print(f"[dim]  • {rel_path}[/dim]")
                if len(discovered_files) > 3:
                    self.console.print(f"[dim]  ... and {len(discovered_files) - 3} more[/dim]")
        
        # Add file context (manual files take precedence over discovered)
        files_to_include = self.context_files if self.context_files else discovered_files
        if files_to_include:
            context = self.file_manager.create_context_from_files(files_to_include)
            content_parts.append(context)
        
        # Auto-fetch URLs if detected
        if detections['urls']:
            url_contents = []
            # Use progress spinner for multiple URLs
            if len(detections['urls']) > 1:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(f"Fetching {len(detections['urls'])} URLs...", total=len(detections['urls']))
                    
                    for url in detections['urls']:
                        progress.update(task, advance=1, description=f"Fetching {url}...")
                        content = self.web_searcher.fetch_page_content(url)
                        if content:
                            # Limit content size
                            if len(content) > 5000:
                                content = content[:5000] + "..."
                            url_contents.append(f"=== Content from {url} ===\n{content}\n=== End of {url} ===")
                        else:
                            self.console.print(f"[yellow]Failed to fetch {url}[/yellow]")
            else:
                # Single URL
                for url in detections['urls']:
                    with self.console.status(f"[dim]Fetching {url}...[/dim]", spinner="dots"):
                        content = self.web_searcher.fetch_page_content(url)
                    if content:
                        # Limit content size
                        if len(content) > 5000:
                            content = content[:5000] + "..."
                        url_contents.append(f"=== Content from {url} ===\n{content}\n=== End of {url} ===")
                    else:
                        self.console.print(f"[yellow]Failed to fetch {url}[/yellow]")
            
            if url_contents:
                content_parts.append("\n\n".join(url_contents))
        
        # Add detected files if enabled
        if detections['file_paths'] and self.auto_detector.auto_detect_files:
            file_context = self.file_manager.create_context_from_files(detections['file_paths'])
            if file_context:
                content_parts.append(file_context)
        
        # Combine text content
        if content_parts:
            text_content = "\n\n".join(content_parts) + f"\n\n{user_input}"
        else:
            text_content = user_input
        
        # Add detected images to context images
        for img_path in detections['image_paths']:
            if img_path not in self.context_images:
                self.context_images.append(img_path)
        
        # Check if we have images to include
        if self.context_images:
            # Create multimodal content
            content_blocks = self.image_handler.create_multimodal_content(
                text_content, 
                self.context_images
            )
            
            # Clear images after use
            self.console.print(f"[dim]Including {len(self.context_images)} image(s) in message[/dim]")
            self.context_images = []
            
            # Add to conversation as multimodal
            self.conversation.add_message("user", content_blocks)
        else:
            # Regular text message
            self.conversation.add_message("user", user_input)
        
        # Prepare messages for API
        messages = []
        for msg in self.conversation.get_messages():
            # Handle both string and multimodal content
            if isinstance(msg.content, str):
                # For the last user message, include file context if any
                if msg == self.conversation.get_messages()[-1] and self.context_files:
                    messages.append(Message(role=msg.role, content=text_content))
                else:
                    messages.append(Message(role=msg.role, content=msg.content))
            else:
                # Multimodal content
                messages.append(Message(role=msg.role, content=msg.content))
        
        try:
            # Check context before sending
            current_messages = self._prepare_api_messages()
            stats = self.context_manager.get_context_stats(current_messages)
            
            if self.context_manager.should_warn(stats):
                self.console.print(
                    f"[yellow]⚠ Context usage: {stats.formatted_status}[/yellow]"
                )
            
            # Show thinking indicator with progress
            response_text = ""
            
            if self.compact_mode:
                # Use progress spinner for compact mode
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("Thinking...", total=None)
                    
                    for chunk in self.bedrock_client.send_message(messages, self.system_prompt):
                        response_text += chunk
                        progress.update(task, description=f"Generating response... ({len(response_text)} chars)")
                
                # Display full response
                self._display_response(response_text)
            else:
                # Detect query intent for fun verb
                query_context = self.analyze_query(user_input) if self.smart_context else None
                intent = query_context.intent if query_context else 'general'
                verbs = self.FUN_VERBS.get(intent, self.FUN_VERBS['general'])
                verb = random.choice(verbs)
                
                # Start streaming with dynamic status
                start_time = time.time()
                token_count = 0
                stop_streaming = threading.Event()
                
                # Shared variable for response length
                response_info = {'length': 0}
                
                def update_status(status_console, verb, start_time, response_info):
                    """Update status line in a separate thread."""
                    while not stop_streaming.is_set():
                        elapsed = int(time.time() - start_time)
                        # Estimate tokens (rough approximation)
                        estimated_tokens = response_info['length'] // 4
                        status_line = f"{verb}... ({elapsed}s · ⚙ {estimated_tokens/1000:.1f}k tokens · [dim]ESC to interrupt[/dim])"
                        status_console.print(f"\r{status_line}", end="")
                        time.sleep(0.1)
                
                # Create a separate console for status updates
                from rich.console import Console as StatusConsole
                status_console = StatusConsole(file=sys.stderr)
                
                # Start status thread
                status_thread = threading.Thread(target=update_status, args=(status_console, verb, start_time, response_info))
                status_thread.daemon = True
                status_thread.start()
                
                try:
                    # Start the stream
                    stream = self.bedrock_client.send_message(messages, self.system_prompt)
                    
                    # Show assistant label after a brief delay
                    self.console.print("\n[dim]Assistant:[/dim]")
                    
                    # Stream response
                    for chunk in stream:
                        response_text += chunk
                        response_info['length'] = len(response_text)
                        self.console.print(chunk, end="")
                        token_count = len(response_text) // 4  # Rough token estimate
                    
                    self.console.print()  # New line after streaming
                    
                finally:
                    # Stop status updates
                    stop_streaming.set()
                    status_thread.join(timeout=0.5)
                    # Clear status line
                    status_console.print("\r" + " " * 80 + "\r", end="")
            
            # Add to conversation history
            self.conversation.add_message("assistant", response_text)
            
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
    
    def _handle_git_command(self, command: str):
        """Handle git commands."""
        if not self.git:
            self.console.print("[red]Git commands not available - not in a git repository[/red]")
            return
        
        parts = command.split()
        
        try:
            if command == '/git' or command == '/git status':
                # Show git status
                status = self.git.get_status()
                formatted_status = self.git.format_status_for_display(status)
                self.console.print(Panel(formatted_status, title="Git Status", border_style="blue"))
            
            elif command == '/git diff':
                # Show unstaged diff
                diff = self.git.get_diff(staged=False)
                if diff:
                    syntax = Syntax(diff, "diff", theme="monokai", line_numbers=True)
                    self.console.print(Panel(syntax, title="Git Diff (Unstaged)", border_style="yellow"))
                else:
                    self.console.print("[yellow]No unstaged changes[/yellow]")
            
            elif command == '/git diff --staged':
                # Show staged diff
                diff = self.git.get_diff(staged=True)
                if diff:
                    syntax = Syntax(diff, "diff", theme="monokai", line_numbers=True)
                    self.console.print(Panel(syntax, title="Git Diff (Staged)", border_style="green"))
                else:
                    self.console.print("[yellow]No staged changes[/yellow]")
            
            elif command == '/git log':
                # Show git log
                log = self.git.get_log(limit=10, oneline=True)
                self.console.print(Panel(log, title="Recent Commits", border_style="blue"))
            
            elif command == '/git commit':
                # Create commit with AI-generated message
                self._create_git_commit()
            
            else:
                self.console.print(f"[red]Unknown git command: {command}[/red]")
                self.console.print("[yellow]Available: /git, /git diff, /git diff --staged, /git log, /git commit[/yellow]")
        
        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")
    
    def _create_git_commit(self):
        """Create a git commit with AI-generated message."""
        try:
            # Get current status
            status = self.git.get_status()
            
            if not status.staged and not status.modified:
                self.console.print("[yellow]No changes to commit[/yellow]")
                return
            
            # If no staged changes, ask to stage all
            if not status.staged and status.modified:
                self.console.print(f"[yellow]No staged changes. You have {len(status.modified)} modified files.[/yellow]")
                response = self.session.prompt("Stage all modified files? (y/n): ")
                if response.lower() == 'y':
                    self.git.stage_files(status.modified)
                    status = self.git.get_status()  # Refresh status
                else:
                    self.console.print("[yellow]Commit cancelled[/yellow]")
                    return
            
            # Get diff for commit message generation
            diff = self.git.get_diff(staged=True)
            if not diff:
                self.console.print("[yellow]No staged changes to commit[/yellow]")
                return
            
            # Show what will be committed
            self.console.print("\n[bold]Files to be committed:[/bold]")
            for file in status.staged[:10]:
                self.console.print(f"  • {file}")
            if len(status.staged) > 10:
                self.console.print(f"  ... and {len(status.staged) - 10} more")
            
            # Generate commit message using AI
            self.console.print("\n[dim]Generating commit message...[/dim]")
            
            prompt = f"""Based on the following git diff, generate a concise and descriptive commit message.
Follow conventional commit format if possible (feat:, fix:, docs:, etc).

Git diff:
```diff
{diff[:3000]}  # Limit diff size
```

Provide ONLY the commit message, no explanation."""
            
            messages = [Message(role="user", content=prompt)]
            
            commit_message = ""
            for chunk in self.bedrock_client.send_message(messages, stream=True):
                commit_message += chunk
            
            commit_message = commit_message.strip()
            
            # Show proposed message
            self.console.print(f"\n[green]Proposed commit message:[/green]")
            self.console.print(Panel(commit_message, border_style="green"))
            
            # Ask for confirmation or edit
            response = self.session.prompt("\nUse this message? (y)es, (e)dit, (c)ancel: ")
            
            if response.lower() == 'e':
                # Allow editing
                commit_message = self.session.prompt("Commit message: ", default=commit_message)
            elif response.lower() != 'y':
                self.console.print("[yellow]Commit cancelled[/yellow]")
                return
            
            # Create the commit
            commit_hash = self.git.commit(commit_message)
            self.console.print(f"\n[green]✓ Created commit: {commit_hash[:8]}[/green]")
            self.console.print(f"[dim]Message: {commit_message}[/dim]")
            
        except Exception as e:
            self.console.print(f"[red]Error creating commit: {e}[/red]")
    
    def _display_response(self, response: str):
        """Display response with proper formatting."""
        # Try to render as markdown
        try:
            md = Markdown(response)
            self.console.print(md)
        except Exception:
            # Fallback to plain text
            self.console.print(response)
    
    def _handle_search(self, query: str):
        """Handle web search command."""
        if not query:
            self.console.print("[yellow]Usage: /search <query>[/yellow]")
            self.console.print("[yellow]Example: /search python asyncio best practices[/yellow]")
            return
        
        try:
            # Show search in progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Searching for: {query}", total=None)
                
                # Get search results with AI summary
                summary = self.smart_search.search_with_context(
                    query,
                    context="User is asking this in the context of a coding assistance session."
                )
            
            # Display results
            self.console.print("\n[bold]Search Results:[/bold]\n")
            md = Markdown(summary)
            self.console.print(md)
            
            # Add to conversation
            self.conversation.add_message("user", f"/search {query}")
            self.conversation.add_message("assistant", summary)
            
        except Exception as e:
            self.console.print(f"[red]Search error: {e}[/red]")
    
    def _handle_screenshot(self):
        """Handle screenshot capture."""
        try:
            self.console.print("[dim]Capturing screenshot...[/dim]")
            
            # Capture screenshot
            screenshot_path = self.screenshot_capture.capture_screenshot()
            
            if screenshot_path:
                # Add to context images
                self.context_images.append(screenshot_path)
                self.console.print(f"[green]Screenshot captured: {screenshot_path.name}[/green]")
                self.console.print("[dim]The screenshot will be included in your next message[/dim]")
            else:
                self.console.print("[red]Failed to capture screenshot[/red]")
                self.console.print("[yellow]Make sure pyautogui is installed: pip install pyautogui[/yellow]")
                
        except Exception as e:
            self.console.print(f"[red]Screenshot error: {e}[/red]")
    
    def _add_images(self, file_paths: str):
        """Add image files to context."""
        if not file_paths:
            self.console.print("[yellow]Usage: /image <path1> [path2] ...[/yellow]")
            return
        
        paths = file_paths.split()
        added_count = 0
        
        for path_str in paths:
            path = Path(path_str).resolve()
            
            if not path.exists():
                self.console.print(f"[red]File not found: {path}[/red]")
                continue
            
            if not self.image_handler.is_image_file(path):
                self.console.print(f"[yellow]Not an image file: {path.name}[/yellow]")
                self.console.print(f"[dim]Supported formats: {', '.join(self.image_handler.SUPPORTED_FORMATS)}[/dim]")
                continue
            
            if path not in self.context_images:
                self.context_images.append(path)
                added_count += 1
                self.console.print(f"[green]Added image: {path.name}[/green]")
            else:
                self.console.print(f"[yellow]Image already in context: {path.name}[/yellow]")
        
        if added_count > 0:
            self.console.print(f"[dim]Total images in context: {len(self.context_images)}[/dim]")
    
    def _prepare_api_messages(self) -> List[dict]:
        """Prepare messages for API calls with potential compaction.
        
        Returns:
            List of message dictionaries
        """
        messages = []
        
        for msg in self.conversation.get_messages():
            # Convert to dict format
            if hasattr(msg, 'to_dict'):
                messages.append(msg.to_dict())
            else:
                messages.append({
                    'role': msg.role,
                    'content': msg.content
                })
        
        # Check if we need to compact
        if self.auto_compact_enabled:
            stats = self.context_manager.get_context_stats(messages)
            if stats.should_compact:
                self.console.print("[yellow]Auto-compacting conversation history...[/yellow]")
                messages = self.context_manager.compact_messages(messages)
                
                # Show new stats
                new_stats = self.context_manager.get_context_stats(messages)
                self.console.print(
                    f"[green]Compacted: {stats.total_tokens:,} → {new_stats.total_tokens:,} tokens "
                    f"({new_stats.remaining_tokens:,} available)[/green]"
                )
        
        return messages
    
    def _show_project_info(self):
        """Show project analysis information."""
        if not self.smart_context:
            self.console.print("[yellow]Project analysis not available[/yellow]")
            return
            
        try:
            with self.console.status("[dim]Analyzing project structure...[/dim]", spinner="dots"):
                project_info = self.smart_context.project_analyzer.analyze_project()
            
            # Format project information
            info_text = f"[bold]Project Analysis[/bold]\n\n"
            info_text += f"Type: [green]{project_info.project_type}[/green]\n"
            info_text += f"Root: {project_info.root_path}\n"
            
            if project_info.framework:
                info_text += f"Framework: [cyan]{project_info.framework}[/cyan]\n"
            
            if project_info.main_directories:
                info_text += f"\nMain Directories:\n"
                for d in project_info.main_directories[:5]:
                    rel_path = d.relative_to(project_info.root_path)
                    info_text += f"  • {rel_path}\n"
            
            if project_info.test_directories:
                info_text += f"\nTest Directories:\n"
                for d in project_info.test_directories[:3]:
                    rel_path = d.relative_to(project_info.root_path)
                    info_text += f"  • {rel_path}\n"
            
            if project_info.config_files:
                info_text += f"\nConfiguration Files:\n"
                for f in project_info.config_files[:5]:
                    rel_path = f.relative_to(project_info.root_path)
                    info_text += f"  • {rel_path}\n"
            
            # Add file count
            total_files = sum(1 for _ in project_info.root_path.rglob('*') 
                            if _.is_file() and not self.smart_context.project_analyzer._should_ignore(_))
            info_text += f"\nTotal Files: {total_files:,}\n"
            
            info_text += f"\n[dim]Auto-discovery: {'[green]enabled[/green]' if self.auto_discover_files else '[red]disabled[/red]'}[/dim]"
            
            self.console.print(Panel(info_text, title="Project Information", border_style="blue"))
            
        except Exception as e:
            self.console.print(f"[red]Error analyzing project: {e}[/red]")
    
    def analyze_query(self, query: str):
        """Simple query analysis to determine intent."""
        query_lower = query.lower()
        
        # Check for intent patterns
        if any(word in query_lower for word in ['debug', 'fix', 'error', 'bug', 'issue', 'problem']):
            return type('QueryContext', (), {'intent': 'debug'})
        elif any(word in query_lower for word in ['implement', 'add', 'create', 'build', 'write']):
            return type('QueryContext', (), {'intent': 'implement'})
        elif any(word in query_lower for word in ['test', 'testing', 'verify', 'check']):
            return type('QueryContext', (), {'intent': 'test'})
        elif any(word in query_lower for word in ['refactor', 'improve', 'optimize', 'clean']):
            return type('QueryContext', (), {'intent': 'refactor'})
        elif any(word in query_lower for word in ['explain', 'what', 'how', 'why', 'understand']):
            return type('QueryContext', (), {'intent': 'explain'})
        elif any(word in query_lower for word in ['review', 'analyze', 'audit', 'inspect']):
            return type('QueryContext', (), {'intent': 'review'})
        else:
            return type('QueryContext', (), {'intent': 'general'})
    
    def _toggle_autodiscover(self):
        """Toggle automatic file discovery."""
        if not self.smart_context:
            self.console.print("[yellow]Auto-discovery not available - smart context initialization failed[/yellow]")
            return
            
        self.auto_discover_files = not self.auto_discover_files
        status = "[green]enabled[/green]" if self.auto_discover_files else "[red]disabled[/red]"
        self.console.print(f"Automatic file discovery {status}")
        
        if self.auto_discover_files:
            self.console.print("[dim]I will automatically find relevant files based on your queries[/dim]")
        else:
            self.console.print("[dim]Use /files to manually add files to context[/dim]")
    
    def _execute_bash(self, command: str):
        """Execute a bash command and display output."""
        if not command:
            self.console.print("[yellow]Usage: /bash <command> or /! <command>[/yellow]")
            self.console.print("[yellow]Example: /bash ls -la[/yellow]")
            self.console.print("[yellow]Example: /! pwd[/yellow]")
            return
        
        # Safety check for dangerous commands
        dangerous_patterns = [
            r'\brm\s+-rf\s+/', r'\brm\s+-fr\s+/',  # rm -rf /
            r'\b>\s*/dev/sd[a-z]', r'\bdd\s+.*of=/dev/sd[a-z]',  # disk operations
            r'\bmkfs\.', r'\bformat\s+',  # formatting
            r'\b:\(\)\{\s*:\|\s*:\s*&\s*\}', # fork bomb
            r'\bsudo\s+rm\s+-rf\s+/', # sudo rm -rf /
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                self.console.print("[red]⚠️  Dangerous command detected![/red]")
                response = self.session.prompt("Are you sure you want to execute this? (yes/no): ")
                if response.lower() != 'yes':
                    self.console.print("[yellow]Command cancelled[/yellow]")
                    return
        
        try:
            # Show command being executed
            self.console.print(f"[dim]$ {command}[/dim]")
            
            # Handle cd command specially to change working directory
            if command.strip().startswith('cd '):
                path = command[3:].strip()
                # Remove quotes if present
                if path.startswith('"') and path.endswith('"'):
                    path = path[1:-1]
                elif path.startswith("'") and path.endswith("'"):
                    path = path[1:-1]
                
                try:
                    # Expand ~ and environment variables
                    path = os.path.expanduser(os.path.expandvars(path))
                    # Make absolute
                    if not os.path.isabs(path):
                        path = os.path.join(os.getcwd(), path)
                    
                    os.chdir(path)
                    self.console.print(f"[green]Changed directory to: {os.getcwd()}[/green]")
                    return
                except Exception as e:
                    self.console.print(f"[red]Failed to change directory: {e}[/red]")
                    return
            
            # Execute command with a timeout
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=os.getcwd()
            )
            
            # Display output
            if result.stdout:
                self.console.print(result.stdout.rstrip())
            
            if result.stderr:
                self.console.print(f"[red]{result.stderr.rstrip()}[/red]")
            
            # Show exit code if non-zero
            if result.returncode != 0:
                self.console.print(f"[red]Exit code: {result.returncode}[/red]")
            
            # Add to conversation history for context
            output = result.stdout + (f"\n{result.stderr}" if result.stderr else "")
            if output.strip():
                self.conversation.add_message(
                    "user", 
                    f"Executed bash command: {command}\nOutput:\n{output[:2000]}"  # Limit output
                )
            
        except subprocess.TimeoutExpired:
            self.console.print("[red]Command timed out after 30 seconds[/red]")
        except Exception as e:
            self.console.print(f"[red]Error executing command: {e}[/red]")
    
    def _run_last_command(self):
        """Run the last command or code block from assistant's response."""
        # Get the last assistant message
        messages = self.conversation.get_messages()
        last_assistant_msg = None
        
        for msg in reversed(messages):
            if msg.role == 'assistant':
                last_assistant_msg = msg
                break
        
        if not last_assistant_msg:
            self.console.print("[yellow]No assistant response found[/yellow]")
            return
        
        # Extract code blocks
        code_blocks = self.code_extractor.extract_code_blocks(last_assistant_msg.content)
        
        # Look for bash/shell commands
        bash_blocks = []
        for block in code_blocks:
            if block['language'] in ['bash', 'sh', 'shell', 'console', 'terminal']:
                bash_blocks.append(block)
        
        # Also look for inline commands (lines starting with $ or #)
        import re
        inline_commands = re.findall(r'^\s*[$#]\s*(.+)$', last_assistant_msg.content, re.MULTILINE)
        
        # Combine all found commands
        all_commands = []
        for block in bash_blocks:
            # Split multi-line commands
            commands = [cmd.strip() for cmd in block['code'].split('\n') if cmd.strip()]
            all_commands.extend(commands)
        
        all_commands.extend(inline_commands)
        
        if not all_commands:
            self.console.print("[yellow]No executable commands found in the last response[/yellow]")
            self.console.print("[dim]Tip: I look for code blocks marked as bash/sh/shell or lines starting with $ or #[/dim]")
            return
        
        # If single command, run it
        if len(all_commands) == 1:
            self.console.print(f"[green]Running command:[/green] {all_commands[0]}")
            self._execute_bash(all_commands[0])
        else:
            # Multiple commands - let user choose
            self.console.print("[green]Found multiple commands:[/green]")
            for i, cmd in enumerate(all_commands, 1):
                self.console.print(f"  {i}. {cmd}")
            
            try:
                choice = self.session.prompt("Select command number (or 'all' to run all): ")
                
                if choice.lower() == 'all':
                    for cmd in all_commands:
                        self.console.print(f"\n[green]Running:[/green] {cmd}")
                        self._execute_bash(cmd)
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_commands):
                        self._execute_bash(all_commands[idx])
                    else:
                        self.console.print("[red]Invalid selection[/red]")
            except (ValueError, KeyboardInterrupt):
                self.console.print("[yellow]Cancelled[/yellow]")
    
    def _show_todos(self):
        """Extract and show tasks/todos from conversation."""
        import re
        
        todos = []
        messages = self.conversation.get_messages()
        
        # Patterns to find todos/tasks
        todo_patterns = [
            r'(?:TODO|TASK|FIXME):\s*(.+)',
            r'(?:^|\n)\s*[-*]\s*\[\s*\]\s*(.+)',  # Markdown checkboxes
            r'(?:^|\n)\s*\d+\.\s*(.+?)(?:\n|$)',  # Numbered lists
            r'(?:need to|should|must|will)\s+(.+?)(?:\.|$)',  # Action items
        ]
        
        for msg in messages:
            if msg.role == 'assistant':
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                
                # Look for explicit todos
                for pattern in todo_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                    for match in matches:
                        task = match.strip()
                        if len(task) > 10 and len(task) < 200:  # Reasonable task length
                            todos.append(task)
        
        if todos:
            # Remove duplicates while preserving order
            seen = set()
            unique_todos = []
            for todo in todos:
                if todo.lower() not in seen:
                    seen.add(todo.lower())
                    unique_todos.append(todo)
            
            # Display todos
            todo_text = "[bold]📋 Tasks from Conversation[/bold]\n\n"
            for i, todo in enumerate(unique_todos[:20], 1):  # Limit to 20
                todo_text += f"  {i}. {todo}\n"
            
            if len(unique_todos) > 20:
                todo_text += f"\n  ... and {len(unique_todos) - 20} more"
            
            self.console.print(Panel(todo_text, border_style="blue"))
        else:
            self.console.print("[yellow]No specific tasks found in conversation[/yellow]")
            self.console.print("[dim]Tip: I look for TODO markers, checkboxes, numbered lists, and action phrases[/dim]")