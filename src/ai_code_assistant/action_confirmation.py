"""Action confirmation dialogs with Claude Code-style presentation."""

from typing import Optional, List, Tuple
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.box import ROUNDED
from rich.text import Text
from rich.columns import Columns
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.formatted_text import HTML


class ActionConfirmation:
    """Provides Claude Code-style confirmation dialogs for actions."""
    
    def __init__(self, console: Console):
        """Initialize confirmation dialog handler.
        
        Args:
            console: Rich console for output
        """
        self.console = console
        
    def confirm_file_action(self, action_type: str, file_path: Path, 
                          content: Optional[str] = None, 
                          language: Optional[str] = None) -> Tuple[bool, bool]:
        """Show confirmation dialog for file action.
        
        Args:
            action_type: Type of action (create, edit, delete)
            file_path: Path to file
            content: File content for create/edit
            language: Language for syntax highlighting
            
        Returns:
            Tuple of (confirmed, dont_ask_again)
        """
        # Create the confirmation panel
        title = f"{action_type.title()} file"
        
        # Build content preview
        content_lines = []
        
        # Show file path prominently
        content_lines.append(f"[bold cyan]{file_path}[/bold cyan]\n")
        
        if content and action_type != 'delete':
            lines = content.split('\n')
            total_lines = len(lines)
            
            # For short files, show all content
            if total_lines <= 20:
                if language:
                    syntax = Syntax(content, language, theme="monokai", 
                                  line_numbers=True, word_wrap=False)
                    content_lines.append(syntax)
                else:
                    for i, line in enumerate(lines, 1):
                        content_lines.append(f"  {i:3d}  {line}")
            else:
                # For longer files, show preview with context
                preview_lines = []
                
                # Show first 10 lines
                preview_lines.extend(lines[:10])
                preview_lines.append("")
                preview_lines.append(f"  ... ({total_lines - 15} lines hidden) ...")
                preview_lines.append("")
                # Show last 5 lines
                preview_lines.extend(lines[-5:])
                
                preview_content = '\n'.join(preview_lines)
                
                if language:
                    syntax = Syntax(preview_content, language, theme="monokai",
                                  line_numbers=False, word_wrap=False)
                    content_lines.append(syntax)
                else:
                    content_lines.append(preview_content)
        
        # Create the main panel
        panel_content = "\n".join(str(c) for c in content_lines)
        panel = Panel(
            panel_content,
            title=f"[bold]{title}[/bold]",
            border_style="blue",
            box=ROUNDED,
            padding=(1, 2),
            expand=True
        )
        
        self.console.print(panel)
        
        # Show the action question
        question = f"Do you want to {action_type} this file?"
        self.console.print(f"\n{question}")
        
        # Create key bindings for the options
        kb = KeyBindings()
        result = {'choice': None}
        
        @kb.add('1')
        @kb.add('y')
        @kb.add(Keys.ControlM)  # Enter
        def yes(event):
            result['choice'] = 1
            event.app.exit()
            
        @kb.add('2')
        @kb.add(Keys.Tab)
        def yes_dont_ask(event):
            result['choice'] = 2
            event.app.exit()
            
        @kb.add('3')
        @kb.add('n')
        @kb.add(Keys.Escape)
        def no(event):
            result['choice'] = 3
            event.app.exit()
        
        # Show options
        options = [
            "[bold]1. Yes[/bold]",
            "[dim]2. Yes, and don't ask again this session (tab)[/dim]",
            "[dim]3. No (esc)[/dim]"
        ]
        
        for opt in options:
            self.console.print(f"  {opt}")
        
        # Get user choice
        try:
            prompt("", key_bindings=kb)
            choice = result['choice'] or 3  # Default to No
        except (KeyboardInterrupt, EOFError):
            choice = 3
        
        # Return based on choice
        if choice == 1:
            return True, False
        elif choice == 2:
            return True, True
        else:
            return False, False
    
    def confirm_command_action(self, command: str, description: Optional[str] = None) -> Tuple[bool, bool]:
        """Show confirmation dialog for command execution.
        
        Args:
            command: Command to execute
            description: Optional description
            
        Returns:
            Tuple of (confirmed, dont_ask_again)
        """
        # Create the command panel
        panel_content = f"[bold yellow]$ {command}[/bold yellow]"
        
        if description:
            panel_content = f"{description}\n\n{panel_content}"
        
        panel = Panel(
            panel_content,
            title="[bold]Execute command[/bold]",
            border_style="yellow",
            box=ROUNDED,
            padding=(1, 2),
            expand=True
        )
        
        self.console.print(panel)
        
        # Show the action question
        self.console.print("\nDo you want to execute this command?")
        
        # Create key bindings
        kb = KeyBindings()
        result = {'choice': None}
        
        @kb.add('1')
        @kb.add('y')
        @kb.add(Keys.ControlM)  # Enter
        def yes(event):
            result['choice'] = 1
            event.app.exit()
            
        @kb.add('2')
        @kb.add(Keys.Tab)
        def yes_dont_ask(event):
            result['choice'] = 2
            event.app.exit()
            
        @kb.add('3')
        @kb.add('n')
        @kb.add(Keys.Escape)
        def no(event):
            result['choice'] = 3
            event.app.exit()
        
        # Show options
        options = [
            "[bold]1. Yes[/bold]",
            "[dim]2. Yes, and don't ask again this session (tab)[/dim]",
            "[dim]3. No (esc)[/dim]"
        ]
        
        for opt in options:
            self.console.print(f"  {opt}")
        
        # Get user choice
        try:
            prompt("", key_bindings=kb)
            choice = result['choice'] or 3  # Default to No
        except (KeyboardInterrupt, EOFError):
            choice = 3
        
        # Return based on choice
        if choice == 1:
            return True, False
        elif choice == 2:
            return True, True
        else:
            return False, False
    
    def confirm_multiple_actions(self, file_actions: List, command_actions: List) -> Tuple[bool, bool]:
        """Show confirmation for multiple actions at once.
        
        Args:
            file_actions: List of file actions
            command_actions: List of command actions
            
        Returns:
            Tuple of (confirmed, dont_ask_again)
        """
        # Create summary table
        table = Table(title="Actions Summary", box=ROUNDED, expand=True)
        table.add_column("Type", style="cyan", width=10)
        table.add_column("Action", style="white")
        table.add_column("Target", style="yellow")
        
        # Add file actions
        for action in file_actions:
            table.add_row(
                "File",
                action.action_type.title(),
                str(action.file_path)
            )
        
        # Add command actions
        for action in command_actions:
            table.add_row(
                "Command",
                "Execute",
                action.command[:50] + "..." if len(action.command) > 50 else action.command
            )
        
        self.console.print(table)
        
        # Show total count
        total = len(file_actions) + len(command_actions)
        self.console.print(f"\n[bold]Total: {total} action{'s' if total != 1 else ''}[/bold]")
        
        # Ask for confirmation
        self.console.print("\nDo you want to execute all these actions?")
        
        # Create key bindings
        kb = KeyBindings()
        result = {'choice': None}
        
        @kb.add('1')
        @kb.add('y')
        @kb.add(Keys.ControlM)  # Enter
        def yes(event):
            result['choice'] = 1
            event.app.exit()
            
        @kb.add('2')
        @kb.add(Keys.Tab)
        def yes_dont_ask(event):
            result['choice'] = 2
            event.app.exit()
            
        @kb.add('3')
        @kb.add('n')
        @kb.add(Keys.Escape)
        def no(event):
            result['choice'] = 3
            event.app.exit()
        
        # Show options
        options = [
            "[bold]1. Yes, execute all[/bold]",
            "[dim]2. Yes, and don't ask again this session (tab)[/dim]",
            "[dim]3. No, cancel all (esc)[/dim]"
        ]
        
        for opt in options:
            self.console.print(f"  {opt}")
        
        # Get user choice
        try:
            prompt("", key_bindings=kb)
            choice = result['choice'] or 3  # Default to No
        except (KeyboardInterrupt, EOFError):
            choice = 3
        
        # Return based on choice
        if choice == 1:
            return True, False
        elif choice == 2:
            return True, True
        else:
            return False, False