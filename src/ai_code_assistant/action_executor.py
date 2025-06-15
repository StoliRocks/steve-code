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
from .structured_output import TodoItem


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
        
        # Debug: log response snippet and code blocks found
        if not code_blocks:
            logger.debug("No code blocks found in response")
        else:
            logger.debug(f"Found {len(code_blocks)} code blocks")
            
        # Look for file path indicators before code blocks
        lines = response.split('\n')
        used_blocks = set()  # Track which code blocks we've assigned
        
        for i, line in enumerate(lines):
            # Match patterns like "### package.json" or "**lib/lambda/app.py**" or "lib/lambda/app.py"
            file_patterns = [
                r'^#{1,6}\s*(.+?)$',         # # to ###### filename
                r'^\*{2}(.+?)\*{2}$',        # **filename**
                r'^`(.+?)`:\s*$',            # `filename`:
                r'^`(.+?)`$',                # `filename`
                r'^File:\s*(.+?)$',          # File: filename
                r'^Create\s+(.+?)$',         # Create filename
                r'^(.+?):$',                 # filename:
                r'^\d+\.\s*(.+?)$',          # 1. filename
            ]
            
            potential_path = None
            for pattern in file_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    potential_path = match.group(1).strip().rstrip(':')
                    break
            
            if potential_path:
                # Check if it looks like a file path - be more lenient
                # Accept paths with extensions, paths with slashes, or common filenames
                common_files = [
                    'makefile', 'dockerfile', 'readme', 'license', 'changelog',
                    'package.json', 'tsconfig.json', '.gitignore', '.eslintrc.json',
                    'jest.config.js', 'cdk.json', '.npmignore'
                ]
                
                is_file_path = (
                    ('.' in potential_path and not potential_path.startswith('#')) or 
                    '/' in potential_path or
                    potential_path.lower() in common_files or
                    potential_path.lower().replace('-', '').replace('_', '') in [f.replace('-', '').replace('_', '') for f in common_files]
                )
                
                if is_file_path:
                    # Look for the next unused code block within the next 10 lines
                    for j, block in enumerate(code_blocks):
                        if j not in used_blocks:
                            # Check if the code block is reasonably close to this file path
                            block_line = getattr(block, 'line_number', i + 1)
                            if block_line > i and block_line <= i + 10:
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
        
        # Also look for any orphaned code blocks that might be files
        # This catches cases where the file path isn't immediately before the code
        for j, block in enumerate(code_blocks):
            if j not in used_blocks and block.filename:
                # This block has an embedded filename
                file_path = self.root_path / block.filename
                file_actions.append(FileAction(
                    action_type='create',
                    file_path=file_path,
                    content=block.content,
                    language=block.language
                ))
                used_blocks.add(j)
        
        # Final fallback: Look for common file patterns in the entire response
        # This helps catch cases where formatting isn't standard
        if not file_actions:
            file_mention_pattern = r'(?:^|\n)(?:create|Create|file|File)?\s*(?:the\s+)?(?:following\s+)?(?:file\s+)?["\']?([a-zA-Z0-9_\-./]+\.(?:json|ts|js|py|yaml|yml|md|txt|sh|dockerfile|makefile))["\']?'
            
            for match in re.finditer(file_mention_pattern, response, re.IGNORECASE | re.MULTILINE):
                potential_file = match.group(1)
                # Find the next unused code block after this mention
                match_pos = match.start()
                match_line = response[:match_pos].count('\n')
                
                for j, block in enumerate(code_blocks):
                    if j not in used_blocks:
                        block_line = getattr(block, 'line_number', 0)
                        if block_line > match_line:
                            file_path = self.root_path / potential_file
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
                    # Check if it's a file operation or npm/cdk command
                    if any(op in cmd for op in ['mkdir', 'touch', 'cp', 'mv', 'cd', 'npm', 'npx', 'cdk', 'node']):
                        command_actions.append(CommandAction(
                            command=cmd,
                            description="Command execution"
                        ))
                    # Also capture npm/cdk commands
                    elif any(op in cmd for op in ['npm', 'cdk', 'npx']):
                        command_actions.append(CommandAction(
                            command=cmd,
                            description="Package/CDK operation"
                        ))
        
        # Fallback: if we didn't match any files but have code blocks, try to extract from content
        if not file_actions and code_blocks:
            # Look for file paths mentioned anywhere in the response
            file_mention_pattern = r'(?:^|\s)([\w\-]+(?:/[\w\-]+)*\.(?:json|js|ts|tsx|py|md|yml|yaml|txt|gitignore))(?:\s|$|:)'
            for match in re.finditer(file_mention_pattern, response, re.MULTILINE):
                file_path_str = match.group(1)
                # Find unused code block that might belong to this file
                for j, block in enumerate(code_blocks):
                    if j not in used_blocks:
                        file_path = self.root_path / file_path_str
                        file_actions.append(FileAction(
                            action_type='create',
                            file_path=file_path,
                            content=block.content,
                            language=block.language
                        ))
                        used_blocks.add(j)
                        break
        
        # Debug output if no actions found
        if not file_actions and not command_actions:
            logger.debug("No actions detected in response")
            logger.debug(f"Response preview: {response[:200]}...")
            
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
            # Debug: log when no actions found
            self.console.print("[dim]No executable actions detected in response[/dim]")
            return False
            
        self.console.print("\n[bold blue]Detected Actions:[/bold blue]")
        
        if command_actions:
            self.console.print("\n[bold]Commands to execute:[/bold]")
            for cmd in command_actions:
                self.console.print(f"  • {cmd.command}")
                if cmd.description:
                    self.console.print(f"    [dim]{cmd.description}[/dim]")
                
        if file_actions:
            self.console.print("\n[bold]Files to create/modify:[/bold]")
            for action in file_actions:
                try:
                    rel_path = action.file_path.relative_to(self.root_path)
                except ValueError:
                    # Path is not relative to root, show absolute
                    rel_path = action.file_path
                self.console.print(f"  • {action.action_type}: {rel_path}")
                if action.language:
                    self.console.print(f"    [dim]Language: {action.language}[/dim]")
        
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
    
    def actions_to_todos(self, file_actions: List[FileAction], 
                         command_actions: List[CommandAction]) -> List[TodoItem]:
        """Convert file and command actions to todo items.
        
        Args:
            file_actions: List of file actions
            command_actions: List of command actions
            
        Returns:
            List of TodoItem objects
        """
        todos = []
        todo_id = 1
        
        # Add command actions first (often create directories)
        for cmd in command_actions:
            # Determine priority based on command type
            priority = "high" if any(x in cmd.command for x in ['mkdir', 'npm init', 'cdk init']) else "medium"
            
            # Use description if available, otherwise truncate long commands
            if cmd.description:
                content = cmd.description
            else:
                if len(cmd.command) > 50:
                    content = f"{cmd.command[:47]}..."
                else:
                    content = cmd.command
            
            todos.append(TodoItem(
                id=f"action_{todo_id}",
                content=content,
                status="pending",
                priority=priority,
                metadata={'type': 'command', 'action': cmd}
            ))
            todo_id += 1
        
        # Add file actions
        for action in file_actions:
            try:
                rel_path = action.file_path.relative_to(self.root_path)
            except ValueError:
                rel_path = action.file_path
            
            # Use concise format without redundant "file" word
            content_desc = f"{action.action_type.title()} {rel_path}"
            
            todos.append(TodoItem(
                id=f"action_{todo_id}",
                content=content_desc,
                status="pending",
                priority="medium",
                metadata={'type': 'file', 'action': action}
            ))
            todo_id += 1
        
        return todos