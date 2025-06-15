"""Structured output formatting for interactive mode."""

from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from dataclasses import dataclass
import time


@dataclass
class UpdateItem:
    """Represents a single update item."""
    action: str  # "Create", "Update", "Delete", etc.
    target: str  # File path or description
    details: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    additions: int = 0
    deletions: int = 0
    
    def format(self) -> str:
        """Format the update item."""
        status_icon = {
            "pending": "○",
            "in_progress": "●",
            "completed": "✓",
            "failed": "✗"
        }[self.status]
        
        if self.additions > 0 or self.deletions > 0:
            changes = f" (+{self.additions}, -{self.deletions})"
        else:
            changes = ""
        
        return f"{status_icon} {self.action}({self.target}){changes}"


@dataclass
class TodoItem:
    """Represents a todo/task item."""
    id: str
    content: str
    status: str = "pending"  # pending, in_progress, completed, failed
    priority: str = "medium"  # low, medium, high
    metadata: Optional[Dict[str, Any]] = None  # Store action details
    result: Optional[str] = None  # Store execution result
    error: Optional[str] = None  # Store error if failed
    
    def format(self) -> str:
        """Format the todo item."""
        checkbox = "☐" if self.status == "pending" else "☒"
        priority_color = {
            "low": "dim",
            "medium": "white",
            "high": "yellow"
        }[self.priority]
        
        # Add strikethrough for completed items
        if self.status == "completed":
            return f"{checkbox} [strike {priority_color}]{self.content}[/strike {priority_color}]"
        else:
            return f"{checkbox} [{priority_color}]{self.content}[/{priority_color}]"


