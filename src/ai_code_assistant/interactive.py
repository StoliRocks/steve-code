"""Interactive mode for the AI Code Assistant."""

import sys
import os
import subprocess
import logging
import time
import random
import threading
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
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
from rich.live import Live

from .bedrock_client import BedrockClient, ModelType, Message
from .conversation import ConversationHistory
from .code_extractor import CodeExtractor
from .file_context import FileContextManager
from .config import ConfigManager
from .web_search import WebSearcher, SmartWebSearch
from .image_handler import ImageHandler
from .command_completer import CommandCompleter
from .auto_detection import AutoDetector
from .context_manager import ContextManager, ContextStats
from .query_analyzer import QueryAnalyzer
from .structured_output import StructuredOutput, UpdateItem, TodoItem
from .action_executor import ActionExecutor
from .collapsible_output import CollapsibleOutput
from .structured_action_parser import StructuredActionParser
from .action_reprocessor import ActionReprocessor
from .response_filter import ResponseFilter
from .response_processor import ResponseProcessor
from .update_checker import UpdateChecker, get_update_message
from .execution_planner import ExecutionPlanner

logger = logging.getLogger(__name__)


class InteractiveMode:
    """Interactive chat mode for the AI assistant."""
    
    
    # Interactive commands
    COMMANDS = {
        '/help': 'Show this help message',
        '/clear': 'Clear conversation history',
        '/exit': 'Exit the assistant',
        '/quit': 'Exit the assistant',
        '/save': 'Save the current conversation',
        '/load': 'Load a previous conversation',
        '/files': 'Add files to context (Note: files are auto-discovered based on your queries)',
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
        '/todo done <number>': 'Mark a todo as completed',
        '/todo run <number>': 'Execute a specific action',
        '/todo all': 'Execute all pending actions',
        '/todo skip': 'Skip the next pending action',
        '/todo actions': 'Show current action queue',
        '/verbose': 'Toggle verbose mode (show/hide technical details like XML blocks)',
        '/settings': 'Show or modify settings (use /settings <key> <value>)',
        '/set': 'Set a configuration value (temperature, max_tokens, region, auto_detect, verbose)',
        '/config': 'Save current settings to config file',
        '/search': 'Search the web for current information',
        '/screenshot': 'Take a screenshot for analysis',
        '/image': 'Add image files for analysis',
        '/update': 'Check for and install updates',
    }
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        history_dir: Optional[Path] = None,
        compact_mode: bool = True  # Default to non-streaming mode
    ):
        """Initialize interactive mode.
        
        Args:
            bedrock_client: Bedrock client instance
            history_dir: Directory for conversation history
            compact_mode: Whether to show full response at once (True) or stream it (False)
        """
        self.bedrock_client = bedrock_client
        self.conversation = ConversationHistory(history_dir)
        self.code_extractor = CodeExtractor()
        self.file_manager = FileContextManager()
        self.console = Console()
        self.compact_mode = compact_mode
        self.verbose_mode = False  # Hide implementation details by default
        self.config_manager = ConfigManager()
        
        # File context
        self.context_files: List[Path] = []
        
        # Working directory
        self.root_path = Path.cwd()
        
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
        
        # Initialize web search
        self.web_searcher = WebSearcher()
        self.smart_search = SmartWebSearch(self.web_searcher, self.bedrock_client)
        
        # Initialize image handling
        self.image_handler = ImageHandler()
        self.screenshot_capture = None  # Will be initialized on first use
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
            self.smart_context = QueryAnalyzer()
            self.auto_discover_files = True  # Enable by default
            
            # Analyze project on startup to understand context
            self.project_info = None
            self.project_summary = ""
            self.project_analyzer = None
            self._analyze_project_context()
            
        except Exception as e:
            logger.warning(f"Failed to initialize smart context: {e}")
            self.smart_context = None
            self.auto_discover_files = False
            self.project_info = None
            self.project_analyzer = None
            self.project_summary = ""
        
        # Initialize structured output formatter
        self.structured_output = StructuredOutput(self.console)
        
        # Initialize action executor
        self.action_executor = ActionExecutor(self.console, self.root_path)
        
        # Initialize collapsible output
        self.collapsible_output = CollapsibleOutput(self.console)
        
        # Initialize structured action parser
        self.action_parser = StructuredActionParser()
        self.action_reprocessor = ActionReprocessor(self.bedrock_client)
        
        # Initialize response processor
        self.response_processor = ResponseProcessor(verbose_mode=self.verbose_mode)
        
        # Track current todos
        self.current_todos: List[TodoItem] = []
        
        # Track action todos separately
        self.action_todos: List[TodoItem] = []
        
        # Store last response for /expand command
        self.last_response = ""
        self.last_response_sections = []
        
        # Initialize update checker
        self.update_checker = UpdateChecker()
        self.update_check_thread = None
        self.update_available = False
        self.last_update_message = None
        
        # Initialize execution planner
        self.execution_planner = ExecutionPlanner(bedrock_client, self.console)
    
    def _create_prompt_style(self) -> Style:
        """Create prompt style."""
        return Style.from_dict({
            'prompt': '#00aa00 bold',
        })
    
    def _handle_update(self):
        """Handle the /update command."""
        self.console.print("[cyan]Checking for updates...[/cyan]")
        
        # Force check for updates
        update_info = self.update_checker.check_for_update(force=True)
        
        if update_info:
            latest_version, download_url = update_info
            from .version import __version__
            
            self.console.print(f"\n[green]Update available![/green]")
            self.console.print(f"Current version: v{__version__}")
            self.console.print(f"Latest version: v{latest_version}")
            self.console.print(f"Release: {download_url}\n")
            
            # Ask for confirmation
            response = input("Would you like to update now? (y/N): ")
            if response.lower() == 'y':
                if self.update_checker.auto_update(confirm=False):
                    self.console.print("\n[yellow]Please restart steve-code to use the new version.[/yellow]")
                    self.console.print("Exiting...")
                    sys.exit(0)
                else:
                    self.console.print("\n[red]Update failed. Please try manually:[/red]")
                    self.console.print("pip install --upgrade git+https://github.com/StoliRocks/steve-code.git")
        else:
            self.console.print(f"[green]You're already on the latest version![/green]")
    
    
    def _background_update_check(self):
        """Background thread to check for updates periodically."""
        first_check = True
        while True:
            try:
                # On first run, wait just 5 seconds to avoid conflicting with startup
                # Then check every 30 minutes
                if first_check:
                    time.sleep(5)
                    first_check = False
                else:
                    time.sleep(30 * 60)  # 30 minutes
                
                # Check for updates
                if self.verbose_mode:
                    self.console.print("\n[dim]Background update check running...[/dim]")
                    
                update_info = self.update_checker.check_for_update(force=True)  # Force check
                if update_info and not self.update_available:
                    self.update_available = True
                    latest_version, _ = update_info
                    from .version import __version__
                    self.last_update_message = (
                        f"\n[yellow]📦 Update available: v{latest_version} "
                        f"(current: v{__version__})[/yellow]\n"
                        f"[dim]Run '/update' or 'sc --update' to install[/dim]\n"
                    )
                    # Print the update message (thread-safe with Rich console)
                    self.console.print(self.last_update_message)
                elif self.verbose_mode:
                    self.console.print("[dim]No updates found in background check[/dim]")
            except Exception as e:
                logger.debug(f"Background update check failed: {e}")
                if self.verbose_mode:
                    self.console.print(f"[dim]Background update check error: {e}[/dim]")
    
    def _get_screenshot_capture(self):
        """Get or initialize screenshot capture lazily."""
        if self.screenshot_capture is None:
            try:
                from .image_handler import ScreenshotCapture
                self.screenshot_capture = ScreenshotCapture()
            except Exception as e:
                logger.warning(f"Screenshot capture unavailable: {e}")
                # Return a dummy object that always fails
                class DummyScreenshot:
                    def capture_screenshot(self, *args, **kwargs):
                        logger.error("Screenshot capture not available - install pyautogui")
                        return None
                self.screenshot_capture = DummyScreenshot()
        return self.screenshot_capture
    
    def run(self):
        """Run the interactive mode."""
        try:
            self._show_welcome()
        except Exception as e:
            from rich.markup import escape
            self.console.print(f"[red]Error showing welcome: {escape(str(e))}[/red]")
            logger.error(f"Welcome screen error: {e}", exc_info=True)
        
        # Start background update checker thread
        self.update_check_thread = threading.Thread(
            target=self._background_update_check,
            daemon=True  # Dies when main program exits
        )
        self.update_check_thread.start()
        
        # Also check for updates on startup
        try:
            if self.verbose_mode:
                self.console.print("[dim]Checking for updates...[/dim]")
            update_msg = get_update_message()
            if update_msg:
                self.console.print(update_msg)
                self.console.print()
                self.update_available = True
            elif self.verbose_mode:
                from .version import __version__
                self.console.print(f"[dim]No updates available (current: v{__version__})[/dim]")
        except Exception as e:
            logger.debug(f"Initial update check failed: {e}")
            if self.verbose_mode:
                self.console.print(f"[dim]Update check failed: {e}[/dim]")
        
        # Debug: Confirm we got this far
        self.console.print("[dim]Ready for input...[/dim]")
        
        # Check if we can actually run in interactive mode
        if not sys.stdin.isatty():
            self.console.print("[red]Error: Interactive mode requires a terminal (TTY)[/red]")
            self.console.print("[yellow]Try running with a direct prompt instead:[/yellow]")
            self.console.print("  sc \"Your question here\"")
            return
            
        # Debug: Print that we're entering the main loop
        logger.debug("Entering interactive main loop...")
        
        try:
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
                    
                    # Debug: About to show prompt
                    logger.debug("About to show prompt...")
                    
                    # Get user input
                    user_input = self.session.prompt(
                        prompt_text,
                        multiline=False,
                        style=self._create_prompt_style()
                    )
                    
                    if not user_input.strip():
                        # If we have pending action todos, execute the next one
                        if self.action_todos:
                            next_todo = next((t for t in self.action_todos if t.status == "pending"), None)
                            if next_todo:
                                self._execute_action_todo(next_todo)
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
                    from rich.markup import escape
                    self.console.print(f"[red]Error: {escape(str(e))}[/red]")
                    logger.exception("Error in main loop")
        except Exception as e:
            self.console.print(f"[red]Fatal error in interactive mode: {e}[/red]")
            logger.exception("Fatal error in interactive mode")
            import traceback
            traceback.print_exc()
    
    def _show_welcome(self):
        """Show welcome message."""
        welcome_text = "[bold blue]Steve Code[/bold blue]\n\n"
        welcome_text += "Interactive mode with AWS Bedrock\n"
        welcome_text += f"Model: [green]{self.bedrock_client.model_type.name}[/green]\n"
        
        # Add project context if available
        if self.project_summary:
            welcome_text += f"\n[cyan]{self.project_summary}[/cyan]\n"
        
        welcome_text += "\nType [yellow]/help[/yellow] for available commands\n"
        welcome_text += "Type [yellow]/exit[/yellow] to quit"
        
        welcome = Panel(
            Text.from_markup(welcome_text),
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
                self.console.print("[yellow]Keys: temperature, max_tokens, region, verbose[/yellow]")
        
        elif cmd == '/verbose':
            self.verbose_mode = not self.verbose_mode
            self.response_processor.verbose_mode = self.verbose_mode
            if self.verbose_mode:
                self.console.print("[yellow]Verbose mode enabled - showing technical details[/yellow]")
            else:
                self.console.print("[green]Verbose mode disabled - hiding technical details[/green]")
        
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
            if args.startswith('done '):
                self._mark_todo_done(args[5:])
            elif args == 'all':
                self._execute_all_action_todos()
            elif args.startswith('run '):
                self._execute_action_todo_by_number(args[4:])
            elif args.startswith('skip'):
                self._skip_next_action_todo()
            elif args == 'actions':
                self._show_action_todos()
            else:
                self._show_todos()
        
        elif cmd == '/update':
            self._handle_update()
        
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("Type /help for available commands")
        
        return True
    
    def _show_help(self):
        """Show help message."""
        help_text = "[bold]Available Commands:[/bold]\n\n"
        for cmd, desc in self.COMMANDS.items():
            help_text += f"  [cyan]{cmd:<12}[/cyan] {desc}\n"
        
        # Add keyboard shortcuts section
        help_text += "\n[bold]Keyboard Shortcuts:[/bold]\n\n"
        help_text += "  [cyan]ctrl+r[/cyan]      Expand collapsed output\n"
        help_text += "  [cyan]ctrl+c[/cyan]      Interrupt current operation\n"
        help_text += "  [cyan]ctrl+d[/cyan]      Exit interactive mode\n"
        help_text += "  [cyan]↑/↓[/cyan]         Navigate command history\n"
        help_text += "  [cyan]tab[/cyan]         Auto-complete files/commands\n"
        
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
Response Mode: [yellow]{'Full' if self.compact_mode else 'Streaming'}[/yellow]

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
Auto-detect URLs: [yellow]{'Enabled' if self.auto_detector.auto_fetch_urls else 'Disabled'}[/yellow]
Auto-detect Images: [yellow]{'Enabled' if self.auto_detector.auto_detect_images else 'Disabled'}[/yellow]
Auto-detect Files: [yellow]{'Enabled' if self.auto_detector.auto_detect_files else 'Disabled'}[/yellow]
Auto-discover Files: [yellow]{'Enabled' if self.auto_discover_files else 'Disabled'}[/yellow]
Auto-compact: [yellow]{'Enabled' if self.auto_compact_enabled else 'Disabled'}[/yellow]
Verbose Mode: [yellow]{'Enabled' if self.verbose_mode else 'Disabled'}[/yellow]

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
            
            elif key == "verbose":
                # Parse verbose setting
                if value.lower() in ['true', 'on', '1', 'yes']:
                    self.verbose_mode = True
                    self.response_processor.verbose_mode = True
                    self.console.print("[yellow]Verbose mode enabled - showing technical details[/yellow]")
                elif value.lower() in ['false', 'off', '0', 'no']:
                    self.verbose_mode = False
                    self.response_processor.verbose_mode = False
                    self.console.print("[green]Verbose mode disabled - hiding technical details[/green]")
                else:
                    self.console.print(f"[yellow]Invalid verbose value. Use: true/false, on/off, yes/no[/yellow]")
            
            else:
                self.console.print(f"[red]Unknown setting: {key}[/red]")
                self.console.print("[yellow]Available keys: temperature, max_tokens, region, auto_detect, auto_compact, auto_discover, verbose[/yellow]")
        
        except ValueError as e:
            from rich.markup import escape
            self.console.print(f"[red]Invalid value: {escape(str(e))}[/red]")
    
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
            compact_mode=self.compact_mode,  # Whether to show full response vs streaming
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
            from rich.markup import escape
            self.console.print(f"[red]Error showing tree: {escape(str(e))}[/red]")
    
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
            from rich.markup import escape
            self.console.print(f"[red]Error saving conversation: {escape(str(e))}[/red]")
    
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
            from rich.markup import escape
            self.console.print(f"[red]Error loading conversation: {escape(str(e))}[/red]")
    
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
            from rich.markup import escape
            self.console.print(f"[red]Error exporting: {escape(str(e))}[/red]")
    
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
        
        # Show code blocks and ask for confirmation
        output_path = Path(output_dir) if output_dir else Path.cwd() / "extracted_code"
        
        self.console.print(f"\n[bold]Found {len(code_blocks)} code block(s) to save:[/bold]")
        for i, block in enumerate(code_blocks):
            filename = block.filename or f"code_block_{i + 1}.{self._get_extension(block.language)}"
            self.console.print(f"  • {output_path / filename} ({block.language})")
        
        # Ask for confirmation
        self.console.print(f"\n[yellow]Save these {len(code_blocks)} file(s) to {output_path}?[/yellow]")
        response = self.session.prompt("(y/n) > ").strip().lower()
        
        if response == 'y':
            saved_files = self.code_extractor.save_code_blocks(code_blocks, output_path)
            self.console.print(f"[green]✓ Saved {len(saved_files)} file(s)[/green]")
            for file in saved_files:
                self.console.print(f"  • {file}")
        else:
            self.console.print("[yellow]Code extraction cancelled[/yellow]")
    
    def _get_extension(self, language: str) -> str:
        """Get file extension for a language."""
        extensions = {
            'python': 'py',
            'javascript': 'js',
            'typescript': 'ts',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'go': 'go',
            'rust': 'rs',
            'ruby': 'rb',
            'php': 'php',
            'shell': 'sh',
            'bash': 'sh',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'yaml': 'yaml',
            'xml': 'xml',
            'sql': 'sql',
            'markdown': 'md',
        }
        return extensions.get(language.lower(), 'txt')
    
    def _analyze_intent(self, user_input: str) -> Dict[str, Any]:
        """Use Claude to analyze the user's intent and create an action plan.
        
        Args:
            user_input: The user's query
            
        Returns:
            Dictionary with intent analysis and action plan
        """
        # Create a quick intent analysis prompt
        intent_prompt = f"""As an intelligent coding assistant, analyze this user query and determine their intent:
Query: "{user_input}"

Project context: {self.project_summary if self.project_summary else "Working in a code repository"}

Provide a JSON response with:
1. "intent": Brief description of what the user wants
2. "requires_code_analysis": true/false - whether this needs local code analysis
3. "suggested_actions": List of 2-5 specific actions to take
4. "files_needed": true/false - whether we should auto-discover files
5. "file_search_patterns": List of glob patterns to find relevant files (e.g., "*.png", "**/*.py", "src/**/*.js")
6. "file_extensions": List of file extensions to look for (e.g., [".png", ".jpg", ".py"])
7. "search_keywords": Keywords to search for in filenames

Be extremely proactive - assume the user wants immediate help with their local code.
If they mention "my" anything, they mean the code in the current directory.
Do NOT suggest asking for more information - suggest concrete actions.

DEFAULT TO TRUE for requires_code_analysis unless the query is clearly not about code.
Examples that require code analysis: recommendations, help, improve, review, debug, etc.
Examples that don't: "what is Python?", "explain git", "how does AWS work?"

Special handling:
- If user mentions "screenshots", "images", "pictures" -> include image extensions
- If user mentions specific file types -> include those extensions
- If user wants to analyze visuals -> set file_extensions to image formats
- "my screenshots" or "the screenshots" means actual image files in the project
- Do NOT analyze code capabilities - analyze actual visual content

IMPORTANT: When user says "summarize the screenshots" they want you to:
1. Find actual screenshot/image files (PNG, JPG, etc.)
2. Look at the visual content
3. Describe what's shown in the images
They do NOT want you to explain screenshot functionality!

Example response for "summarize the screenshots":
{{
  "intent": "User wants me to analyze the visual content of screenshot images in the project",
  "requires_code_analysis": false,
  "suggested_actions": [
    "Find all screenshot/image files in the project",
    "Analyze the visual content of each image",
    "Describe what is shown in the screenshots"
  ],
  "files_needed": true,
  "file_search_patterns": ["*.png", "*.jpg", "*.jpeg", "*screenshot*", "*Screenshot*"],
  "file_extensions": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
  "search_keywords": ["screenshot", "Screenshot", "image", "screen"]
}}"""

        try:
            # Quick API call for intent analysis
            messages = [Message(role="user", content=intent_prompt)]
            response_text = ""
            
            for chunk in self.bedrock_client.send_message(messages, stream=True):
                response_text += chunk
            
            # Try to parse JSON from response
            import json
            import re
            
            # Extract JSON from response - handle nested objects
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group())
                return intent_data
            
        except Exception as e:
            logger.debug(f"Intent analysis failed: {e}")
        
        # Fallback to simple analysis
        return {
            "intent": "Process user query",
            "requires_code_analysis": any(word in user_input.lower() for word in ['my', 'code', 'application', 'project']),
            "suggested_actions": ["Respond to user query"],
            "files_needed": 'my' in user_input.lower()
        }
    
    def _process_message(self, user_input: str):
        """Process a user message."""
        # Show immediate processing indication - keep it running during all setup
        with self.console.status("[dim]● Understanding your request...[/dim]", spinner="dots") as status:
            # Auto-detect content in the input
            detections = self.auto_detector.extract_all(user_input)
            
            # Show what was detected (only in verbose mode)
            if self.verbose_mode:
                summary = self.auto_detector.format_detection_summary(detections)
                if summary:
                    status.stop()
                    self.console.print(f"[dim]{summary}[/dim]")
                    status.start()
            
            # Prepare content parts
            content_parts = []
            
            # Auto-discover relevant files based on dynamic planning
            discovered_files = []
            plan = None  # Initialize plan variable
            
            # Use ExecutionPlanner for dynamic discovery if enabled
            if self.auto_discover_files and not self.context_files:  # Don't override manual files
                status.update("[dim]● Analyzing project context...[/dim]")
                # Create execution plan using AI
                plan = self.execution_planner.create_plan(user_input, verbose=self.verbose_mode)
            
            # Show plan interpretation
            if plan and plan.get('interpretation'):
                status.stop()
                self.console.print(f"[cyan]Understanding: {plan['interpretation']}[/cyan]")
                status.start()
            
            # Process files from the plan
            if plan and plan.get('files_to_analyze'):
                status.update("[dim]● Discovering relevant files...[/dim]")
                for file_spec in plan['files_to_analyze']:
                    pattern = file_spec.get('pattern', '')
                    max_files = file_spec.get('max_files', 10)
                    
                    try:
                        # Handle both simple patterns (*.png) and recursive (**/*.py)
                        if '**' in pattern:
                            matches = list(Path(self.root_path).rglob(pattern.replace('**/', '')))
                        else:
                            matches = list(Path(self.root_path).glob(pattern))
                        
                        # Limit number of files
                        for match in matches[:max_files]:
                            if match.is_file() and match not in discovered_files:
                                discovered_files.append(match)
                                if len(discovered_files) >= 20:  # Overall limit
                                    break
                    except Exception as e:
                        logger.debug(f"Error with pattern {pattern}: {e}")
                    
                    if len(discovered_files) >= 20:
                        break
            
            # Show discovered files (only in verbose mode)
            if discovered_files and self.verbose_mode:
                self.console.print(f"\n● Auto-discovered {len(discovered_files)} relevant files")
                for file in discovered_files[:3]:
                    rel_path = file.relative_to(self.root_path) if hasattr(file, 'relative_to') else file
                    self.console.print(f"  {rel_path}")
                if len(discovered_files) > 3:
                    self.console.print(f"  [dim italic]... +{len(discovered_files) - 3} more files[/dim italic]")
            
            # Add plan info to context if we found useful information
            if plan.get('project_info') or plan.get('analysis_approach'):
                plan_context = []
                if plan.get('project_info'):
                    plan_context.append(f"[Project Analysis]\n{json.dumps(plan['project_info'], indent=2)}")
                if plan.get('analysis_approach'):
                    plan_context.append(f"[Approach]\n{plan['analysis_approach']}")
                if plan_context:
                    content_parts.append("\n\n".join(plan_context))
        
        # Add file context (manual files take precedence over discovered)
        files_to_include = self.context_files if self.context_files else discovered_files
        if files_to_include:
            # Separate text files from image files
            text_files = []
            image_files = []
            for file_path in files_to_include:
                if self.image_handler.is_image_file(file_path):
                    image_files.append(file_path)
                else:
                    text_files.append(file_path)
            
            # Add text files to context
            if text_files:
                status.update(f"[dim]● Reading {len(text_files)} file(s)...[/dim]")
                if self.verbose_mode:
                    status.stop()
                    self.console.print(f"[dim]Including {len(text_files)} text files in context...[/dim]")
                    status.start()
                context = self.file_manager.create_context_from_files(text_files)
                if context:
                    content_parts.append(context)
                    if self.verbose_mode:
                        status.stop()
                        self.console.print(f"[dim]Added {len(context)} characters of file content[/dim]")
                        status.start()
            
            # Add image files to context_images
            if image_files:
                status.stop()
                self.console.print(f"[green]Found {len(image_files)} image(s) to analyze[/green]")
                for img_path in image_files:
                    if img_path not in self.context_images:
                        self.context_images.append(img_path)
                        if self.verbose_mode:
                            rel_path = img_path.relative_to(self.root_path) if hasattr(img_path, 'relative_to') else img_path
                            self.console.print(f"  • {rel_path}")
                status.start()
        
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
        
        # Add plan info to content if we created one
        if plan and plan.get('analysis_approach'):
            # Plan was created, add its approach to context
            approach_context = f"\n[Analysis Approach]\n{plan['analysis_approach']}\n"
            content_parts.insert(0, approach_context)
        
        # Combine text content
        if content_parts:
            text_content = "\n\n".join(content_parts) + f"\n\n{user_input}"
        else:
            text_content = user_input
        
        # Add detected images to context images
        for img_path in detections['image_paths']:
            if img_path not in self.context_images:
                self.context_images.append(img_path)
        
            # Update status before processing images
            if self.context_images:
                status.update("[dim]● Preparing images for analysis...[/dim]")
        
        # End of status context - close it before showing results
        # This ensures the spinner runs during all preparation work
        
        # Check if we have images to include
        if self.context_images:
            # Create multimodal content
            content_blocks = self.image_handler.create_multimodal_content(
                text_content, 
                self.context_images
            )
            
            # Show what images are being sent
            self.console.print(f"[cyan]Sending {len(self.context_images)} image(s) for analysis[/cyan]")
            if self.verbose_mode:
                for img in self.context_images:
                    rel_path = img.relative_to(self.root_path) if hasattr(img, 'relative_to') else img
                    self.console.print(f"  • {rel_path}")
            
            # Clear images after use
            self.context_images = []
            
            # Add to conversation as multimodal
            self.conversation.add_message("user", content_blocks)
        else:
            # Regular text message - but use text_content if we have file context
            if content_parts:
                self.conversation.add_message("user", text_content)
            else:
                self.conversation.add_message("user", user_input)
        
        # Prepare messages for API
        messages = []
        for msg in self.conversation.get_messages():
            # Handle both string and multimodal content
            if isinstance(msg.content, str):
                # Just use the content as-is since we already included files in conversation
                messages.append(Message(role=msg.role, content=msg.content))
            else:
                # Multimodal content
                messages.append(Message(role=msg.role, content=msg.content))
        
        try:
            # Check context before sending
            current_messages = self._prepare_api_messages()
            stats = self.context_manager.get_context_stats(current_messages)
            
            if self.context_manager.should_warn(stats):
                remaining_percent = 100 - stats.usage_percentage
                self.console.print(
                    f"[yellow]Context left until auto-compact: {remaining_percent:.0f}%[/yellow]"
                )
            
            # Show thinking indicator with progress
            response_text = ""
            
            if self.compact_mode:
                # Show progress spinner while generating full response
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
                
                # Display full response (this cleans and processes actions)
                self._display_response(response_text)
                # Note: _display_response already calls _process_actions
            else:
                # Detect query intent for status message
                query_context = self.analyze_query(user_input) if self.smart_context else None
                intent = query_context.intent if query_context else 'general'
                
                # More descriptive status messages
                status_messages = {
                    'debug': '🔍 Analyzing the issue',
                    'implement': '🔨 Crafting solution',
                    'test': '🧪 Preparing tests',
                    'refactor': '♻️ Improving code',
                    'explain': '📚 Formulating explanation',
                    'review': '👀 Reviewing code',
                    'general': '🤔 Processing request'
                }
                status_message = status_messages.get(intent, status_messages['general'])
                
                # Start streaming with Live display
                start_time = time.time()
                
                # Create a status panel that will be updated
                def generate_status():
                    elapsed = time.time() - start_time
                    estimated_tokens = len(response_text) // 4
                    context_percent = 100 - stats.usage_percentage
                    
                    # Build status line with better formatting
                    status_parts = []
                    status_parts.append(f"● {status_message}... ({int(elapsed)}s)")
                    status_parts.append(f"{estimated_tokens/1000:.1f}k tokens")
                    
                    # Context with better visual
                    if context_percent > 30:
                        context_color = "green"
                    elif context_percent > 20:
                        context_color = "yellow"
                    else:
                        context_color = "red"
                    
                    if context_percent <= 30:
                        status_parts.append(f"[{context_color}]Context: {context_percent:.0f}% left[/{context_color}]")
                    
                    status_parts.append("[dim]esc to interrupt[/dim]")
                    
                    return " · ".join(status_parts)
                
                # Use Live display for real-time updates
                with Live(generate_status(), console=self.console, refresh_per_second=4) as live:
                    # Start the stream
                    stream = self.bedrock_client.send_message(messages, self.system_prompt)
                    
                    # Brief pause to show status
                    time.sleep(0.2)
                    
                    # Clear the status and show assistant label
                    live.stop()
                
                # Collect full response first (even in streaming mode)
                # This allows proper cleaning before display
                for chunk in stream:
                    response_text += chunk
                
                # Now display the cleaned response
                self.console.print("\n[dim]Assistant:[/dim]")
                self._display_response(response_text)
            
            # Add to conversation history (with original response for context)
            self.conversation.add_message("assistant", response_text)
            
        except Exception as e:
            from rich.markup import escape
            self.console.print(f"\n[red]Error: {escape(str(e))}[/red]")
    
    def _display_response(self, response: str):
        """Display response with proper formatting and action detection."""
        # Store original for /expand command
        self.last_response = response
        
        # Process the response to clean it
        processed = self.response_processor.process(response)
        display_response = self.response_processor.format_for_display(processed)
        
        # Always show the full AI response - don't collapse the actual answer
        try:
            md = Markdown(display_response)
            self.console.print(md)
        except Exception:
            # Fallback to plain text
            self.console.print(display_response)
        
        # Process actions (pass original response)
        self._process_actions(response)
    
    def _process_and_display_actions(self, response: str):
        """Process actions and display them as todos."""
        # Process actions (this will handle both structured and unstructured)
        self._process_actions(response)
    
    def _process_actions(self, response: str):
        """Extract and process actions from the response."""
        # First try to extract structured actions
        structured_actions, clean_response = self.action_parser.extract_actions(response)
        
        if structured_actions:
            # Convert structured actions to todos
            file_actions = []
            command_actions = []
            
            for action in structured_actions:
                if action.action_type == 'file':
                    from .action_executor import FileAction
                    file_actions.append(FileAction(
                        action_type='create',
                        file_path=Path(action.content['path']),
                        content=action.content['content'],
                        language=None
                    ))
                elif action.action_type == 'command':
                    from .action_executor import CommandAction
                    command_actions.append(CommandAction(
                        command=action.content['command'],
                        description=action.description
                    ))
            
            # Convert to todos
            self.action_todos = self.action_executor.actions_to_todos(file_actions, command_actions)
            
            # Display as todo list
            self.structured_output.display_action_todos(self.action_todos)
            
            # Show quick execute option
            if self.action_todos:
                self.console.print("\n[cyan]Quick actions:[/cyan]")
                self.console.print("  • Press [bold]Enter[/bold] to execute next action")
                self.console.print("  • Type [bold]/todo all[/bold] to execute all at once")
                self.console.print("  • Type [bold]/todo skip[/bold] to skip current action")
                
        else:
            # Check if response looks like it has unstructured actions
            if self.action_parser.detect_unstructured_actions(response):
                # Try regex-based extraction
                file_actions, command_actions = self.action_executor.extract_actions_from_response(response)
                
                if file_actions or command_actions:
                    # Convert to todos
                    self.action_todos = self.action_executor.actions_to_todos(file_actions, command_actions)
                    
                    # Display as todo list
                    self.structured_output.display_action_todos(self.action_todos)
                    
                    # Show hint
                    self.console.print("\n[yellow]💡 Tip: Actions detected from response[/yellow]")
                    self.console.print("[cyan]Press Enter to start executing, or type a command[/cyan]")
    
    def _confirm_action(self, prompt: str) -> bool:
        """Ask for confirmation with a yes/no prompt."""
        from rich.prompt import Confirm
        return Confirm.ask(prompt, default=True)
    
    def _execute_structured_actions(self, actions: List[Any]):
        """Execute structured actions step by step."""
        from rich.prompt import Confirm
        
        for i, action in enumerate(actions):
            self.console.print(f"\n[bold]Step {i+1} of {len(actions)}:[/bold]")
            self.console.print(f"[cyan]{action.description}[/cyan]")
            
            if action.action_type == 'command':
                self.console.print(f"Command: [yellow]{action.content['command']}[/yellow]")
                if Confirm.ask("Execute this command?", default=True):
                    # Execute the command
                    import subprocess
                    try:
                        result = subprocess.run(
                            action.content['command'],
                            shell=True,
                            capture_output=True,
                            text=True,
                            cwd=self.root_path
                        )
                        if result.returncode == 0:
                            self.console.print("[green]✓ Command executed successfully[/green]")
                            if result.stdout:
                                self.console.print(f"[dim]{result.stdout}[/dim]")
                        else:
                            self.console.print(f"[red]✗ Command failed[/red]")
                            if result.stderr:
                                self.console.print(f"[red]{result.stderr}[/red]")
                    except Exception as e:
                        from rich.markup import escape
                        self.console.print(f"[red]Error: {escape(str(e))}[/red]")
                else:
                    self.console.print("[yellow]Skipped[/yellow]")
                    
            elif action.action_type == 'file':
                file_path = self.root_path / action.content['path']
                self.console.print(f"File: [green]{action.content['path']}[/green]")
                
                # Show content preview
                content = action.content['content']
                lines = content.split('\\n')
                preview_lines = lines[:5]
                if len(lines) > 5:
                    self.console.print("[dim]Content preview:[/dim]")
                    for line in preview_lines:
                        self.console.print(f"[dim]  {line}[/dim]")
                    self.console.print(f"[dim]  ... ({len(lines) - 5} more lines)[/dim]")
                else:
                    self.console.print("[dim]Content:[/dim]")
                    for line in lines:
                        self.console.print(f"[dim]  {line}[/dim]")
                
                if Confirm.ask("Create this file?", default=True):
                    try:
                        # Create parent directories
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        # Write file
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        self.console.print(f"[green]✓ Created: {action.content['path']}[/green]")
                    except Exception as e:
                        from rich.markup import escape
                        self.console.print(f"[red]Error creating file: {escape(str(e))}[/red]")
                else:
                    self.console.print("[yellow]Skipped[/yellow]")
    
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
        screenshot_capture = self._get_screenshot_capture()
        if not screenshot_capture:
            self.console.print("[red]Screenshot capture is not available[/red]")
            self.console.print("[yellow]Install with: pip install pyautogui[/yellow]")
            return
            
        try:
            self.console.print("[dim]Capturing screenshot...[/dim]")
            
            # Capture screenshot
            screenshot_path = screenshot_capture.capture_screenshot()
            
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
                self.console.print("\n● Auto-compacting conversation history...")
                messages = self.context_manager.compact_messages(messages)
                
                # Show new stats
                new_stats = self.context_manager.get_context_stats(messages)
                saved_tokens = stats.total_tokens - new_stats.total_tokens
                self.console.print(
                    f"  [green]✓ Freed {saved_tokens:,} tokens "
                    f"({100 - new_stats.usage_percentage:.0f}% context available)[/green]\n"
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
                    # Format like Claude Code
                    self.console.print(f"● Bash(cd {command[3:].strip()})")
                    self.console.print(f"  [green]✓ Changed to {os.getcwd()}[/green]")
                    return
                except Exception as e:
                    self.console.print(f"● Bash(cd {command[3:].strip()})")
                    self.console.print(f"  [red]✗ Failed: {e}[/red]")
                    return
            
            # Show command execution in Claude Code style
            self.console.print(f"● Bash({command})")
            self.console.print(f"  [dim]Running...[/dim]")
            
            # Execute command with a timeout
            import subprocess
            start_time = time.time()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=os.getcwd()
            )
            elapsed = time.time() - start_time
            
            # Format output
            output_lines = []
            if result.stdout:
                from rich.markup import escape
                output_lines.extend([escape(line) for line in result.stdout.rstrip().split('\n')])
            if result.stderr:
                from rich.markup import escape
                output_lines.extend([f"[red]{escape(line)}[/red]" for line in result.stderr.rstrip().split('\n')])
            
            # Show collapsible output
            if len(output_lines) > 3:
                # Show first 3 lines
                for line in output_lines[:3]:
                    self.console.print(f"  {line}")
                remaining = len(output_lines) - 3
                self.console.print(f"  [dim italic]... +{remaining} lines (ctrl+r to expand)[/dim italic]")
            else:
                # Show all lines if 3 or fewer
                for line in output_lines:
                    self.console.print(f"  {line}")
            
            # Show status
            if result.returncode == 0:
                self.console.print(f"  [green]✓ Completed in {elapsed:.1f}s[/green]")
            else:
                self.console.print(f"  [red]✗ Exit code: {result.returncode}[/red]")
            
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
    
    def _execute_action_todo(self, todo: TodoItem):
        """Execute a single action todo."""
        if todo.status != "pending":
            self.console.print(f"[yellow]Action already {todo.status}[/yellow]")
            return
        
        # Update status to in_progress
        todo.status = "in_progress"
        self.structured_output.display_action_todos(self.action_todos)
        
        # Execute based on type
        success = False
        try:
            if todo.metadata and todo.metadata['type'] == 'command':
                success = self.action_executor.execute_command(todo.metadata['action'])
            elif todo.metadata and todo.metadata['type'] == 'file':
                # Show confirmation for file creation
                action = todo.metadata['action']
                try:
                    rel_path = action.file_path.relative_to(self.root_path)
                except ValueError:
                    rel_path = action.file_path
                
                self.console.print(f"\n[cyan]Creating file: {rel_path}[/cyan]")
                
                # Show content preview
                if hasattr(action, 'content') and action.content:
                    lines = action.content.strip().split('\n')
                    if len(lines) <= 10:
                        self.console.print("[dim]Content:[/dim]")
                        for line in lines:
                            self.console.print(f"  [dim]{line}[/dim]")
                    else:
                        self.console.print("[dim]Content preview:[/dim]")
                        for line in lines[:5]:
                            self.console.print(f"  [dim]{line}[/dim]")
                        self.console.print(f"  [dim]... ({len(lines) - 5} more lines)[/dim]")
                
                if self._confirm_action("Create this file?"):
                    success = self.action_executor.execute_file_action(action)
                else:
                    self.console.print("[yellow]Skipped[/yellow]")
                    todo.status = "pending"
                    return
                    
            # Update status
            todo.status = "completed" if success else "failed"
            if not success and not todo.error:
                todo.error = "Execution failed"
                
        except Exception as e:
            from rich.markup import escape
            todo.status = "failed"
            todo.error = str(e)
            self.console.print(f"[red]Error: {escape(str(e))}[/red]")
        
        # Refresh display
        self.structured_output.display_action_todos(self.action_todos)
        
        # If there are more todos, show hint
        remaining = [t for t in self.action_todos if t.status == "pending"]
        if remaining:
            self.console.print(f"\n[dim]{len(remaining)} actions remaining. Press Enter to continue.[/dim]")
    
    def _execute_action_todo_by_number(self, number: str):
        """Execute a specific action todo by number."""
        try:
            idx = int(number) - 1
            if 0 <= idx < len(self.action_todos):
                self._execute_action_todo(self.action_todos[idx])
            else:
                self.console.print("[red]Invalid action number[/red]")
        except ValueError:
            self.console.print("[red]Please provide a valid number[/red]")
    
    def _execute_all_action_todos(self):
        """Execute all pending action todos."""
        pending = [t for t in self.action_todos if t.status == "pending"]
        if not pending:
            self.console.print("[yellow]No pending actions to execute[/yellow]")
            return
        
        self.console.print(f"\n[cyan]Executing {len(pending)} actions...[/cyan]")
        
        for todo in pending:
            self._execute_action_todo(todo)
            # Small pause between actions
            if todo.status == "completed":
                time.sleep(0.1)
    
    def _skip_next_action_todo(self):
        """Skip the next pending action todo."""
        next_todo = next((t for t in self.action_todos if t.status == "pending"), None)
        if next_todo:
            next_todo.status = "completed"
            next_todo.result = "Skipped by user"
            self.console.print(f"[yellow]Skipped: {next_todo.content}[/yellow]")
            self.structured_output.display_action_todos(self.action_todos)
        else:
            self.console.print("[yellow]No pending actions to skip[/yellow]")
    
    def _show_action_todos(self):
        """Show current action todos."""
        if self.action_todos:
            self.structured_output.display_action_todos(self.action_todos)
        else:
            self.console.print("[yellow]No actions in queue[/yellow]")
    
    def _show_todos(self):
        """Extract and show tasks/todos from conversation."""
        import re
        
        # Extract todos from conversation
        extracted_todos = self._extract_todos_from_conversation()
        
        # Convert to TodoItem objects
        todo_items = []
        for i, (todo_text, priority) in enumerate(extracted_todos[:20]):
            todo_item = TodoItem(
                id=f"todo_{i+1}",
                content=todo_text,
                status="pending",
                priority=priority
            )
            todo_items.append(todo_item)
        
        if todo_items:
            # Update and display using structured output
            self.structured_output.update_todos(todo_items)
            
            # Store for future reference
            self.current_todos = todo_items
            
            # Show additional context
            if len(extracted_todos) > 20:
                self.console.print(f"\n[dim]... and {len(extracted_todos) - 20} more tasks found[/dim]")
        else:
            self.console.print("[yellow]No specific tasks found in conversation[/yellow]")
            self.console.print("[dim]Tip: I look for TODO markers, checkboxes, numbered lists, and action phrases[/dim]")
    
    def _extract_todos_from_conversation(self) -> List[Tuple[str, str]]:
        """Extract todos from conversation history.
        
        Returns:
            List of (todo_text, priority) tuples
        """
        import re
        
        todos = []
        messages = self.conversation.get_messages()
        
        # Patterns to find todos/tasks with priority hints
        high_priority_patterns = [
            r'(?:URGENT|CRITICAL|IMPORTANT|ASAP):\s*(.+)',
            r'(?:must|need to)\s+immediately\s+(.+?)(?:\.|$)',
        ]
        
        medium_priority_patterns = [
            r'(?:TODO|TASK|FIXME):\s*(.+)',
            r'(?:^|\n)\s*[-*]\s*\[\s*\]\s*(.+)',  # Markdown checkboxes
            r'(?:should|need to|must)\s+(.+?)(?:\.|$)',
        ]
        
        low_priority_patterns = [
            r'(?:^|\n)\s*\d+\.\s*(.+?)(?:\n|$)',  # Numbered lists
            r'(?:could|might want to|consider)\s+(.+?)(?:\.|$)',
        ]
        
        for msg in messages[-10:]:  # Only look at recent messages
            if msg.role == 'assistant':
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                
                # Check high priority patterns
                for pattern in high_priority_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                    for match in matches:
                        task = match.strip()
                        if 10 < len(task) < 200:
                            todos.append((task, "high"))
                
                # Check medium priority patterns
                for pattern in medium_priority_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                    for match in matches:
                        task = match.strip()
                        if 10 < len(task) < 200:
                            todos.append((task, "medium"))
                
                # Check low priority patterns
                for pattern in low_priority_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                    for match in matches:
                        task = match.strip()
                        if 10 < len(task) < 200:
                            todos.append((task, "low"))
        
        # Remove duplicates while preserving order and priority
        seen = set()
        unique_todos = []
        for todo, priority in todos:
            if todo.lower() not in seen:
                seen.add(todo.lower())
                unique_todos.append((todo, priority))
        
        return unique_todos
    
    def _analyze_project_context(self):
        """Analyze the current directory as a code project."""
        try:
            from .project_analyzer import ProjectAnalyzer
            
            # Create a dedicated analyzer  
            analyzer = ProjectAnalyzer(self.root_path)
            self.project_analyzer = analyzer
            self.project_info = self.project_analyzer.analyze_project()
            
            # Get project summary
            self.project_summary = self.project_analyzer.get_project_summary()
            
            # Pre-load relevant files based on project type
            if self.project_info.main_directories:
                # Find main entry points
                entry_files = []
                for main_dir in self.project_info.main_directories[:2]:  # Limit to first 2 directories
                    # Look for common entry points
                    patterns = ['main.*', 'app.*', 'index.*', '__main__.*']
                    for pattern in patterns:
                        for file_path in main_dir.glob(pattern):
                            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.java', '.go']:
                                entry_files.append(file_path)
                                if len(entry_files) >= 3:
                                    break
                
                # Pre-load these files silently
                if entry_files:
                    for file_path in entry_files[:3]:
                        try:
                            content = self.file_manager.read_file(file_path)
                            if content:
                                self.context_files[str(file_path)] = content
                        except Exception:
                            pass
            
            # Update system prompt with project context
            self._update_system_prompt_with_project()
            
        except Exception as e:
            logger.warning(f"Project analysis failed: {e}")
            # Escape the error message to prevent markup issues
            from rich.markup import escape
            self.console.print(f"[yellow]Project analysis failed: {escape(str(e))}[/yellow]")
            self.project_summary = None
            self.project_analyzer = None
    
    def _update_system_prompt_with_project(self):
        """Update the system prompt to include project context."""
        if not self.project_analyzer or not self.project_summary:
            return
        
        # Get base system prompt
        base_prompt = self.bedrock_client.get_default_system_prompt(interactive=True)
        
        # Add project-specific context
        project_context = f"""\n\nYou are operating in a {self.project_info.project_type} project.\n{self.project_summary}\n\nCRITICAL INSTRUCTIONS - YOU ARE AN INTELLIGENT CODING AGENT:

1. NEVER ask clarifying questions - make intelligent assumptions and take action
2. When the user mentions "my" ANYTHING - they mean the code in the current directory
3. Create actionable TODO lists and concrete recommendations, not questions
4. If the user's intent is unclear, interpret it in the most helpful way possible
5. Always analyze included files thoroughly and provide specific feedback
6. Be extremely proactive - if you think the user might want something, just do it
7. Focus on actual code in the files, not generic advice

BEHAVIORAL RULES:
- User asks about "my application" → Analyze their actual code files
- User wants "recommendations" → Provide a numbered list of specific improvements
- User seems stuck → Create a step-by-step action plan
- Query is vague → Interpret generously and provide comprehensive help

You are not a question-asking assistant. You are a problem-solving coding agent.
When in doubt, analyze code and provide solutions, don't ask for clarification.

CRITICAL: If files are included in the context, you MUST analyze them and provide specific recommendations.
NEVER say "I need more information" or "Could you share your code" when files are already provided.
The files in the context ARE the user's application - analyze them immediately."""
        
        # Update system prompt
        self.system_prompt = base_prompt + project_context
    
    def _mark_todo_done(self, todo_num: str):
        """Mark a todo as completed."""
        try:
            num = int(todo_num) - 1
            if 0 <= num < len(self.current_todos):
                self.current_todos[num].status = "completed"
                self.console.print(f"[green]✓ Marked todo #{num + 1} as completed:[/green]")
                self.console.print(f"  {self.current_todos[num].format()}")
                
                # Show updated todo list
                self.structured_output.update_todos(self.current_todos)
            else:
                self.console.print(f"[red]Invalid todo number. Use /todo to see the list.[/red]")
        except ValueError:
            self.console.print("[red]Please provide a valid number.[/red]")
    
    def _show_project_info(self):
        """Show project analysis information."""
        if not self.project_analyzer:
            self.console.print("[yellow]No project analysis available[/yellow]")
            self.console.print("[dim]Try restarting to analyze the project[/dim]")
            return
        
        # Get detailed project info
        info = self.project_analyzer.project_info
        
        # Create a nice display
        self.console.print("\n[bold blue]Project Analysis[/bold blue]")
        self.console.print(f"[cyan]{self.project_summary}[/cyan]\n")
        
        # Show build files
        if info.build_files:
            self.console.print("[bold]Build Files:[/bold]")
            for file in info.build_files[:5]:
                self.console.print(f"  • {file.relative_to(info.root_path)}")
        
        # Show config files
        if info.config_files:
            self.console.print("\n[bold]Config Files:[/bold]")
            for file in info.config_files[:5]:
                self.console.print(f"  • {file.relative_to(info.root_path)}")
        
        # Show test directories
        if info.test_directories:
            self.console.print("\n[bold]Test Directories:[/bold]")
            for dir in info.test_directories:
                self.console.print(f"  • {dir.relative_to(info.root_path)}")
        
        # Suggest actions
        self.console.print("\n[dim]Tip: I can automatically analyze your code when you ask questions![/dim]")
    
    def _toggle_autodiscover(self):
        """Toggle automatic file discovery."""
        self.auto_discover_files = not self.auto_discover_files
        status = "enabled" if self.auto_discover_files else "disabled"
        self.console.print(f"[green]Automatic file discovery {status}[/green]")
        
        if self.auto_discover_files:
            self.console.print("[dim]I'll automatically find relevant files when you ask about code[/dim]")
        else:
            self.console.print("[dim]Use /files to manually add files to context[/dim]")
    
    def _show_expanded_response(self):
        """Show the last response with all sections expanded."""
        if not self.last_response:
            self.console.print("[yellow]No previous response to show[/yellow]")
            return
        
        # Responses are now shown in full by default
        self.console.print("[dim]Note: Responses are now displayed in full by default.[/dim]")
        self.console.print("[dim]The /expand command is no longer needed.[/dim]")