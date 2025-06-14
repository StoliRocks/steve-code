"""Custom command completer for interactive mode."""

from typing import Iterable, Dict
from prompt_toolkit.completion import Completer, Completion, PathCompleter, merge_completers
from prompt_toolkit.document import Document
from pathlib import Path


class CommandCompleter(Completer):
    """Custom completer that handles commands and file paths."""
    
    def __init__(self, commands: Dict[str, str]):
        """Initialize the command completer.
        
        Args:
            commands: Dictionary of commands and their descriptions
        """
        self.commands = commands
        self.path_completer = PathCompleter(expanduser=True)
        
        # Commands that accept file paths
        self.file_commands = {'/files', '/image', '/tree'}
    
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Get completions for the current input."""
        text = document.text_before_cursor
        
        # If we're at the beginning or after a space, complete commands
        if not text or text[-1] == ' ':
            # Check if we should complete file paths
            words = text.strip().split()
            if words and words[0] in self.file_commands:
                # Complete file paths
                # Create a new document with just the path part
                path_start = len(' '.join(words[:-1])) + 1 if len(words) > 1 else len(words[0]) + 1
                path_text = text[path_start:] if path_start < len(text) else ''
                path_doc = Document(path_text, len(path_text))
                
                for completion in self.path_completer.get_completions(path_doc, complete_event):
                    yield completion
            elif not words:
                # Complete commands at the start
                for cmd, desc in self.commands.items():
                    yield Completion(
                        cmd,
                        start_position=0,
                        display=cmd,
                        display_meta=desc[:50] + '...' if len(desc) > 50 else desc
                    )
        else:
            # Complete commands that start with the current text
            words = text.split()
            if len(words) == 1 and words[0].startswith('/'):
                # Completing a command
                for cmd, desc in self.commands.items():
                    if cmd.startswith(words[0]):
                        yield Completion(
                            cmd,
                            start_position=-len(words[0]),
                            display=cmd,
                            display_meta=desc[:50] + '...' if len(desc) > 50 else desc
                        )
            elif words and words[0] in self.file_commands:
                # Completing file paths after a file command
                # Get just the current path being typed
                if len(words) > 1:
                    current_path = words[-1]
                    path_doc = Document(current_path, len(current_path))
                    
                    for completion in self.path_completer.get_completions(path_doc, complete_event):
                        # Adjust the start position
                        yield Completion(
                            completion.text,
                            start_position=-len(current_path),
                            display=completion.display,
                            display_meta=completion.display_meta
                        )


class SmartPathCompleter(Completer):
    """Enhanced path completer with smart filtering."""
    
    def __init__(self):
        """Initialize the smart path completer."""
        self.path_completer = PathCompleter(
            expanduser=True,
            file_filter=self._file_filter
        )
        
        # Common ignore patterns
        self.ignore_dirs = {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv', 
            'env', '.env', 'dist', 'build', '.pytest_cache', '.mypy_cache'
        }
        
        # Common file patterns to show
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt',
            '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd',
            '.html', '.css', '.scss', '.sass', '.less',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini',
            '.md', '.rst', '.txt', '.log',
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp'
        }
    
    def _file_filter(self, path: str) -> bool:
        """Filter files to show in completion.
        
        Args:
            path: Path to check
            
        Returns:
            True if the file should be shown
        """
        p = Path(path)
        
        # Always show directories (unless ignored)
        if p.is_dir():
            return p.name not in self.ignore_dirs
        
        # Show files with relevant extensions
        return p.suffix.lower() in self.code_extensions or p.name in {
            'Makefile', 'Dockerfile', 'requirements.txt', 'package.json',
            'Cargo.toml', 'go.mod', '.gitignore', '.dockerignore'
        }
    
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Get smart path completions."""
        return self.path_completer.get_completions(document, complete_event)