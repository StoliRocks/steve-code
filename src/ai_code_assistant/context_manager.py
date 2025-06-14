"""Context size management and auto-compaction."""

import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
import tiktoken

logger = logging.getLogger(__name__)


@dataclass
class ContextStats:
    """Statistics about current context usage."""
    total_tokens: int
    max_tokens: int
    remaining_tokens: int
    usage_percentage: float
    message_count: int
    should_compact: bool
    
    @property
    def formatted_status(self) -> str:
        """Get formatted status string."""
        return (f"{self.total_tokens:,}/{self.max_tokens:,} tokens "
                f"({self.usage_percentage:.1f}% used, "
                f"{self.remaining_tokens:,} remaining)")


class ContextManager:
    """Manages conversation context size and automatic compaction."""
    
    # Default thresholds
    DEFAULT_COMPACT_THRESHOLD = 0.8  # Compact when 80% full
    DEFAULT_WARNING_THRESHOLD = 0.7  # Warn when 70% full
    
    # Approximate tokens per character (conservative estimate)
    TOKENS_PER_CHAR = 0.25
    
    def __init__(self, max_tokens: int = 128000, 
                 compact_threshold: float = DEFAULT_COMPACT_THRESHOLD,
                 warning_threshold: float = DEFAULT_WARNING_THRESHOLD):
        """Initialize context manager.
        
        Args:
            max_tokens: Maximum context tokens
            compact_threshold: Threshold to trigger auto-compact (0-1)
            warning_threshold: Threshold to show warnings (0-1)
        """
        self.max_tokens = max_tokens
        self.compact_threshold = compact_threshold
        self.warning_threshold = warning_threshold
        
        # Try to use tiktoken for accurate counting
        self.encoder = None
        try:
            # Use cl100k_base encoding (GPT-4/Claude compatible)
            self.encoder = tiktoken.get_encoding("cl100k_base")
            logger.info("Using tiktoken for accurate token counting")
        except Exception as e:
            logger.warning(f"tiktoken not available, using estimation: {e}")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: Text to count
            
        Returns:
            Number of tokens
        """
        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except Exception:
                # Fallback to estimation
                pass
        
        # Estimate tokens from character count
        return int(len(text) * self.TOKENS_PER_CHAR)
    
    def count_message_tokens(self, messages: List[dict]) -> int:
        """Count total tokens in messages.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Total token count
        """
        total = 0
        
        for msg in messages:
            # Add message overhead (role, formatting)
            total += 4  # Approximate overhead per message
            
            content = msg.get('content', '')
            if isinstance(content, str):
                total += self.count_tokens(content)
            elif isinstance(content, list):
                # Multimodal content
                for block in content:
                    if block.get('type') == 'text':
                        total += self.count_tokens(block.get('text', ''))
                    elif block.get('type') == 'image':
                        # Images consume significant tokens
                        total += 1000  # Conservative estimate per image
        
        return total
    
    def get_context_stats(self, messages: List[dict]) -> ContextStats:
        """Get current context statistics.
        
        Args:
            messages: Current conversation messages
            
        Returns:
            Context statistics
        """
        total_tokens = self.count_message_tokens(messages)
        remaining = self.max_tokens - total_tokens
        usage_pct = (total_tokens / self.max_tokens) * 100
        
        return ContextStats(
            total_tokens=total_tokens,
            max_tokens=self.max_tokens,
            remaining_tokens=max(0, remaining),
            usage_percentage=usage_pct,
            message_count=len(messages),
            should_compact=usage_pct >= (self.compact_threshold * 100)
        )
    
    def should_warn(self, stats: ContextStats) -> bool:
        """Check if we should warn about context size.
        
        Args:
            stats: Current context stats
            
        Returns:
            True if warning should be shown
        """
        return stats.usage_percentage >= (self.warning_threshold * 100)
    
    def compact_messages(self, messages: List[dict], keep_recent: int = 10) -> List[dict]:
        """Compact messages to reduce context size.
        
        Args:
            messages: Messages to compact
            keep_recent: Number of recent messages to keep in full
            
        Returns:
            Compacted messages
        """
        if len(messages) <= keep_recent:
            return messages
        
        # Keep system messages and recent messages
        compacted = []
        
        # Keep any system messages
        for msg in messages:
            if msg.get('role') == 'system':
                compacted.append(msg)
        
        # Summarize older messages
        older_messages = messages[:-keep_recent]
        older_content = []
        
        for msg in older_messages:
            if msg.get('role') != 'system':
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if isinstance(content, str):
                    # Truncate long messages
                    if len(content) > 500:
                        content = content[:500] + "..."
                    older_content.append(f"{role}: {content}")
        
        if older_content:
            summary = {
                'role': 'system',
                'content': (f"[Previous conversation summary - {len(older_messages)} messages]\n" +
                           "\n".join(older_content[:5]) +  # Show first 5
                           f"\n... and {len(older_content) - 5} more messages")
            }
            compacted.append(summary)
        
        # Add recent messages in full
        compacted.extend(messages[-keep_recent:])
        
        return compacted
    
    def estimate_tokens_for_content(self, text: str = "", 
                                  images: int = 0, 
                                  files: int = 0) -> int:
        """Estimate tokens for planned content.
        
        Args:
            text: Text content
            images: Number of images
            files: Number of files
            
        Returns:
            Estimated token count
        """
        total = 0
        
        if text:
            total += self.count_tokens(text)
        
        # Estimates for other content
        total += images * 1000  # ~1k tokens per image
        total += files * 500    # ~500 tokens per file
        
        return total
    
    def get_auto_compact_status(self, enabled: bool, stats: ContextStats) -> str:
        """Get auto-compact status message.
        
        Args:
            enabled: Whether auto-compact is enabled
            stats: Current context stats
            
        Returns:
            Status message
        """
        if not enabled:
            return "Auto-compact: Disabled"
        
        if stats.should_compact:
            return f"Auto-compact: Ready to trigger (>{self.compact_threshold*100:.0f}% full)"
        else:
            tokens_until = int(self.max_tokens * self.compact_threshold) - stats.total_tokens
            return f"Auto-compact: Enabled (triggers in ~{tokens_until:,} tokens)"