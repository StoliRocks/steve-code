"""Automatic detection of URLs and file paths in user input."""

import re
from pathlib import Path
from typing import List, Tuple, Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class AutoDetector:
    """Detects and extracts URLs and file paths from text."""
    
    # URL regex pattern
    URL_PATTERN = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}'
        r'\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)',
        re.IGNORECASE
    )
    
    # File path patterns
    FILE_PATH_PATTERNS = [
        # Absolute paths
        re.compile(r'(?:^|\s)(/[\w\-./]+\.\w+)(?:\s|$)'),
        # Relative paths with extension
        re.compile(r'(?:^|\s)((?:\w+/)*\w+\.\w+)(?:\s|$)'),
        # Windows paths
        re.compile(r'(?:^|\s)([A-Za-z]:\\[\w\-\\./]+\.\w+)(?:\s|$)'),
        # Quoted paths
        re.compile(r'["\']([^"\']+\.\w+)["\']'),
        # Paths in backticks
        re.compile(r'`([^`]+\.\w+)`'),
    ]
    
    # Common image extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}
    
    # Common code/doc extensions to check
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
        '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r',
        '.html', '.css', '.scss', '.json', '.xml', '.yaml', '.yml',
        '.md', '.rst', '.txt', '.log', '.csv', '.sql'
    }
    
    def __init__(self, auto_fetch_urls: bool = True, auto_detect_images: bool = True,
                 auto_detect_files: bool = False):
        """Initialize the auto detector.
        
        Args:
            auto_fetch_urls: Whether to automatically fetch URLs
            auto_detect_images: Whether to automatically detect image paths
            auto_detect_files: Whether to automatically detect other file paths
        """
        self.auto_fetch_urls = auto_fetch_urls
        self.auto_detect_images = auto_detect_images
        self.auto_detect_files = auto_detect_files
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text.
        
        Args:
            text: Input text
            
        Returns:
            List of unique URLs found
        """
        if not self.auto_fetch_urls:
            return []
        
        urls = self.URL_PATTERN.findall(text)
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def extract_file_paths(self, text: str) -> Tuple[List[Path], List[Path]]:
        """Extract file paths from text.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (image_paths, other_file_paths)
        """
        all_paths = set()
        
        # Extract paths using various patterns
        for pattern in self.FILE_PATH_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                # Clean up the path
                path_str = match.strip().strip('"\'`')
                if path_str:
                    all_paths.add(path_str)
        
        # Filter and categorize paths
        image_paths = []
        other_paths = []
        
        for path_str in all_paths:
            try:
                path = Path(path_str)
                
                # Check if it's a valid path that exists
                if path.exists() and path.is_file():
                    ext = path.suffix.lower()
                    
                    if ext in self.IMAGE_EXTENSIONS and self.auto_detect_images:
                        image_paths.append(path)
                        logger.info(f"Auto-detected image: {path}")
                    elif ext in self.CODE_EXTENSIONS and self.auto_detect_files:
                        other_paths.append(path)
                        logger.info(f"Auto-detected file: {path}")
                elif not path.is_absolute():
                    # Try relative to current directory
                    abs_path = Path.cwd() / path
                    if abs_path.exists() and abs_path.is_file():
                        ext = abs_path.suffix.lower()
                        
                        if ext in self.IMAGE_EXTENSIONS and self.auto_detect_images:
                            image_paths.append(abs_path)
                            logger.info(f"Auto-detected image: {abs_path}")
                        elif ext in self.CODE_EXTENSIONS and self.auto_detect_files:
                            other_paths.append(abs_path)
                            logger.info(f"Auto-detected file: {abs_path}")
            except Exception as e:
                logger.debug(f"Invalid path {path_str}: {e}")
                continue
        
        return image_paths, other_paths
    
    def extract_all(self, text: str) -> dict:
        """Extract all detectable content from text.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with urls, image_paths, and file_paths
        """
        urls = self.extract_urls(text)
        image_paths, file_paths = self.extract_file_paths(text)
        
        return {
            'urls': urls,
            'image_paths': image_paths,
            'file_paths': file_paths
        }
    
    def format_detection_summary(self, detections: dict) -> str:
        """Format a summary of what was detected.
        
        Args:
            detections: Dictionary from extract_all
            
        Returns:
            Formatted summary string
        """
        parts = []
        
        if detections['urls']:
            parts.append(f"{len(detections['urls'])} URL(s)")
        if detections['image_paths']:
            parts.append(f"{len(detections['image_paths'])} image(s)")
        if detections['file_paths']:
            parts.append(f"{len(detections['file_paths'])} file(s)")
        
        if parts:
            return f"Auto-detected: {', '.join(parts)}"
        return ""