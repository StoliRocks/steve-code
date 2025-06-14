"""Action executor for automatically performing tasks from AI responses."""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

from .code_extractor import CodeBlock, CodeExtractor


@dataclass
class FileAction:
    """Represents a file creation/modification action."""
    action_type: str  # 'create', 'modify', 'delete'
    file_path: Path
    content: Optional[str] = None
    language: Optional[str] = None
    

@dataclass 
class CommandAction:
    """Represents a command to execute."""
    command: str
    description: Optional[str] = None
    working_dir: Optional[Path] = None


class ActionExecutor:
    """Executes actions extracted from AI responses."""
    
    def __init__(self, console: Console, root_path: Path = None):
        """Initialize the action executor.
        
        Args:
            console: Rich console for output
            root_path: Root directory for file operations
        """
        self.console = console
        self.root_path = root_path or Path.cwd()
        self.code_extractor = CodeExtractor()
        
    def extract_actions_from_response(self, response: str) -> Tuple[List[FileAction], List[CommandAction]]:
        """Extract file and command actions from an AI response.
        
        Args:
            response: The AI response text
            
        Returns:
            Tuple of (file_actions, command_actions)
        """
        file_actions = []
        command_actions = []
        
        # Extract code blocks that look like file contents
        code_blocks = self.code_extractor.extract_code_blocks(response)
        
        # Look for file path indicators before code blocks
        lines = response.split('\n')
        used_blocks = set()  # Track which code blocks we've assigned
        
        for i, line in enumerate(lines):
            # Match patterns like "### package.json" or "**lib/lambda/app.py**" or "lib/lambda/app.py"
            file_patterns = [
                r'^#{1,3}\s*(.+?)$',        # ### filename
                r'^\*{2}(.+?)\*{2}$',        # **filename**
                r'^`(.+?)`$',                # `filename`
                r'^(.+?):?\s*$',             # filename: or just filename
            ]
            
            potential_path = None
            for pattern in file_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    potential_path = match.group(1).strip().rstrip(':')
                    break
            
            if potential_path:
                # Check if it looks like a file path
                if ('.' in potential_path and not potential_path.startswith('#')) or '/' in potential_path:
                    # Look for the next unused code block
                    for j, block in enumerate(code_blocks):
                        if j not in used_blocks and (not block.line_number or block.line_number > i):
                            # This code block likely belongs to this file
                            file_path = self.root_path / potential_path
                            file_actions.append(FileAction(
                                action_type='create',
                                file_path=file_path,
                                content=block.content,
                                language=block.language
                            ))
                            used_blocks.add(j)
                            break
        
        # Extract bash/shell commands
        bash_pattern = r'```(?:bash|sh|shell)\s*\n(.*?)```'
        bash_matches = re.findall(bash_pattern, response, re.DOTALL)
        
        for match in bash_matches:
            commands = match.strip().split('\n')
            for cmd in commands:
                cmd = cmd.strip()
                if cmd and not cmd.startswith('#'):
                    # Check if it's a file operation command
                    if any(op in cmd for op in ['mkdir', 'touch', 'cp', 'mv']):
                        command_actions.append(CommandAction(
                            command=cmd,
                            description="File system operation"
                        ))
        
        return file_actions, command_actions
    
    def display_actions_summary(self, file_actions: List[FileAction], 
                               command_actions: List[CommandAction]) -> bool:
        """Display a summary of actions and ask for confirmation.
        
        Args:
            file_actions: List of file actions
            command_actions: List of command actions
            
        Returns:
            True if user confirms, False otherwise
        """
        if not file_actions and not command_actions:
            return False
            
        self.console.print("\n[bold blue]Detected Actions:[/bold blue]")
        
        if command_actions:
            self.console.print("\n[bold]Commands to execute:[/bold]")
            for cmd in command_actions:
                self.console.print(f"  • {cmd.command}")
                
        if file_actions:
            self.console.print("\n[bold]Files to create/modify:[/bold]")
            for action in file_actions:
                rel_path = action.file_path.relative_to(self.root_path)
                self.console.print(f"  • {action.action_type}: {rel_path}")
        
        return Confirm.ask("\n[yellow]Execute these actions?[/yellow]", default=True)
    
    def execute_command(self, command: CommandAction) -> bool:
        """Execute a single command.
        
        Args:
            command: Command to execute
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.console.print(f"[dim]Executing: {command.command}[/dim]")
            
            # Use shell=True for commands with pipes, redirects, etc.
            result = subprocess.run(
                command.command,
                shell=True,
                cwd=command.working_dir or self.root_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                if result.stdout:
                    self.console.print(f"[green]✓[/green] {result.stdout.strip()}")
                return True
            else:
                if result.stderr:
                    self.console.print(f"[red]✗ Error:[/red] {result.stderr.strip()}")
                return False
                
        except Exception as e:
            from rich.markup import escape
            self.console.print(f"[red]Failed to execute command: {escape(str(e))}[/red]")
            return False
    
    def execute_file_action(self, action: FileAction) -> bool:
        """Execute a file action.
        
        Args:
            action: File action to execute
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if action.action_type == 'create':
                # Create parent directories if needed
                action.file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the file
                with open(action.file_path, 'w', encoding='utf-8') as f:
                    f.write(action.content or '')
                
                rel_path = action.file_path.relative_to(self.root_path)
                self.console.print(f"[green]✓ Created:[/green] {rel_path}")
                return True
                
            elif action.action_type == 'modify':
                # TODO: Implement file modification with diff display
                pass
                
            elif action.action_type == 'delete':
                # TODO: Implement file deletion with extra confirmation
                pass
                
        except Exception as e:
            from rich.markup import escape
            self.console.print(f"[red]Failed to {action.action_type} file: {escape(str(e))}[/red]")
            return False
            
        return False
    
    def execute_all_actions(self, file_actions: List[FileAction], 
                           command_actions: List[CommandAction]):
        """Execute all actions in order.
        
        Args:
            file_actions: List of file actions
            command_actions: List of command actions
        """
        # Execute commands first (like mkdir)
        for cmd in command_actions:
            self.execute_command(cmd)
        
        # Then create/modify files
        for action in file_actions:
            self.execute_file_action(action)