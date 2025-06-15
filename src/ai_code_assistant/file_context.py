"""File context handling for including files in prompts."""

import os
from pathlib import Path
from typing import List, Optional, Dict, Set
import mimetypes
import logging
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.console import Console

from .smart_context import SmartContextManager


class FileContextManager:
    """Manages file context for AI prompts."""
    
    # Default file size limit (10MB)
    DEFAULT_SIZE_LIMIT = 10 * 1024 * 1024
    
    # Common text file extensions
    TEXT_EXTENSIONS = {
        '.txt', '.md', '.rst', '.log', '.csv', '.json', '.xml', '.yaml', '.yml',
        '.toml', '.ini', '.cfg', '.conf', '.properties', '.env',
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cc',
        '.cxx', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift',
        '.kt', '.scala', '.r', '.m', '.sh', '.bash', '.zsh', '.fish',
        '.ps1', '.bat', '.cmd', '.sql', '.html', '.htm', '.css', '.scss',
        '.sass', '.less', '.vue', '.svelte', '.astro',
        '.dockerfile', '.dockerignore', '.gitignore', '.gitattributes',
        '.editorconfig', '.prettierrc', '.eslintrc', '.babelrc',
        'makefile', 'cmakelists.txt', 'requirements.txt', 'package.json',
        'cargo.toml', 'go.mod', 'pom.xml', 'build.gradle', 'gemfile'
    }
    
    def __init__(self, size_limit: int = DEFAULT_SIZE_LIMIT, show_progress: bool = True, 
                 use_smart_context: bool = True):
        """Initialize the file context manager.
        
        Args:
            size_limit: Maximum file size in bytes
            show_progress: Whether to show progress indicators
            use_smart_context: Whether to use smart context analysis
        """
        self.size_limit = size_limit
        self.logger = logging.getLogger(__name__)
        self.console = Console()
        self.show_progress = show_progress
        self.use_smart_context = use_smart_context
        self.smart_context = SmartContextManager() if use_smart_context else None
    
    def read_file(self, file_path: Path) -> Optional[str]:
        """Read a file's content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content or None if unable to read
        """
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return None
        
        if not file_path.is_file():
            self.logger.error(f"Not a file: {file_path}")
            return None
        
        if file_path.stat().st_size > self.size_limit:
            self.logger.error(f"File too large: {file_path} (>{self.size_limit} bytes)")
            return None
        
        if not self._is_text_file(file_path):
            self.logger.error(f"Not a text file: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            self.logger.error(f"Unable to decode file: {file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if a file is likely a text file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if likely a text file
        """
        # Check by extension first
        if file_path.suffix.lower() in self.TEXT_EXTENSIONS:
            return True
        
        # Check by mime type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith('text/'):
            return True
        
        # Check by reading first few bytes
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(512)
                if b'\0' in chunk:
                    return False  # Binary file
                
                # Try to decode as UTF-8
                try:
                    chunk.decode('utf-8')
                    return True
                except UnicodeDecodeError:
                    return False
        except Exception:
            return False
    
    def format_file_content(self, file_path: Path, content: str) -> str:
        """Format file content for inclusion in prompt.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            Formatted content with file header
        """
        return f"=== File: {file_path} ===\n{content}\n=== End of {file_path} ==="
    
    def read_multiple_files(self, file_paths: List[Path]) -> Dict[Path, Optional[str]]:
        """Read multiple files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary mapping file paths to their content
        """
        results = {}
        for file_path in file_paths:
            results[file_path] = self.read_file(file_path)
        return results
    
    def create_context_from_files(self, file_paths: List[Path], include_related: bool = True) -> str:
        """Create a formatted context string from multiple files with progress indication.
        
        Args:
            file_paths: List of file paths
            include_related: Whether to include related files (imports, tests, configs)
            
        Returns:
            Formatted context string
        """
        if not file_paths:
            return ""
        
        # Use smart context if enabled
        original_count = len(file_paths)
        if self.use_smart_context and self.smart_context and include_related:
            file_paths = self.smart_context.get_smart_context(file_paths)
            if len(file_paths) > original_count:
                self.console.print(f"[dim]Including {len(file_paths) - original_count} related files[/dim]")
        
        context_parts = []
        
        if self.show_progress and len(file_paths) > 1:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task("Reading files...", total=len(file_paths))
                
                for file_path in file_paths:
                    progress.update(task, description=f"Reading {file_path.name}")
                    # Skip image files - they should be handled separately
                    if file_path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}:
                        self.logger.debug(f"Skipping image file: {file_path}")
                        progress.advance(task)
                        continue
                    content = self.read_file(file_path)
                    if content is not None:
                        context_parts.append(self.format_file_content(file_path, content))
                    progress.advance(task)
        else:
            # No progress bar for single file or when disabled
            for file_path in file_paths:
                # Skip image files - they should be handled separately
                if file_path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}:
                    self.logger.debug(f"Skipping image file: {file_path}")
                    continue
                content = self.read_file(file_path)
                if content is not None:
                    context_parts.append(self.format_file_content(file_path, content))
        
        return "\n\n".join(context_parts)
    
    def find_files(
        self,
        pattern: str,
        root_dir: Path = Path.cwd(),
        recursive: bool = True,
        exclude_dirs: Optional[Set[str]] = None
    ) -> List[Path]:
        """Find files matching a pattern.
        
        Args:
            pattern: File pattern (glob-style)
            root_dir: Root directory to search
            recursive: Whether to search recursively
            exclude_dirs: Set of directory names to exclude
            
        Returns:
            List of matching file paths
        """
        if exclude_dirs is None:
            exclude_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}
        
        root_dir = Path(root_dir).resolve()
        
        if recursive:
            pattern = f"**/{pattern}"
        
        matches = []
        for path in root_dir.glob(pattern):
            # Skip if in excluded directory
            if any(excluded in path.parts for excluded in exclude_dirs):
                continue
            
            if path.is_file():
                matches.append(path)
        
        return sorted(matches)
    
    def get_directory_tree(
        self,
        root_dir: Path = Path.cwd(),
        max_depth: int = 3,
        exclude_dirs: Optional[Set[str]] = None
    ) -> str:
        """Get a directory tree representation.
        
        Args:
            root_dir: Root directory
            max_depth: Maximum depth to traverse
            exclude_dirs: Set of directory names to exclude
            
        Returns:
            String representation of directory tree
        """
        if exclude_dirs is None:
            exclude_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}
        
        root_dir = Path(root_dir).resolve()
        tree_lines = [f"{root_dir.name}/"]
        
        def _build_tree(path: Path, prefix: str = "", depth: int = 0):
            if depth >= max_depth:
                return
            
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return
            
            for i, item in enumerate(items):
                if item.name in exclude_dirs:
                    continue
                
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "
                
                if item.is_dir():
                    tree_lines.append(f"{prefix}{current_prefix}{item.name}/")
                    _build_tree(item, prefix + next_prefix, depth + 1)
                else:
                    tree_lines.append(f"{prefix}{current_prefix}{item.name}")
        
        _build_tree(root_dir)
        return "\n".join(tree_lines)