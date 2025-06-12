"""Interactive mode for the AI Code Assistant."""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text

from .bedrock_client import BedrockClient, ModelType, Message
from .conversation import ConversationHistory
from .code_extractor import CodeExtractor
from .file_context import FileContextManager
from .config import ConfigManager


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
        '/set': 'Set a configuration value (temperature, max_tokens, region)',
        '/config': 'Save current settings to config file',
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
        
        # Prompt session with history
        history_file = Path.home() / ".steve_code" / "prompt_history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            style=self._create_prompt_style()
        )
        
        # System prompt
        self.system_prompt = (
            "You are an AI coding assistant. You help with programming tasks, "
            "code review, debugging, and technical questions. You can analyze "
            "code, suggest improvements, and explain complex concepts clearly."
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
Compact Mode: [yellow]{'On' if self.compact_mode else 'Off'}[/yellow]
Session ID: [dim]{self.conversation.session_id}[/dim]"""
        
        if self.context_files:
            status += "\n\n[bold]Context Files:[/bold]"
            for file in self.context_files:
                status += f"\n  • {file}"
        
        self.console.print(Panel(status, title="Status", border_style="blue"))
    
    def _show_settings(self):
        """Show current settings."""
        settings = f"""[bold]Current Settings:[/bold]

Model: [green]{self.bedrock_client.model_type.value}[/green]
Region: [yellow]{self.bedrock_client.region_name}[/yellow]
Max Tokens: [yellow]{self.bedrock_client.max_tokens}[/yellow]
Temperature: [yellow]{self.bedrock_client.temperature}[/yellow]
Compact Mode: [yellow]{'Enabled' if self.compact_mode else 'Disabled'}[/yellow]

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
                if 1 <= tokens <= 100000:
                    self.bedrock_client.max_tokens = tokens
                    self.console.print(f"[green]Max tokens set to {tokens}[/green]")
                else:
                    self.console.print("[red]Max tokens must be between 1 and 100000[/red]")
            
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
            
            else:
                self.console.print(f"[red]Unknown setting: {key}[/red]")
                self.console.print("[yellow]Available keys: temperature, max_tokens, region[/yellow]")
        
        except ValueError as e:
            self.console.print(f"[red]Invalid value: {e}[/red]")
    
    def _save_config(self):
        """Save current settings to configuration file."""
        # Map model type to string
        model_map_reverse = {
            ModelType.CLAUDE_4_SONNET: 'sonnet-4',
            ModelType.CLAUDE_3_7_SONNET: 'sonnet-3.7',
            ModelType.CLAUDE_4_OPUS: 'opus-4',
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
            'sonnet-4': ModelType.CLAUDE_4_SONNET,
            'sonnet-3.7': ModelType.CLAUDE_3_7_SONNET,
            'opus-4': ModelType.CLAUDE_4_OPUS,
        }
        
        if not model_name:
            self.console.print("[yellow]Available models: sonnet-4, sonnet-3.7, opus-4[/yellow]")
            return
        
        model_type = model_map.get(model_name.lower())
        if model_type:
            self.bedrock_client.switch_model(model_type)
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
        # Add file context if any
        full_input = user_input
        if self.context_files:
            context = self.file_manager.create_context_from_files(self.context_files)
            full_input = f"{context}\n\n{user_input}"
        
        # Add to conversation history
        self.conversation.add_message("user", user_input)
        
        # Prepare messages for API
        messages = [
            Message(role=msg.role, content=msg.content)
            for msg in self.conversation.get_messages()
        ]
        
        # If we have file context, modify the last message
        if self.context_files and messages:
            messages[-1] = Message(role="user", content=full_input)
        
        try:
            # Show thinking indicator
            self.console.print("[dim]Thinking...[/dim]", end="")
            
            # Get response from Bedrock
            response_text = ""
            for chunk in self.bedrock_client.send_message(messages, self.system_prompt):
                response_text += chunk
                if not self.compact_mode:
                    self.console.print(chunk, end="")
            
            if self.compact_mode:
                # Clear thinking indicator
                self.console.print("\r" + " " * 20 + "\r", end="")
                # Display full response
                self._display_response(response_text)
            else:
                self.console.print()  # New line after streaming
            
            # Add to conversation history
            self.conversation.add_message("assistant", response_text)
            
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
    
    def _display_response(self, response: str):
        """Display response with proper formatting."""
        # Try to render as markdown
        try:
            md = Markdown(response)
            self.console.print(md)
        except Exception:
            # Fallback to plain text
            self.console.print(response)