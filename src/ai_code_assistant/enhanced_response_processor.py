"""Enhanced response processor with tool output formatting like Claude Code."""

import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.markdown import Markdown
import json


@dataclass
class ToolCall:
    """Represents a tool call from the AI."""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[str] = None


@dataclass
class ResponseSection:
    """A section of the response."""
    type: str  # 'text', 'tool', 'code', 'thinking'
    content: Any  # String for text, ToolCall for tools, etc.
    collapsed: bool = False
    

class EnhancedResponseProcessor:
    """Process AI responses with Claude Code-style tool formatting."""
    
    def __init__(self, console: Console, verbose: bool = False):
        """Initialize the processor.
        
        Args:
            console: Rich console for output
            verbose: Show all details including thinking/analysis
        """
        self.console = console
        self.verbose = verbose
        self.collapsed_content = []  # Store collapsed content for expansion
        
        # Patterns for different response elements
        self.tool_call_pattern = re.compile(
            r'<function_calls>.*?