"""Enhancement to display tool outputs like Claude Code."""

from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
import re


class ToolDisplayEnhancement:
    """Enhance tool output display to match Claude Code style."""
    
    # Patterns that indicate tool usage in responses
    TOOL_INDICATORS = {
        'read_file': [
            r"(?:Let me |I'll |I will )?(?:read|check|look at|examine) (?:the )?(?:file|code)",
            r"(?:Reading|Checking|Looking at|Examining) [^\n]+\.(py|js|ts|java|cpp|c|h|md|txt|json|yaml|yml)",
        ],
        'edit_file': [
            r"(?:Let me |I'll |I will )?(?:edit|modify|update|change|fix) (?:the )?(?:file|code)",
            r"(?:Editing|Modifying|Updating|Changing|Fixing) [^\n]+\.(py|js|ts|java|cpp|c|h|md|txt|json|yaml|yml)",
        ],
        'run_command': [
            r"(?:Let me |I'll |I will )?(?:run|execute) (?:the )?(?:command|bash)",
            r"(?:Running|Executing) (?:command:|bash:)?",
        ],
        'search': [
            r"(?:Let me |I'll |I will )?(?:search|grep|find|look for)",
            r"(?:Searching|Looking) for",
        ]
    }
    
    def __init__(self, console: Console, verbose: bool = False):
        """Initialize the enhancement.
        
        Args:
            console: Rich console
            verbose: Whether to show verbose output
        """
        self.console = console
        self.verbose = verbose
        
    def format_tool_usage(self, text: str, tool_type: str, details: Dict[str, Any]) -> None:
        """Format tool usage in Claude Code style.
        
        Args:
            text: Description text (e.g., "Let me read the file")
            tool_type: Type of tool (read_file, edit_file, etc.)
            details: Tool-specific details
        """
        # Print the description with bullet
        self.console.print(f"[cyan]● {text}[/cyan]")
        
        if tool_type == 'read_file':
            self._format_read_file(details)
        elif tool_type == 'edit_file':
            self._format_edit_file(details)
        elif tool_type == 'run_command':
            self._format_run_command(details)
        elif tool_type == 'search':
            self._format_search(details)
            
    def _format_read_file(self, details: Dict[str, Any]) -> None:
        """Format read file output."""
        file_path = details.get('path', 'unknown')
        content = details.get('content', '')
        line_count = len(content.split('\n'))
        
        # Show tool invocation
        self.console.print(f"\n[cyan]● Read([blue]{file_path}[/blue])[/cyan]")
        
        if self.verbose or line_count <= 10:
            # Show full content
            if details.get('language'):
                syntax = Syntax(content, details['language'], theme="monokai", line_numbers=True)
                self.console.print(Panel(syntax, border_style="dim"))
            else:
                self.console.print(Panel(content, border_style="dim"))
        else:
            # Show collapsed hint
            self.console.print(f"  [dim]⎿  Read {line_count} lines (press Enter to expand)[/dim]\n")
            
    def _format_edit_file(self, details: Dict[str, Any]) -> None:
        """Format edit file output."""
        file_path = details.get('path', 'unknown')
        
        # Show tool invocation
        self.console.print(f"\n[cyan]● Update([blue]{file_path}[/blue])[/cyan]")
        
        # Create edit panel similar to Claude Code
        panel_content = []
        panel_content.append(f"[bold]Edit file[/bold]")
        panel_content.append(f"╭{'─' * 78}╮")
        panel_content.append(f"│ {file_path:<76} │")
        panel_content.append(f"│{' ' * 78}│")
        
        # Show diff if available
        if 'diff' in details:
            for line in details['diff'].split('\n')[:20]:  # Limit lines shown
                if line.startswith('-'):
                    panel_content.append(f"│ [red]{line:<76}[/red] │")
                elif line.startswith('+'):
                    panel_content.append(f"│ [green]{line:<76}[/green] │")
                else:
                    panel_content.append(f"│ {line:<76} │")
                    
        panel_content.append(f"╰{'─' * 78}╯")
        
        for line in panel_content:
            self.console.print(line)
            
        # Confirmation prompt
        if not details.get('auto_confirm'):
            self.console.print("\n[yellow]Do you want to make this edit?[/yellow]")
            self.console.print("  [green]1. Yes[/green]")
            self.console.print("  [red]2. No[/red]")
            
    def _format_run_command(self, details: Dict[str, Any]) -> None:
        """Format command execution output."""
        command = details.get('command', 'unknown')
        output = details.get('output', '')
        
        # Show tool invocation
        self.console.print(f"\n[cyan]● Bash: [blue]{command}[/blue][/cyan]")
        
        if output:
            lines = output.split('\n')
            if self.verbose or len(lines) <= 10:
                self.console.print(Panel(output, title="Output", border_style="dim"))
            else:
                # Show first few lines
                preview = '\n'.join(lines[:5]) + '\n...'
                self.console.print(Panel(preview, title="Output (truncated)", border_style="dim"))
                self.console.print(f"  [dim]⎿  {len(lines)} lines (press Enter to expand)[/dim]\n")
                
    def _format_search(self, details: Dict[str, Any]) -> None:
        """Format search results."""
        pattern = details.get('pattern', 'unknown')
        matches = details.get('matches', [])
        
        # Show tool invocation
        self.console.print(f"\n[cyan]● Search: [blue]{pattern}[/blue][/cyan]")
        
        if not matches:
            self.console.print("  [yellow]No matches found[/yellow]")
        elif len(matches) <= 5 or self.verbose:
            for match in matches:
                self.console.print(f"  [green]✓[/green] {match}")
        else:
            # Show first few matches
            for match in matches[:3]:
                self.console.print(f"  [green]✓[/green] {match}")
            self.console.print(f"  [dim]... and {len(matches) - 3} more matches[/dim]\n")
            
    def enhance_response(self, response: str) -> str:
        """Enhance a response by detecting and formatting tool usage.
        
        Args:
            response: The AI response text
            
        Returns:
            Enhanced response (for now, returns original)
        """
        # This is where we would parse the response and format tool usage
        # For now, we'll return the original response
        # In a full implementation, this would:
        # 1. Parse the response for tool usage patterns
        # 2. Extract tool calls and their results
        # 3. Format them using the methods above
        # 4. Return the enhanced display
        
        return response
    
    def detect_tool_intent(self, text: str) -> Optional[Tuple[str, str]]:
        """Detect if text indicates tool usage intent.
        
        Args:
            text: Text to check
            
        Returns:
            Tuple of (tool_type, matched_text) or None
        """
        for tool_type, patterns in self.TOOL_INDICATORS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return (tool_type, match.group(0))
        return None