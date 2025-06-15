"""Collapsible output display for better UX."""

from typing import List, Optional, Dict, Any, Tuple
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich.table import Table
from rich.box import ROUNDED
import re
import platform


class CollapsibleSection:
    """Represents a collapsible section of output."""
    
    def __init__(self, title: str, content: str, expanded: bool = False, 
                 syntax: Optional[str] = None):
        """Initialize a collapsible section.
        
        Args:
            title: Section title
            content: Section content
            expanded: Whether to show expanded by default
            syntax: Optional syntax highlighting language
        """
        self.title = title
        self.content = content
        self.expanded = expanded
        self.syntax = syntax
        self.line_count = len(content.splitlines())
        
    def render(self, console: Console, show_expanded: bool = None):
        """Render the section.
        
        Args:
            console: Rich console
            show_expanded: Override expanded state
        """
        is_expanded = show_expanded if show_expanded is not None else self.expanded
        
        if is_expanded:
            # Show full content
            if self.syntax:
                syntax_obj = Syntax(self.content, self.syntax, theme="monokai", 
                                   line_numbers=True)
                console.print(Panel(syntax_obj, title=self.title, border_style="blue"))
            else:
                console.print(Panel(self.content, title=self.title, border_style="blue"))
        else:
            # Show collapsed with line count - Claude Code style
            # Determine expand key based on platform
            expand_key = "ctrl+r" if platform.system() != "Darwin" else "cmd+r"
            hint = f"[dim]{self.line_count} lines[/dim] [dim italic]({expand_key} to expand)[/dim]"
            console.print(f"[cyan]▸[/cyan] [bold]{self.title}[/bold]")
            console.print(f"  [dim]└─[/dim] {hint}")


