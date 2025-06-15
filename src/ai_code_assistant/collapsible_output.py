"""Collapsible output display for better UX."""

from typing import List, Optional, Dict, Any
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich.table import Table
import re


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
            hint = f"[dim]{self.line_count} lines (press Enter to expand)[/dim]"
            console.print(f"[cyan]● {self.title}[/cyan]")
            console.print(f"  [dim]⎿ {hint}[/dim]")


class CollapsibleOutput:
    """Manages collapsible output sections."""
    
    def __init__(self, console: Console):
        """Initialize collapsible output manager.
        
        Args:
            console: Rich console for output
        """
        self.console = console
        self.sections: List[CollapsibleSection] = []
        
    def format_tool_usage(self, tool_name: str, args: str, output: str = None, 
                         collapsed: bool = True) -> None:
        """Format tool usage in Claude Code style.
        
        Args:
            tool_name: Name of the tool (Read, Write, Bash, etc.)
            args: Tool arguments (file path, command, etc.)
            output: Tool output (optional)
            collapsed: Whether to show collapsed by default
        """
        # Tool invocation with bullet point
        self.console.print(f"\n[cyan]● {tool_name}([blue]{args}[/blue])[/cyan]")
        
        if output:
            lines = output.split('\n')
            line_count = len(lines)
            
            if collapsed and line_count > 10:
                # Show collapsed
                preview = '\n'.join(lines[:5])
                if preview:
                    self.console.print(Panel(preview + "\n...", border_style="dim"))
                self.console.print(f"  [dim]⎿ {line_count} lines (press Enter to expand)[/dim]")
            else:
                # Show full output
                self.console.print(Panel(output, border_style="dim"))
        
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
        """Display a summary of sections.
        
        Args:
            sections: List of sections to summarize
        """
        if not sections:
            return
            
        # Group sections by type
        code_sections = [s for s in sections if s.syntax]
        text_sections = [s for s in sections if not s.syntax]
        
        self.console.print("\n[bold blue]Response Summary:[/bold blue]")
        
        if code_sections:
            self.console.print(f"\n[bold]Code Sections ({len(code_sections)}):[/bold]")
            for section in code_sections:
                self.console.print(f"  • {section.title} ({section.line_count} lines)")
                
        if text_sections:
            self.console.print(f"\n[bold]Text Sections ({len(text_sections)}):[/bold]")
            for section in text_sections:
                # Show first line or two of content
                preview = section.content.split('\n')[0][:80]
                if len(preview) == 80:
                    preview += "..."
                self.console.print(f"  • {section.title}")
                self.console.print(f"    [dim]{preview}[/dim]")
    
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