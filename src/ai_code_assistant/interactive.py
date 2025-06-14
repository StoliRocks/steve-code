"""Interactive mode for the AI Code Assistant."""

import sys
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
        '/files': 'Add files to context',
        '/status': 'Show current status',
        '/model': 'Switch model (sonnet-4, sonnet-3.7, opus-4)',
        '/export': 'Export conversation (json/markdown)',
        '/code': 'Extract and save code blocks',
        '/tree': 'Show directory tree',
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
    
    def _create_prompt_style(self) -> Style:
        """Create prompt style."""
        return Style.from_dict({
            'prompt': '#00aa00 bold',
        })
    
    def run(self):
        """Run the interactive mode."""
        self._show_welcome()
        
        while True:
            try:
                # Get user input
                user_input = self.session.prompt(
                    "\n>>> ",
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
        status = f"""[bold]Current Status:[/bold]

Model: [green]{self.bedrock_client.model_type.name}[/green]
Messages: [yellow]{len(self.conversation.messages)}[/yellow]
Context Files: [yellow]{len(self.context_files)}[/yellow]
Context Images: [yellow]{len(self.context_images)}[/yellow]
Compact Mode: [yellow]{'On' if self.compact_mode else 'Off'}[/yellow]
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
            
            else:
                self.console.print(f"[red]Unknown setting: {key}[/red]")
                self.console.print("[yellow]Available keys: temperature, max_tokens, region, auto_detect[/yellow]")
        
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
        
        # Add file context if any
        if self.context_files:
            context = self.file_manager.create_context_from_files(self.context_files)
            content_parts.append(context)
        
        # Auto-fetch URLs if detected
        if detections['urls']:
            url_contents = []
            for url in detections['urls']:
                self.console.print(f"[dim]Fetching {url}...[/dim]")
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
                # Stream directly to console in normal mode
                self.console.print("[dim]Assistant:[/dim]")
                for chunk in self.bedrock_client.send_message(messages, self.system_prompt):
                    response_text += chunk
                    self.console.print(chunk, end="")
                self.console.print()  # New line after streaming
            
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