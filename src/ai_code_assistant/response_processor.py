"""Process and clean AI responses before display."""

import re
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ProcessedResponse:
    """Container for processed response data."""
    clean_text: str
    has_actions: bool
    action_count: int
    original_length: int
    cleaned_length: int


class ResponseProcessor:
    """Process AI responses to hide implementation details and format for display."""
    
    def __init__(self, verbose_mode: bool = False):
        """Initialize processor.
        
        Args:
            verbose_mode: If True, show all content including technical details
        """
        self.verbose_mode = verbose_mode
        
        # Patterns to remove in non-verbose mode
        self.action_pattern = re.compile(r'<actions>.*?</actions>', re.DOTALL | re.IGNORECASE)
        self.thinking_pattern = re.compile(r'<thinking>.*?</thinking>', re.DOTALL | re.IGNORECASE)
        self.analysis_pattern = re.compile(r'<analysis>.*?</analysis>', re.DOTALL | re.IGNORECASE)
        
        # Pattern to detect if response contains actions
        self.has_actions_pattern = re.compile(r'<actions>', re.IGNORECASE)
        
    def process(self, response: str) -> ProcessedResponse:
        """Process a complete response.
        
        Args:
            response: The raw AI response
            
        Returns:
            ProcessedResponse with cleaned text and metadata
        """
        if self.verbose_mode:
            # In verbose mode, return original
            return ProcessedResponse(
                clean_text=response,
                has_actions=bool(self.has_actions_pattern.search(response)),
                action_count=response.count('<action'),
                original_length=len(response),
                cleaned_length=len(response)
            )
        
        # Clean the response
        original_length = len(response)
        has_actions = bool(self.has_actions_pattern.search(response))
        action_count = response.count('<action')
        
        # Remove action blocks
        clean_text = self.action_pattern.sub('', response)
        
        # Remove thinking blocks (if any)
        clean_text = self.thinking_pattern.sub('', clean_text)
        
        # Remove analysis blocks that aren't meant for users
        clean_text = self.analysis_pattern.sub('', clean_text)
        
        # Clean up extra newlines left by removal
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
        clean_text = clean_text.strip()
        
        # If we removed everything, provide a minimal response
        if not clean_text and has_actions:
            clean_text = "I'll help you with that. Let me process the actions..."
        
        return ProcessedResponse(
            clean_text=clean_text,
            has_actions=has_actions,
            action_count=action_count,
            original_length=original_length,
            cleaned_length=len(clean_text)
        )
    
    def format_for_display(self, processed: ProcessedResponse) -> str:
        """Format processed response for display.
        
        Args:
            processed: The processed response
            
        Returns:
            Formatted text ready for display
        """
        text = processed.clean_text
        
        # Add action summary if actions were found and hidden
        if processed.has_actions and not self.verbose_mode:
            if processed.action_count > 0:
                action_text = "action" if processed.action_count == 1 else "actions"
                text += f"\n\n[dim]📋 {processed.action_count} {action_text} ready to execute[/dim]"
        
        return text
    
    def extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """Extract code blocks from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            List of dicts with 'language' and 'code' keys
        """
        code_pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
        blocks = []
        
        for match in code_pattern.finditer(text):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            blocks.append({
                'language': language,
                'code': code
            })
        
        return blocks