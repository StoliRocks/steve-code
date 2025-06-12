"""Conversation history management."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .bedrock_client import Message


class ConversationHistory:
    """Manages conversation history and persistence."""
    
    def __init__(self, history_dir: Optional[Path] = None):
        """Initialize conversation history.
        
        Args:
            history_dir: Directory to store conversation history
        """
        if history_dir is None:
            history_dir = Path.home() / ".steve_code" / "history"
        
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        self.messages: List[Message] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.history_dir / f"session_{self.session_id}.json"
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        message = Message(role=role, content=content)
        self.messages.append(message)
        self._save_session()
    
    def clear(self):
        """Clear the conversation history."""
        self.messages = []
        self._save_session()
    
    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """Get messages from history.
        
        Args:
            limit: Maximum number of recent messages to return
            
        Returns:
            List of messages
        """
        if limit is None:
            return self.messages
        return self.messages[-limit:]
    
    def _save_session(self):
        """Save the current session to disk."""
        session_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in self.messages
            ]
        }
        
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    def load_session(self, session_file: Path) -> bool:
        """Load a previous session from disk.
        
        Args:
            session_file: Path to session file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.messages = [
                Message(role=msg["role"], content=msg["content"])
                for msg in session_data.get("messages", [])
            ]
            self.session_id = session_data.get("session_id", self.session_id)
            return True
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions.
        
        Returns:
            List of session information dictionaries
        """
        sessions = []
        for session_file in self.history_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        "file": session_file,
                        "session_id": data.get("session_id"),
                        "timestamp": data.get("timestamp"),
                        "message_count": len(data.get("messages", []))
                    })
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        
        return sorted(sessions, key=lambda x: x["timestamp"], reverse=True)
    
    def export_session(self, output_file: Path, format: str = "json"):
        """Export the current session to a file.
        
        Args:
            output_file: Path to export file
            format: Export format ('json' or 'markdown')
        """
        if format == "json":
            self._export_json(output_file)
        elif format == "markdown":
            self._export_markdown(output_file)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self, output_file: Path):
        """Export session as JSON."""
        session_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in self.messages
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    def _export_markdown(self, output_file: Path):
        """Export session as Markdown."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# AI Code Assistant Session\n\n")
            f.write(f"**Session ID:** {self.session_id}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for msg in self.messages:
                if msg.role == "user":
                    f.write(f"## User\n\n{msg.content}\n\n")
                else:
                    f.write(f"## Assistant\n\n{msg.content}\n\n")