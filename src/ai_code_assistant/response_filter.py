"""Filter response content to hide implementation details from users."""

import re
from typing import Tuple, Optional


class ResponseFilter:
    """Filters AI responses to hide technical implementation details."""
    
    def __init__(self):
        # Pattern to detect action blocks
        self.action_pattern = re.compile(r'<actions>.*?</actions>', re.DOTALL)
        self.in_action_block = False
        self.buffer = ""
        
    def filter_chunk(self, chunk: str) -> Tuple[str, bool]:
        """Filter a streaming chunk of text.
        
        Args:
            chunk: The text chunk to filter
            
        Returns:
            Tuple of (filtered_chunk, found_actions)
        """
        self.buffer += chunk
        output = ""
        found_actions = False
        
        # Check if we're starting an action block
        if '<actions>' in self.buffer and not self.in_action_block:
            # Output everything before the action block
            pre_action = self.buffer.split('<actions>')[0]
            output = pre_action
            self.in_action_block = True
            found_actions = True
            # Keep the rest in buffer
            self.buffer = '<actions>' + self.buffer.split('<actions>', 1)[1]
        
        # If we're in an action block, look for the end
        elif self.in_action_block:
            if '</actions>' in self.buffer:
                # Skip the entire action block
                post_action = self.buffer.split('</actions>', 1)[1]
                self.buffer = post_action
                self.in_action_block = False
                # Don't output anything from the action block
            # else: still in action block, keep buffering
        
        # Not in action block, output normally
        else:
            output = self.buffer
            self.buffer = ""
            
        return output, found_actions
    
    def get_remaining(self) -> str:
        """Get any remaining buffered content."""
        if self.in_action_block:
            # Still in an action block at the end - shouldn't happen with valid XML
            return ""
        return self.buffer