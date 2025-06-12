"""Code block extraction and handling."""

import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class CodeBlock:
    """Represents an extracted code block."""
    language: str
    content: str
    filename: Optional[str] = None
    line_number: Optional[int] = None


class CodeExtractor:
    """Extracts and manages code blocks from text."""
    
    # Pattern to match code blocks with optional language
    CODE_BLOCK_PATTERN = re.compile(
        r'```(?P<lang>\w+)?\s*\n(?P<code>.*?)```',
        re.DOTALL | re.MULTILINE
    )
    
    # Pattern to match filename comments
    FILENAME_PATTERN = re.compile(
        r'#\s*(?:filename|file):\s*(?P<filename>[\w\-./]+)',
        re.IGNORECASE
    )
    
    def extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """Extract all code blocks from text.
        
        Args:
            text: Text containing code blocks
            
        Returns:
            List of extracted code blocks
        """
        code_blocks = []
        
        for match in self.CODE_BLOCK_PATTERN.finditer(text):
            language = match.group('lang') or 'text'
            content = match.group('code')
            
            # Check for filename in the code content
            filename = None
            filename_match = self.FILENAME_PATTERN.search(content)
            if filename_match:
                filename = filename_match.group('filename')
                # Remove the filename comment from content
                content = self.FILENAME_PATTERN.sub('', content).strip()
            
            code_blocks.append(CodeBlock(
                language=language,
                content=content,
                filename=filename
            ))
        
        return code_blocks
    
    def format_code_block(self, code: str, language: str = "text") -> str:
        """Format code as a markdown code block.
        
        Args:
            code: Code content
            language: Programming language
            
        Returns:
            Formatted code block
        """
        return f"```{language}\n{code}\n```"
    
    def save_code_blocks(
        self,
        code_blocks: List[CodeBlock],
        output_dir: Path,
        auto_name: bool = True
    ) -> List[Path]:
        """Save code blocks to files.
        
        Args:
            code_blocks: List of code blocks to save
            output_dir: Directory to save files
            auto_name: Whether to auto-generate filenames
            
        Returns:
            List of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        for i, block in enumerate(code_blocks):
            if block.filename:
                filename = block.filename
            elif auto_name:
                ext = self._get_file_extension(block.language)
                filename = f"code_block_{i + 1}{ext}"
            else:
                continue
            
            file_path = output_dir / filename
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(block.content)
            
            saved_files.append(file_path)
        
        return saved_files
    
    def _get_file_extension(self, language: str) -> str:
        """Get file extension for a programming language.
        
        Args:
            language: Programming language name
            
        Returns:
            File extension with dot
        """
        extensions = {
            'python': '.py',
            'py': '.py',
            'javascript': '.js',
            'js': '.js',
            'typescript': '.ts',
            'ts': '.ts',
            'java': '.java',
            'c': '.c',
            'cpp': '.cpp',
            'c++': '.cpp',
            'csharp': '.cs',
            'cs': '.cs',
            'go': '.go',
            'rust': '.rs',
            'ruby': '.rb',
            'rb': '.rb',
            'php': '.php',
            'swift': '.swift',
            'kotlin': '.kt',
            'scala': '.scala',
            'r': '.r',
            'matlab': '.m',
            'bash': '.sh',
            'sh': '.sh',
            'shell': '.sh',
            'powershell': '.ps1',
            'ps1': '.ps1',
            'sql': '.sql',
            'html': '.html',
            'css': '.css',
            'xml': '.xml',
            'json': '.json',
            'yaml': '.yaml',
            'yml': '.yml',
            'toml': '.toml',
            'ini': '.ini',
            'markdown': '.md',
            'md': '.md',
            'dockerfile': '.dockerfile',
            'docker': '.dockerfile',
            'makefile': '.makefile',
            'make': '.makefile',
        }
        
        return extensions.get(language.lower(), '.txt')
    
    def highlight_code(self, code: str, language: str = "text") -> str:
        """Apply syntax highlighting to code (placeholder for future enhancement).
        
        Args:
            code: Code content
            language: Programming language
            
        Returns:
            Highlighted code (currently just returns the code)
        """
        # This is a placeholder for future syntax highlighting
        # Could integrate with pygments or similar library
        return code
    
    def detect_language(self, code: str) -> str:
        """Attempt to detect the programming language of code.
        
        Args:
            code: Code content
            
        Returns:
            Detected language or 'text'
        """
        # Simple heuristic-based detection
        patterns = {
            'python': [r'def\s+\w+\s*\(', r'import\s+\w+', r'from\s+\w+\s+import'],
            'javascript': [r'function\s+\w+\s*\(', r'const\s+\w+\s*=', r'let\s+\w+\s*='],
            'java': [r'public\s+class\s+\w+', r'private\s+\w+\s+\w+', r'import\s+java\.'],
            'c': [r'#include\s*<\w+\.h>', r'int\s+main\s*\(', r'typedef\s+struct'],
            'cpp': [r'#include\s*<\w+>', r'using\s+namespace\s+std', r'class\s+\w+\s*{'],
            'shell': [r'#!/bin/bash', r'#!/bin/sh', r'\$\(\w+\)'],
        }
        
        for language, patterns_list in patterns.items():
            for pattern in patterns_list:
                if re.search(pattern, code, re.MULTILINE):
                    return language
        
        return 'text'