class StructuredOutput:
    """Provides structured output formatting for the interactive mode."""
    
    def __init__(self, console: Console):
        """Initialize structured output formatter.
        
        Args:
            console: Rich console instance
        """
        self.console = console
        self.current_operation: Optional[str] = None
        self.updates: List[UpdateItem] = []
        self.todos: List[TodoItem] = []
        
    def start_operation(self, operation: str):
        """Start a new operation section.
        
        Args:
            operation: Description of the operation
        """
        self.current_operation = operation
        self.updates = []
        self.console.print(f"\n[bold blue]● {operation}[/bold blue]")
    
    def add_update(self, action: str, target: str, details: Optional[str] = None,
                   additions: int = 0, deletions: int = 0) -> UpdateItem:
        """Add an update to the current operation.
        
        Args:
            action: The action being performed
            target: The target file or object
            details: Optional details
            additions: Number of lines added
            deletions: Number of lines deleted
            
        Returns:
            The created UpdateItem
        """
        update = UpdateItem(
            action=action,
            target=target,
            details=details,
            additions=additions,
            deletions=deletions,
            status="in_progress"
        )
        self.updates.append(update)
        
        # Display the update
        self._display_update(update)
        
        return update
    
    def _display_update(self, update: UpdateItem):
        """Display a single update item."""
        # Format the basic update line
        if update.target.startswith('/'):
            # It's a file path, make it relative if possible
            try:
                target = str(Path(update.target).relative_to(Path.cwd()))
            except:
                target = update.target
        else:
            target = update.target
        
        status_icon = "●" if update.status == "in_progress" else "✓"
        
        self.console.print(f"  {status_icon} {update.action}({target})")
        
        # Show details if present
        if update.details:
            self.console.print(f"    ⎿ {update.details}")
        
        # Show additions/deletions if present
        if update.additions > 0 or update.deletions > 0:
            changes_text = []
            if update.additions > 0:
                changes_text.append(f"[green]+{update.additions}[/green]")
            if update.deletions > 0:
                changes_text.append(f"[red]-{update.deletions}[/red]")
            self.console.print(f"       {' '.join(changes_text)}")
    
    def complete_update(self, update: UpdateItem, success: bool = True):
        """Mark an update as completed.
        
        Args:
            update: The update to complete
            success: Whether the update was successful
        """
        update.status = "completed" if success else "failed"
    
    def show_code_changes(self, file_path: str, changes: List[Tuple[int, str, str]]):
        """Display code changes in a structured format.
        
        Args:
            file_path: Path to the file
            changes: List of (line_number, old_line, new_line) tuples
        """
        # Make path relative if possible
        try:
            rel_path = str(Path(file_path).relative_to(Path.cwd()))
        except:
            rel_path = file_path
        
        self.console.print(f"\n● Update({rel_path})")
        self.console.print(f"  ⎿ Updated {rel_path} with {len(changes)} changes")
        
        # Show each change
        for line_num, old_line, new_line in changes[:5]:  # Limit to 5 changes
            if old_line and new_line:
                # Modified line
                self.console.print(f"       {line_num} - {old_line.strip()}")
                self.console.print(f"       {line_num} + {new_line.strip()}")
            elif new_line:
                # Added line
                self.console.print(f"       {line_num} + {new_line.strip()}")
            elif old_line:
                # Removed line
                self.console.print(f"       {line_num} - {old_line.strip()}")
        
        if len(changes) > 5:
            self.console.print(f"       ... and {len(changes) - 5} more changes")
    
    def update_todos(self, todos: List[TodoItem]):
        """Update and display the todo list.
        
        Args:
            todos: List of todo items
        """
        self.todos = todos
        
        # Group by status
        pending = [t for t in todos if t.status == "pending"]
        in_progress = [t for t in todos if t.status == "in_progress"]
        completed = [t for t in todos if t.status == "completed"]
        
        if not todos:
            return
        
        self.console.print("\n● Update Todos")
        
        # Show summary
        parts = []
        if completed:
            parts.append(f"☒ {len(completed)}")
        if in_progress:
            parts.append(f"● {len(in_progress)}")
        if pending:
            parts.append(f"☐ {len(pending)}")
        
        self.console.print(f"  ⎿ {' '.join(parts)}")
        
        # Show each todo
        for todo in todos[:10]:  # Limit display
            self.console.print(f"     {todo.format()}")
        
        if len(todos) > 10:
            self.console.print(f"     ... and {len(todos) - 10} more")
    
    def show_progress(self, task: str, current: int, total: int):
        """Show a progress bar for a task.
        
        Args:
            task: Description of the task
            current: Current progress
            total: Total items
        """
        percentage = (current / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        
        self.console.print(f"  ● {task}")
        self.console.print(f"    [{bar}] {percentage:.0f}% ({current}/{total})")
    
    def show_status_line(self, verb: str, elapsed: float, tokens: int, 
                        context_percent: int, auto_compact_at: int = 20):
        """Show a comprehensive status line.
        
        Args:
            verb: The current action verb
            elapsed: Elapsed time in seconds
            tokens: Estimated token count
            context_percent: Percentage of context remaining
            auto_compact_at: When auto-compact triggers
        """
        # Build status parts
        status_parts = []
        
        # Action and time
        status_parts.append(f"{verb}... ({int(elapsed)}s)")
        
        # Token count
        status_parts.append(f"⚙ {tokens/1000:.1f}k tokens")
        
        # Context status with color
        context_color = "green" if context_percent > 30 else "yellow" if context_percent > 20 else "red"
        status_parts.append(f"[{context_color}]📊 {context_percent}%[/{context_color}]")
        
        # Auto-compact warning
        if context_percent <= auto_compact_at + 10:
            status_parts.append(f"[yellow]⚠ auto-compact at {auto_compact_at}%[/yellow]")
        
        # ESC hint
        status_parts.append("[dim]ESC to interrupt[/dim]")
        
        # Clear line and display
        status_line = " · ".join(status_parts)
        # Use ANSI escape codes to clear the line properly
        self.console.print(f"\r\033[K{status_line}", end="")
    
    def create_summary_panel(self, title: str, items: List[str]) -> Panel:
        """Create a summary panel with items.
        
        Args:
            title: Panel title
            items: List of items to display
            
        Returns:
            Rich Panel object
        """
        content = "\n".join(f"  • {item}" for item in items)
        return Panel(content, title=title, border_style="blue")
    
    def show_tree(self, title: str, structure: Dict[str, Any]):
        """Display a tree structure.
        
        Args:
            title: Tree title
            structure: Nested dictionary structure
        """
        tree = Tree(f"[bold]{title}[/bold]")
        self._add_tree_nodes(tree, structure)
        self.console.print(tree)
    
    def _add_tree_nodes(self, parent: Tree, structure: Dict[str, Any]):
        """Recursively add nodes to a tree.
        
        Args:
            parent: Parent tree node
            structure: Dictionary structure to add
        """
        for key, value in structure.items():
            if isinstance(value, dict):
                branch = parent.add(f"📁 {key}")
                self._add_tree_nodes(branch, value)
            elif isinstance(value, list):
                branch = parent.add(f"📁 {key}")
                for item in value:
                    branch.add(f"📄 {item}")
            else:
                parent.add(f"📄 {key}: {value}")
    
    def display_action_todos(self, todos: List[TodoItem], show_preview: bool = True):
        """Display action todos with rich formatting and progress tracking.
        
        Args:
            todos: List of todo items with action metadata
            show_preview: Whether to show action preview for pending items
        """
        if not todos:
            return
            
        self.console.print("\n[bold blue]📋 Action Queue[/bold blue]")
        
        # Group by status
        pending = [t for t in todos if t.status == "pending"]
        in_progress = [t for t in todos if t.status == "in_progress"]
        completed = [t for t in todos if t.status == "completed"]
        failed = [t for t in todos if t.status == "failed"]
        
        # Progress bar
        total = len(todos)
        done = len(completed)
        progress = int((done / total) * 20) if total > 0 else 0
        bar = "█" * progress + "░" * (20 - progress)
        
        self.console.print(f"\nProgress: [{bar}] {done}/{total} completed")
        
        # Status summary
        if in_progress:
            self.console.print(f"[yellow]⚡ {len(in_progress)} in progress[/yellow]")
        if failed:
            self.console.print(f"[red]⚠ {len(failed)} failed[/red]")
        
        # List todos with numbers
        for i, todo in enumerate(todos, 1):
            status_icon = {
                "pending": "[blue]●[/blue]",
                "in_progress": "[yellow]►[/yellow]",
                "completed": "[green]✓[/green]",
                "failed": "[red]✗[/red]"
            }[todo.status]
            
            # Color based on status
            color = {
                "pending": "white",
                "in_progress": "yellow",
                "completed": "green",
                "failed": "red"
            }[todo.status]
            
            # Strike through completed items
            if todo.status == "completed":
                self.console.print(f"\n[{color}]{i}. {status_icon} [strike]{todo.content}[/strike][/{color}]")
            else:
                self.console.print(f"\n[{color}]{i}. {status_icon} {todo.content}[/{color}]")
            
            # Show preview for pending items
            if show_preview and todo.status == "pending" and todo.metadata:
                if todo.metadata['type'] == 'command':
                    cmd = todo.metadata['action'].command
                    self.console.print(f"   [dim]└─ Will execute: $ {cmd}[/dim]")
                elif todo.metadata['type'] == 'file':
                    action = todo.metadata['action']
                    # Show file path and content info
                    if hasattr(action, 'content') and action.content:
                        lines = action.content.strip().split('\n')
                        self.console.print(f"   [dim]└─ Will create {len(lines)} lines of {action.language or 'text'}[/dim]")
            
            # Show error for failed items
            if todo.status == "failed" and todo.error:
                self.console.print(f"   [red]└─ Error: {todo.error}[/red]")
        
        # Show next action hint with better preview
        if pending:
            next_idx = next((i for i, t in enumerate(todos, 1) if t.status == "pending"), None)
            if next_idx:
                next_todo = todos[next_idx-1]
                self.console.print(f"\n[bold cyan]Next action ready:[/bold cyan]")
                
                # Show detailed preview based on action type
                if next_todo.metadata:
                    if next_todo.metadata['type'] == 'command':
                        cmd = next_todo.metadata['action'].command
                        desc = next_todo.metadata['action'].description
                        self.console.print(f"  [yellow]→ Execute command:[/yellow] {cmd}")
                        if desc:
                            self.console.print(f"    [dim]{desc}[/dim]")
                    elif next_todo.metadata['type'] == 'file':
                        action = next_todo.metadata['action']
                        self.console.print(f"  [green]→ {action.action_type.title()} file:[/green] {action.file_path}")
                        if hasattr(action, 'content') and action.content:
                            lines = len(action.content.strip().split('\n'))
                            self.console.print(f"    [dim]{lines} lines of {action.language or 'text'} content[/dim]")
                else:
                    self.console.print(f"  → {next_todo.content}")
                
                self.console.print("\n[bold]Press Enter to review and execute this action[/bold]")
                self.console.print("[dim]Or type a command (e.g., /help, /todo skip)[/dim]")
