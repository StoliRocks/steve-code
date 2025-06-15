"""File relationship analysis to automatically include related files."""

import ast
import re
from pathlib import Path
from typing import Set, List, Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class RelatedFilesManager:
    """Manages file relationships by analyzing dependencies."""
    
    # Common config file patterns
    CONFIG_PATTERNS = {
        'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', 'requirements-*.txt',
        'package.json', 'tsconfig.json', 'webpack.config.js', 'babel.config.js',
        'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle', 'Gemfile',
        'Makefile', 'CMakeLists.txt', 'Dockerfile', 'docker-compose.yml',
        '.env', '.env.example', 'config.json', 'config.yml', 'config.yaml',
        'jest.config.js', 'pytest.ini', 'tox.ini', '.eslintrc.js', '.prettierrc'
    }
    
    # Test file patterns
    TEST_PATTERNS = [
        (r'(.*)\.py$', [r'test_\1.py', r'tests/test_\1.py', r'\1_test.py']),
        (r'(.*)\.js$', [r'\1.test.js', r'\1.spec.js', r'__tests__/\1.js']),
        (r'(.*)\.ts$', [r'\1.test.ts', r'\1.spec.ts', r'__tests__/\1.ts']),
        (r'(.*)\.go$', [r'\1_test.go']),
        (r'(.*)\.rb$', [r'spec/\1_spec.rb', r'test/\1_test.rb']),
    ]
    
    def __init__(self, base_path: Path = None):
        """Initialize the smart context manager.
        
        Args:
            base_path: Base path for resolving relative imports
        """
        self.base_path = base_path or Path.cwd()
        
    def find_related_files(self, file_path: Path, max_depth: int = 2) -> Set[Path]:
        """Find files related to the given file.
        
        Args:
            file_path: The main file to analyze
            max_depth: Maximum depth for import resolution
            
        Returns:
            Set of related file paths
        """
        file_path = file_path.resolve()
        related_files = set()
        
        # Always include the main file
        related_files.add(file_path)
        
        # Find imports
        if file_path.suffix == '.py':
            imports = self._find_python_imports(file_path, max_depth)
            related_files.update(imports)
        elif file_path.suffix in ['.js', '.jsx', '.ts', '.tsx']:
            imports = self._find_javascript_imports(file_path, max_depth)
            related_files.update(imports)
        
        # Find test files
        test_files = self._find_test_files(file_path)
        related_files.update(test_files)
        
        # Find config files if this looks like a main module
        if self._is_main_module(file_path):
            config_files = self._find_config_files()
            related_files.update(config_files)
        
        return related_files
    
    def _find_python_imports(self, file_path: Path, max_depth: int, 
                           visited: Optional[Set[Path]] = None) -> Set[Path]:
        """Find Python imports recursively.
        
        Args:
            file_path: Python file to analyze
            max_depth: Maximum recursion depth
            visited: Set of already visited files
            
        Returns:
            Set of imported file paths
        """
        if visited is None:
            visited = set()
        
        if max_depth <= 0 or file_path in visited:
            return set()
        
        visited.add(file_path)
        imports = set()
        
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_path = self._resolve_python_import(alias.name, file_path)
                        if imported_path and imported_path.exists():
                            imports.add(imported_path)
                            # Recursively find imports
                            sub_imports = self._find_python_imports(
                                imported_path, max_depth - 1, visited
                            )
                            imports.update(sub_imports)
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_path = self._resolve_python_import(node.module, file_path)
                        if imported_path and imported_path.exists():
                            imports.add(imported_path)
                            sub_imports = self._find_python_imports(
                                imported_path, max_depth - 1, visited
                            )
                            imports.update(sub_imports)
        
        except Exception as e:
            logger.warning(f"Error parsing Python imports from {file_path}: {e}")
        
        return imports
    
    def _resolve_python_import(self, module_name: str, from_file: Path) -> Optional[Path]:
        """Resolve a Python module name to a file path.
        
        Args:
            module_name: Module name (e.g., 'package.module')
            from_file: File containing the import
            
        Returns:
            Resolved file path or None
        """
        # Try relative to the file's directory
        parts = module_name.split('.')
        current_dir = from_file.parent
        
        # Check for relative import in same package
        for i in range(len(parts)):
            test_path = current_dir
            for part in parts[i:]:
                test_path = test_path / part
            
            # Try as a Python file
            py_file = test_path.with_suffix('.py')
            if py_file.exists():
                return py_file
            
            # Try as a package
            init_file = test_path / '__init__.py'
            if init_file.exists():
                return init_file
            
            # Move up one directory for next iteration
            if i < len(parts) - 1:
                current_dir = current_dir.parent
        
        # Try from project root
        for part in parts:
            current_dir = self.base_path / part
        
        py_file = current_dir.with_suffix('.py')
        if py_file.exists():
            return py_file
        
        init_file = current_dir / '__init__.py'
        if init_file.exists():
            return init_file
        
        return None
    
    def _find_javascript_imports(self, file_path: Path, max_depth: int,
                               visited: Optional[Set[Path]] = None) -> Set[Path]:
        """Find JavaScript/TypeScript imports.
        
        Args:
            file_path: JS/TS file to analyze
            max_depth: Maximum recursion depth
            visited: Set of already visited files
            
        Returns:
            Set of imported file paths
        """
        if visited is None:
            visited = set()
        
        if max_depth <= 0 or file_path in visited:
            return set()
        
        visited.add(file_path)
        imports = set()
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Match import statements
            import_patterns = [
                r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'import\s*\([\'"]([^\'"]+)[\'"]\)',
                r'require\s*\([\'"]([^\'"]+)[\'"]\)',
                r'export\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    imported_path = self._resolve_javascript_import(match, file_path)
                    if imported_path and imported_path.exists():
                        imports.add(imported_path)
                        # Recursively find imports
                        sub_imports = self._find_javascript_imports(
                            imported_path, max_depth - 1, visited
                        )
                        imports.update(sub_imports)
        
        except Exception as e:
            logger.warning(f"Error parsing JS imports from {file_path}: {e}")
        
        return imports
    
    def _resolve_javascript_import(self, import_path: str, from_file: Path) -> Optional[Path]:
        """Resolve a JavaScript import path.
        
        Args:
            import_path: Import path (e.g., './module' or 'package')
            from_file: File containing the import
            
        Returns:
            Resolved file path or None
        """
        if import_path.startswith('.'):
            # Relative import
            base_dir = from_file.parent
            resolved = (base_dir / import_path).resolve()
        else:
            # Package import - try node_modules
            resolved = self.base_path / 'node_modules' / import_path
            if not resolved.exists():
                # Try as local module
                resolved = self.base_path / import_path
        
        # Try different extensions
        extensions = ['.js', '.jsx', '.ts', '.tsx', '.json']
        
        # Try exact path first
        if resolved.exists() and resolved.is_file():
            return resolved
        
        # Try with extensions
        for ext in extensions:
            with_ext = resolved.with_suffix(ext)
            if with_ext.exists():
                return with_ext
        
        # Try index files
        if resolved.is_dir():
            for index_name in ['index.js', 'index.jsx', 'index.ts', 'index.tsx']:
                index_file = resolved / index_name
                if index_file.exists():
                    return index_file
        
        return None
    
    def _find_test_files(self, file_path: Path) -> Set[Path]:
        """Find test files for the given source file.
        
        Args:
            file_path: Source file path
            
        Returns:
            Set of test file paths
        """
        test_files = set()
        file_name = file_path.name
        
        for pattern, test_formats in self.TEST_PATTERNS:
            match = re.match(pattern, file_name)
            if match:
                base_name = match.group(1)
                for test_format in test_formats:
                    test_name = re.sub(r'\\1', base_name, test_format)
                    
                    # Try in same directory
                    test_path = file_path.parent / test_name
                    if test_path.exists():
                        test_files.add(test_path)
                    
                    # Try in project root
                    test_path = self.base_path / test_name
                    if test_path.exists():
                        test_files.add(test_path)
        
        return test_files
    
    def _find_config_files(self) -> Set[Path]:
        """Find relevant config files in the project.
        
        Returns:
            Set of config file paths
        """
        config_files = set()
        
        for config_pattern in self.CONFIG_PATTERNS:
            # Check in project root
            config_path = self.base_path / config_pattern
            if config_path.exists():
                config_files.add(config_path)
            
            # Also check for wildcard patterns
            if '*' in config_pattern:
                for path in self.base_path.glob(config_pattern):
                    if path.is_file():
                        config_files.add(path)
        
        return config_files
    
    def _is_main_module(self, file_path: Path) -> bool:
        """Check if this appears to be a main module.
        
        Args:
            file_path: File to check
            
        Returns:
            True if this looks like a main module
        """
        indicators = [
            'main.py', 'app.py', 'server.py', 'cli.py', '__main__.py',
            'index.js', 'app.js', 'server.js', 'main.js',
            'main.go', 'main.rs', 'Main.java'
        ]
        
        return file_path.name in indicators or file_path.name.startswith('test_')
    
    def get_related_context(self, files: List[Path], max_total_files: int = 10) -> List[Path]:
        """Get a smart context by analyzing file relationships.
        
        Args:
            files: Initial list of files
            max_total_files: Maximum total files to include
            
        Returns:
            Ordered list of files to include in context
        """
        all_files = set()
        
        # Find related files for each input file
        for file_path in files:
            if file_path.exists():
                related = self.find_related_files(file_path)
                all_files.update(related)
        
        # Convert to list and sort by relevance
        file_list = list(all_files)
        
        # Sort: input files first, then imports, then tests, then configs
        def sort_key(path: Path) -> Tuple[int, str]:
            if path in files:
                return (0, str(path))
            elif any(test in path.name for test in ['test_', '_test', '.test.', '.spec.']):
                return (2, str(path))
            elif path.name in self.CONFIG_PATTERNS:
                return (3, str(path))
            else:
                return (1, str(path))
        
        file_list.sort(key=sort_key)
        
        # Limit to max files
        return file_list[:max_total_files]