"""Format tool outputs in a collapsible, user-friendly way."""

from typing import List, Dict, Any, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
import re


class ToolOutputFormatter:
    """Format tool outputs similar to Claude Code's collapsible format."""
    
    def __init__(self, console: Console, verbose: bool = False):
        """Initialize the formatter.
        
        Args:
            console: Rich console for output
            verbose: Whether to show expanded output by default
        """
        self.console = console
        self.verbose = verbose
        self.collapsed_outputs = []  # Store collapsed content for expansion
        
    def format_tool_use(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        """Format a tool use with collapsible output.
        
        Args:
            tool_name: Name of the tool (e.g., "Read", "Edit", "Bash")
            args: Arguments passed to the tool
            result: Result from the tool
        """
        # Format based on tool type
        if tool_name.lower() == "read":
            self._format_read_tool(args, result)
        elif tool_name.lower() == "edit" or tool_name.lower() == "write":
            self._format_file_modification(tool_name, args, result)
        elif tool_name.lower() == "bash":
            self._format_bash_tool(args, result)
        elif tool_name.lower() == "grep" or tool_name.lower() == "glob":
            self._format_search_tool(tool_name, args, result)
        else:
            # Generic format
            self._format_generic_tool(tool_name, args, result)
    
    def _format_read_tool(self, args: Dict[str, Any], result: str) -> None:
        """Format Read tool output."""
        file_path = args.get('file_path', 'unknown')
        lines = result.split('\n') if result else []
        line_count = len(lines)
        
        # Show brief summary
        self.console.print(f"[cyan]● Read([blue]{file_path}[/blue])[/cyan]")
        
        if self.verbose or line_count <= 10:
            # Show full content if verbose or small file
            syntax = Syntax(result, "python", theme="monokai", line_numbers=True)
            self.console.print(Panel(syntax, border_style="dim"))
        else:
            # Show collapsed with hint
            preview_lines = '\n'.join(lines[:5]) + '\n...'
            self.console.print(f"  [dim]⎿  Read {line_count} lines (press Enter to expand)[/dim]")
            # Store for potential expansion
            self.collapsed_outputs.append(('read', file_path, result))
    
    def _format_file_modification(self, tool_name: str, args: Dict[str, Any], result: str) -> None:
        """Format Edit/Write tool output."""
        file_path = args.get('file_path', 'unknown')
        
        self.console.print(f"[cyan]● {tool_name}([blue]{file_path}[/blue])[/cyan]")
        
        if tool_name.lower() == "edit":
            # Show a diff-like view
            old_string = args.get('old_string', '')
            new_string = args.get('new_string', '')
            
            # Create a simple diff display
            diff_panel = self._create_diff_panel(file_path, old_string, new_string)
            self.console.print(diff_panel)
            
            # Add confirmation prompt for interactive mode
            if not self.verbose:
                self.console.print("[yellow]File modified successfully[/yellow]")
        else:
            # Write tool
            content_preview = args.get('content', '')[:200] + '...' if len(args.get('content', '')) > 200 else args.get('content', '')
            self.console.print(Panel(
                Syntax(content_preview, "python", theme="monokai"),
                title=f"Writing to {file_path}",
                border_style="green"
            ))
    
    def _format_bash_tool(self, args: Dict[str, Any], result: str) -> None:
        """Format Bash tool output."""
        command = args.get('command', 'unknown')
        
        # Brief description
        self.console.print(f"[cyan]● Bash: [blue]{command}[/blue][/cyan]")
        
        if result:
            lines = result.split('\n')
            if self.verbose or len(lines) <= 10:
                # Show full output
                self.console.print(Panel(result, title="Output", border_style="dim"))
            else:
                # Show collapsed
                preview = '\n'.join(lines[:5]) + '\n...'
                self.console.print(Panel(preview, title="Output (truncated)", border_style="dim"))
                self.console.print(f"  [dim]⎿  {len(lines)} lines of output (press Enter to expand)[/dim]")
                self.collapsed_outputs.append(('bash', command, result))
    
    def _format_search_tool(self, tool_name: str, args: Dict[str, Any], result: str) -> None:
        """Format Grep/Glob tool output."""
        pattern = args.get('pattern', 'unknown')
        path = args.get('path', '.')
        
        self.console.print(f"[cyan]● {tool_name}: [blue]{pattern}[/blue] in [blue]{path}[/blue][/cyan]")
        
        if result:
            lines = result.split('\n')
            matches = [l for l in lines if l.strip()]
            
            if len(matches) <= 5 or self.verbose:
                for match in matches:
                    self.console.print(f"  [green]✓[/green] {match}")
            else:
                # Show first few matches
                for match in matches[:3]:
                    self.console.print(f"  [green]✓[/green] {match}")
                self.console.print(f"  [dim]... and {len(matches) - 3} more matches[/dim]")
    
    def _format_generic_tool(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        """Format generic tool output."""
        self.console.print(f"[cyan]● {tool_name}[/cyan]")
        
        # Show args in a compact way
        if args:
            args_str = ', '.join(f"{k}={v}" for k, v in args.items() if k != 'content')
            self.console.print(f"  [dim]Args: {args_str}[/dim]")
        
        # Show result
        if result:
            result_str = str(result)
            if len(result_str) > 200 and not self.verbose:
                self.console.print(f"  [dim]Result: {result_str[:200]}...[/dim]")
            else:
                self.console.print(f"  Result: {result_str}")
    
    def _create_diff_panel(self, file_path: str, old_string: str, new_string: str) -> Panel:
        """Create a diff-style panel for file edits."""
        # Split into lines for comparison
        old_lines = old_string.split('\n')
        new_lines = new_string.split('\n')
        
        # Create diff display
        diff_content = []
        
        # Show some context
        diff_content.append(f"[bold]{file_path}[/bold]\n")
        
        # Simple diff display (not a full diff algorithm)
        max_lines = 10 if not self.verbose else None
        
        if len(old_lines) == 1 and len(new_lines) == 1:
            # Single line change
            diff_content.append(f"[red]- {old_lines[0]}[/red]")
            diff_content.append(f"[green]+ {new_lines[0]}[/green]")
        else:
            # Multi-line change
            diff_content.append("[red]--- Original[/red]")
            for i, line in enumerate(old_lines[:max_lines]):
                diff_content.append(f"[red]- {line}[/red]")
            if max_lines and len(old_lines) > max_lines:
                diff_content.append(f"[dim]... ({len(old_lines) - max_lines} more lines)[/dim]")
                
            diff_content.append("\n[green]+++ Modified[/green]")
            for i, line in enumerate(new_lines[:max_lines]):
                diff_content.append(f"[green]+ {line}[/green]")
            if max_lines and len(new_lines) > max_lines:
                diff_content.append(f"[dim]... ({len(new_lines) - max_lines} more lines)[/dim]")
        
        return Panel(
            '\n'.join(diff_content),
            title="Edit file",
            border_style="yellow"
        )
    
    def expand_last(self) -> None:
        """Expand the last collapsed output."""
        if self.collapsed_outputs:
            tool_type, identifier, content = self.collapsed_outputs.pop()
            self.console.print(f"\n[dim]Expanded {tool_type} output:[/dim]")
            
            if tool_type == 'read':
                syntax = Syntax(content, "python", theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, title=identifier, border_style="blue"))
            else:
                self.console.print(Panel(content, title=identifier, border_style="blue"))
    
    def clear_collapsed(self) -> None:
        """Clear stored collapsed outputs."""
        self.collapsed_outputs = []