class CollapsibleOutput:
    """Manages collapsible output sections."""
    
    def __init__(self, console: Console):
        """Initialize collapsible output manager.
        
        Args:
            console: Rich console for output
        """
        self.console = console
        self.sections: List[CollapsibleSection] = []
        self.tool_colors = {
            'Read': 'cyan',
            'Write': 'green',
            'Edit': 'yellow',
            'MultiEdit': 'yellow',
            'Bash': 'magenta',
            'Search': 'blue',
            'WebSearch': 'blue',
            'WebFetch': 'blue',
            'Git': 'red',
            'TodoRead': 'purple',
            'TodoWrite': 'purple',
            'LS': 'cyan',
            'Glob': 'cyan',
            'Grep': 'cyan'
        }
        
    def format_tool_usage(self, tool_name: str, args: str, output: str = None, 
                         collapsed: bool = True, status: str = "complete") -> None:
        """Format tool usage in Claude Code style.
        
        Args:
            tool_name: Name of the tool (Read, Write, Bash, etc.)
            args: Tool arguments (file path, command, etc.)
            output: Tool output (optional)
            collapsed: Whether to show collapsed by default
            status: Status of the operation ('running', 'complete', 'error')
        """
        # Status icons
        status_icons = {
            'running': '[yellow]⟳[/yellow]',
            'complete': '[green]✓[/green]',
            'error': '[red]✗[/red]',
            'pending': '[dim]○[/dim]'
        }
        
        icon = status_icons.get(status, status_icons['complete'])
        
        # Get tool-specific color
        tool_color = self.tool_colors.get(tool_name, 'white')
        
        # Tool invocation with status icon and tool-specific color
        self.console.print(f"\n{icon} [bold {tool_color}]{tool_name}[/bold {tool_color}]([cyan]{args}[/cyan])")
        
        if output:
            lines = output.split('\n')
            line_count = len(lines)
            
            # Determine expand key based on platform
            expand_key = "ctrl+r" if platform.system() != "Darwin" else "cmd+r"
            
            if collapsed and line_count > 10:
                # Show collapsed with preview
                preview_lines = lines[:3]
                preview = '\n'.join(preview_lines)
                
                # Create a subtle preview box
                if preview:
                    preview_text = Text(preview, style="dim")
                    console_width = self.console.width
                    # Truncate long lines in preview
                    truncated_preview = []
                    for line in preview_lines:
                        if len(line) > console_width - 10:
                            truncated_preview.append(line[:console_width - 13] + "...")
                        else:
                            truncated_preview.append(line)
                    
                    preview_panel = Panel(
                        '\n'.join(truncated_preview),
                        border_style="dim",
                        box=ROUNDED,
                        padding=(0, 1),
                        expand=False
                    )
                    self.console.print(preview_panel)
                
                # Show line count and expand hint
                self.console.print(
                    f"  [dim]└─ {line_count} lines[/dim] "
                    f"[dim italic]({expand_key} to expand)[/dim]"
                )
            else:
                # Show full output
                output_panel = Panel(
                    output,
                    border_style="dim" if status == "complete" else "yellow",
                    box=ROUNDED,
                    padding=(0, 1)
                )
                self.console.print(output_panel)
    
    def format_tool_output(self, tool_name: str, args: Dict[str, Any], 
                          result: Any, status: str = "complete") -> None:
        """Format tool output with better structure based on tool type.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments as dictionary
            result: Tool result (can be string, dict, list, etc.)
            status: Status of the operation
        """
        # Format arguments based on tool type
        if tool_name in ['Read', 'Write', 'Edit']:
            arg_str = args.get('file_path', args.get('path', ''))
        elif tool_name == 'Bash':
            arg_str = args.get('command', '')
        elif tool_name in ['Search', 'WebSearch']:
            arg_str = args.get('query', '')
        elif tool_name == 'WebFetch':
            arg_str = args.get('url', '')
        elif tool_name in ['Glob', 'Grep']:
            pattern = args.get('pattern', '')
            path = args.get('path', '.')
            arg_str = f"{pattern} in {path}"
        else:
            # Generic formatting for other tools
            arg_str = ', '.join(f"{k}={v}" for k, v in args.items() if v is not None)
        
        # Convert result to string if needed
        if isinstance(result, dict):
            output = self._format_dict_result(result)
        elif isinstance(result, list):
            output = '\n'.join(str(item) for item in result)
        else:
            output = str(result) if result else None
        
        # Use the main formatting method
        self.format_tool_usage(tool_name, arg_str, output, collapsed=True, status=status)
    
    def _format_dict_result(self, result: Dict[str, Any]) -> str:
        """Format dictionary results nicely.
        
        Args:
            result: Dictionary to format
            
        Returns:
            Formatted string
        """
        lines = []
        for key, value in result.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            elif isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")
        return '\n'.join(lines)
    
    def format_file_operation(self, operation: str, file_path: str, 
                            content: Optional[str] = None, 
                            line_count: Optional[int] = None,
                            status: str = "complete") -> None:
        """Format file operations in Claude Code style.
        
        Args:
            operation: Type of operation ('read', 'write', 'edit', 'create')
            file_path: Path to the file
            content: File content (optional)
            line_count: Number of lines (optional)
            status: Status of the operation
        """
        # Operation icons
        op_icons = {
            'read': '📖',
            'write': '💾',
            'edit': '✏️',
            'create': '✨',
            'delete': '🗑️'
        }
        
        # Status icons
        status_icons = {
            'running': '[yellow]⟳[/yellow]',
            'complete': '[green]✓[/green]',
            'error': '[red]✗[/red]'
        }
        
        icon = status_icons.get(status, status_icons['complete'])
        op_icon = op_icons.get(operation, '📄')
        
        # Determine expand key
        expand_key = "ctrl+r" if platform.system() != "Darwin" else "cmd+r"
        
        # Display operation header
        self.console.print(f"\n{icon} {op_icon} [bold]{operation.title()}[/bold] [cyan]{file_path}[/cyan]")
        
        if content and line_count and line_count > 10:
            # Show collapsed view with preview
            lines = content.split('\n')
            preview_lines = lines[:5]
            preview = '\n'.join(preview_lines)
            
            # Create preview panel
            if preview:
                preview_panel = Panel(
                    preview + "\n[dim]...[/dim]",
                    border_style="dim",
                    box=ROUNDED,
                    padding=(0, 1),
                    expand=False
                )
                self.console.print(preview_panel)
            
            # Show expand hint
            self.console.print(
                f"  [dim]└─ {line_count} lines[/dim] "
                f"[dim italic]({expand_key} to expand)[/dim]"
            )
        elif content:
            # Show full content for small files
            content_panel = Panel(
                content,
                border_style="dim",
                box=ROUNDED,
                padding=(0, 1)
            )
            self.console.print(content_panel)
    
    def show_progress(self, message: str, status: str = "running") -> None:
        """Show a progress indicator for operations.
        
        Args:
            message: Progress message
            status: Current status ('running', 'complete', 'error')
        """
        status_indicators = {
            'running': '[yellow]⟳[/yellow] [dim]Working...[/dim]',
            'complete': '[green]✓[/green] Done',
            'error': '[red]✗[/red] Failed',
            'thinking': '[cyan]🤔[/cyan] [dim]Thinking...[/dim]',
            'analyzing': '[blue]🔍[/blue] [dim]Analyzing...[/dim]'
        }
        
        indicator = status_indicators.get(status, status_indicators['running'])
        self.console.print(f"{indicator} {message}")
    
    def create_summary_panel(self, title: str, items: List[Tuple[str, str]], 
                           style: str = "blue") -> None:
        """Create a summary panel with items.
        
        Args:
            title: Panel title
            items: List of (label, value) tuples
            style: Panel border style
        """
        content_lines = []
        for label, value in items:
            content_lines.append(f"[bold]{label}:[/bold] {value}")
        
        panel = Panel(
            '\n'.join(content_lines),
            title=f"[bold]{title}[/bold]",
            border_style=style,
            box=ROUNDED,
            padding=(1, 2)
        )
        self.console.print(panel)
        
    def parse_response(self, response: str) -> List[CollapsibleSection]:
        """Parse an AI response into collapsible sections.
        
        Args:
            response: The AI response text
            
        Returns:
            List of collapsible sections
        """
        sections = []
        
        # Split response into sections based on headers
        header_pattern = r'^#{1,3}\s+(.+)$'
        
        current_section = None
        current_content = []
        current_syntax = None
        
        lines = response.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for header
            header_match = re.match(header_pattern, line, re.MULTILINE)
            if header_match:
                # Save previous section if exists
                if current_section:
                    content = '\n'.join(current_content).strip()
                    if content:
                        sections.append(CollapsibleSection(
                            current_section, 
                            content,
                            expanded=False,
                            syntax=current_syntax
                        ))
                
                # Start new section
                current_section = header_match.group(1)
                current_content = []
                current_syntax = None
                
            # Check for code block start
            elif line.strip().startswith('```'):
                code_lang_match = re.match(r'```(\w+)?', line.strip())
                if code_lang_match:
                    lang = code_lang_match.group(1) or 'text'
                    
                    # Find the end of code block
                    code_lines = []
                    i += 1
                    while i < len(lines) and not lines[i].strip() == '```':
                        code_lines.append(lines[i])
                        i += 1
                    
                    code_content = '\n'.join(code_lines)
                    
                    # Determine section title
                    if current_section:
                        # Look for file path in content above
                        file_path = self._extract_file_path(current_content)
                        if file_path:
                            sections.append(CollapsibleSection(
                                f"{current_section}: {file_path}",
                                code_content,
                                expanded=False,
                                syntax=lang
                            ))
                        else:
                            current_content.append(line)
                            current_content.extend(code_lines)
                            current_content.append('```')
                            current_syntax = lang
                    else:
                        # Standalone code block
                        sections.append(CollapsibleSection(
                            f"Code ({lang})",
                            code_content,
                            expanded=False,
                            syntax=lang
                        ))
            else:
                if current_section:
                    current_content.append(line)
                    
            i += 1
        
        # Save last section
        if current_section and current_content:
            content = '\n'.join(current_content).strip()
            if content:
                sections.append(CollapsibleSection(
                    current_section,
                    content,
                    expanded=False,
                    syntax=current_syntax
                ))
        
        return sections
    
    def _extract_file_path(self, content_lines: List[str]) -> Optional[str]:
        """Extract file path from content lines.
        
        Args:
            content_lines: Lines of content
            
        Returns:
            File path if found
        """
        # Look for patterns like "### filename.ext" or "**filename.ext**"
        for line in reversed(content_lines[-5:]):  # Check last 5 lines
            # Match various file path patterns
            patterns = [
                r'^\*\*([^*]+)\*\*$',  # **file.ext**
                r'^###\s+(.+)$',        # ### file.ext
                r'^`([^`]+)`$',         # `file.ext`
                r'^File:\s*(.+)$',      # File: file.ext
            ]
            
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    path = match.group(1).strip()
                    if '.' in path or '/' in path:
                        return path
        
        return None
    
    def display_summary(self, sections: List[CollapsibleSection]):
        """Display a summary of sections in Claude Code style.
        
        Args:
            sections: List of sections to summarize
        """
        if not sections:
            return
            
        # Group sections by type
        code_sections = [s for s in sections if s.syntax]
        text_sections = [s for s in sections if not s.syntax]
        
        # Calculate totals
        total_lines = sum(s.line_count for s in sections)
        
        # Create summary items
        summary_items = []
        
        if code_sections:
            code_files = len(set(s.title for s in code_sections))
            code_lines = sum(s.line_count for s in code_sections)
            summary_items.append(("Code", f"{code_files} files, {code_lines} lines"))
            
        if text_sections:
            text_count = len(text_sections)
            text_lines = sum(s.line_count for s in text_sections)
            summary_items.append(("Text", f"{text_count} sections, {text_lines} lines"))
        
        summary_items.append(("Total", f"{len(sections)} sections, {total_lines} lines"))
        
        # Display summary panel
        self.create_summary_panel("Response Summary", summary_items, style="cyan")
        
        # Show collapsible sections
        if sections:
            self.console.print("\n[bold]Sections:[/bold]")
            for i, section in enumerate(sections, 1):
                # Determine section icon based on type
                if section.syntax:
                    icon = "📄" if "." in section.title else "💻"
                else:
                    icon = "📝"
                
                # Show section with collapsed indicator
                expand_key = "ctrl+r" if platform.system() != "Darwin" else "cmd+r"
                self.console.print(
                    f"\n  {icon} [cyan]▸[/cyan] [bold]{section.title}[/bold] "
                    f"[dim]({section.line_count} lines)[/dim] "
                    f"[dim italic]({expand_key} to expand)[/dim]"
                )
    
    def display_sections(self, sections: List[CollapsibleSection], 
                        expand_all: bool = False):
        """Display all sections.
        
        Args:
            sections: List of sections to display
            expand_all: Whether to expand all sections
        """
        for section in sections:
            section.render(self.console, show_expanded=expand_all)
            self.console.print()  # Add spacing
    
    def format_inline_code(self, text: str) -> str:
        """Format text with inline code highlighting.
        
        Args:
            text: Text containing inline code
            
        Returns:
            Formatted text with highlighted code
        """
        # Replace `code` with styled version
        import re
        
        def replace_code(match):
            code = match.group(1)
            return f"[bold cyan]{code}[/bold cyan]"
        
        # Pattern to match inline code
        pattern = r'`([^`]+)`'
        formatted = re.sub(pattern, replace_code, text)
        
        # Also highlight file paths
        path_pattern = r'(\b[\w./\-]+\.(py|js|ts|tsx|jsx|java|cpp|c|h|go|rs|rb|php|sh|yaml|yml|json|xml|html|css|scss|sass|md|txt|log)\b)'
        formatted = re.sub(path_pattern, r'[cyan]\1[/cyan]', formatted)
        
        return formatted
    
    def format_command_output(self, command: str, output: str, 
                            exit_code: int = 0, duration: Optional[float] = None) -> None:
        """Format command execution output in Claude Code style.
        
        Args:
            command: The command that was executed
            output: Command output
            exit_code: Command exit code
            duration: Execution duration in seconds
        """
        # Status based on exit code
        if exit_code == 0:
            status_icon = "[green]✓[/green]"
            status_text = "Success"
            panel_style = "green"
        else:
            status_icon = "[red]✗[/red]"
            status_text = f"Failed (exit code: {exit_code})"
            panel_style = "red"
        
        # Command header
        self.console.print(f"\n{status_icon} [bold magenta]$[/bold magenta] {command}")
        
        # Duration if available
        if duration:
            self.console.print(f"  [dim]Completed in {duration:.2f}s[/dim]")
        
        # Output panel
        if output:
            lines = output.split('\n')
            line_count = len(lines)
            
            # Determine if we should collapse
            if line_count > 20:
                # Show collapsed with preview
                preview = '\n'.join(lines[:10])
                expand_key = "ctrl+r" if platform.system() != "Darwin" else "cmd+r"
                
                preview_panel = Panel(
                    preview + f"\n[dim]... ({line_count - 10} more lines)[/dim]",
                    border_style="dim",
                    box=ROUNDED,
                    padding=(0, 1)
                )
                self.console.print(preview_panel)
                self.console.print(
                    f"  [dim]└─ {line_count} lines total[/dim] "
                    f"[dim italic]({expand_key} to expand)[/dim]"
                )
            else:
                # Show full output
                output_panel = Panel(
                    output,
                    border_style=panel_style,
                    box=ROUNDED,
                    padding=(0, 1)
                )
                self.console.print(output_panel)