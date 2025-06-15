"""Handle AI tool calls with formatted output."""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import subprocess
import glob
import logging

from rich.console import Console
from rich.prompt import Confirm

from .file_context import FileContextManager
from .code_extractor import CodeExtractor
from .tool_output_formatter import ToolOutputFormatter


logger = logging.getLogger(__name__)


class AIToolHandler:
    """Process and execute AI tool calls from responses."""
    
    # Tool patterns in AI responses
    TOOL_PATTERNS = {
        'read': r'Read\(([^)]+)\)',
        'edit': r'Edit\(([^)]+)\)',
        'write': r'Write\(([^)]+)\)',
        'bash': r'Bash\(([^)]+)\)',
        'grep': r'Grep\(([^)]+)\)',
        'glob': r'Glob\(([^)]+)\)',
    }
    
    def __init__(self, console: Console, verbose: bool = False, auto_confirm: bool = False):
        """Initialize the tool handler.
        
        Args:
            console: Rich console for output
            verbose: Show verbose output
            auto_confirm: Auto-confirm file modifications
        """
        self.console = console
        self.verbose = verbose
        self.auto_confirm = auto_confirm
        self.formatter = ToolOutputFormatter(console, verbose)
        self.file_manager = FileContextManager()
        self.code_extractor = CodeExtractor()
        
    def process_response(self, response: str) -> str:
        """Process AI response and handle any tool calls.
        
        Args:
            response: AI response text
            
        Returns:
            Processed response with tool outputs
        """
        # Look for tool calls in the response
        tool_calls = self._extract_tool_calls(response)
        
        if not tool_calls:
            return response
        
        # Execute each tool call
        for tool_name, args in tool_calls:
            try:
                result = self._execute_tool(tool_name, args)
                self.formatter.format_tool_use(tool_name, args, result)
            except Exception as e:
                self.console.print(f"[red]Error executing {tool_name}: {e}[/red]")
                logger.error(f"Tool execution error: {e}", exc_info=True)
        
        return response
    
    def _extract_tool_calls(self, response: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Extract tool calls from AI response.
        
        This is a simplified version - in practice, you'd parse the actual
        XML or structured format the AI uses.
        """
        tool_calls = []
        
        # Simple pattern matching for demonstration
        for tool_name, pattern in self.TOOL_PATTERNS.items():
            matches = re.findall(pattern, response)
            for match in matches:
                # Parse arguments (simplified)
                args = self._parse_tool_args(tool_name, match)
                tool_calls.append((tool_name, args))
        
        return tool_calls
    
    def _parse_tool_args(self, tool_name: str, args_str: str) -> Dict[str, Any]:
        """Parse tool arguments from string.
        
        This is simplified - real implementation would parse actual format.
        """
        # For demonstration, just extract file paths
        if tool_name in ['read', 'write', 'edit']:
            return {'file_path': args_str.strip().strip('"')}
        elif tool_name == 'bash':
            return {'command': args_str.strip().strip('"')}
        elif tool_name in ['grep', 'glob']:
            parts = args_str.split(',')
            return {
                'pattern': parts[0].strip().strip('"'),
                'path': parts[1].strip().strip('"') if len(parts) > 1 else '.'
            }
        return {}
    
    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            
        Returns:
            Tool execution result
        """
        if tool_name == 'read':
            return self._execute_read(args)
        elif tool_name == 'edit':
            return self._execute_edit(args)
        elif tool_name == 'write':
            return self._execute_write(args)
        elif tool_name == 'bash':
            return self._execute_bash(args)
        elif tool_name == 'grep':
            return self._execute_grep(args)
        elif tool_name == 'glob':
            return self._execute_glob(args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def _execute_read(self, args: Dict[str, Any]) -> str:
        """Execute Read tool."""
        file_path = Path(args['file_path'])
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        content = file_path.read_text()
        # Add line numbers like in the actual tool
        lines = content.split('\n')
        numbered_lines = []
        for i, line in enumerate(lines, 1):
            numbered_lines.append(f"{i:6d}→{line}")
        
        return '\n'.join(numbered_lines)
    
    def _execute_edit(self, args: Dict[str, Any]) -> str:
        """Execute Edit tool."""
        file_path = Path(args['file_path'])
        old_string = args.get('old_string', '')
        new_string = args.get('new_string', '')
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Confirm before editing
        if not self.auto_confirm:
            if not Confirm.ask(f"Edit {file_path}?"):
                return "Edit cancelled by user"
        
        content = file_path.read_text()
        if old_string not in content:
            raise ValueError(f"String not found in file: {old_string[:50]}...")
        
        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content)
        
        return f"Successfully edited {file_path}"
    
    def _execute_write(self, args: Dict[str, Any]) -> str:
        """Execute Write tool."""
        file_path = Path(args['file_path'])
        content = args.get('content', '')
        
        # Confirm before writing
        if not self.auto_confirm:
            action = "overwrite" if file_path.exists() else "create"
            if not Confirm.ask(f"{action.capitalize()} {file_path}?"):
                return "Write cancelled by user"
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        return f"Successfully wrote to {file_path}"
    
    def _execute_bash(self, args: Dict[str, Any]) -> str:
        """Execute Bash tool."""
        command = args['command']
        
        # Safety check
        if not self.auto_confirm:
            if not Confirm.ask(f"Execute: {command}?"):
                return "Command cancelled by user"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            
            return output or "(No output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds"
        except Exception as e:
            return f"Command failed: {e}"
    
    def _execute_grep(self, args: Dict[str, Any]) -> str:
        """Execute Grep tool."""
        pattern = args['pattern']
        path = args.get('path', '.')
        
        # Use ripgrep if available, otherwise fall back to grep
        try:
            cmd = ['rg', '--no-heading', pattern, path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout or "No matches found"
        except FileNotFoundError:
            pass
        
        # Fall back to grep
        cmd = ['grep', '-r', pattern, path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout or "No matches found"
    
    def _execute_glob(self, args: Dict[str, Any]) -> str:
        """Execute Glob tool."""
        pattern = args['pattern']
        path = args.get('path', '.')
        
        # Find matching files
        matches = []
        for match in glob.glob(pattern, recursive=True):
            matches.append(match)
        
        if matches:
            return '\n'.join(sorted(matches))
        else:
            return "No files found matching pattern"