"""Project analyzer for intelligent code repository understanding."""

import os
import re
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import fnmatch
import mimetypes

logger = logging.getLogger(__name__)


@dataclass
class ProjectInfo:
    """Information about a detected project."""
    root_path: Path
    project_type: str  # python, javascript, java, etc.
    framework: Optional[str] = None  # django, react, spring, etc.
    build_files: List[Path] = None
    main_directories: List[Path] = None
    test_directories: List[Path] = None
    config_files: List[Path] = None
    
    def __post_init__(self):
        if self.build_files is None:
            self.build_files = []
        if self.main_directories is None:
            self.main_directories = []
        if self.test_directories is None:
            self.test_directories = []
        if self.config_files is None:
            self.config_files = []


class ProjectAnalyzer:
    """Analyzes code repositories to understand structure and find relevant files."""
    
    # Project detection patterns
    PROJECT_MARKERS = {
        'python': {
            'files': ['setup.py', 'pyproject.toml', 'requirements.txt', 'Pipfile', 'poetry.lock'],
            'dirs': ['src', 'tests', 'test', '__pycache__'],
            'frameworks': {
                'django': ['manage.py', 'settings.py', 'urls.py'],
                'flask': ['app.py', 'application.py'],
                'fastapi': ['main.py', 'api/'],
                'pytest': ['pytest.ini', 'conftest.py'],
            }
        },
        'javascript': {
            'files': ['package.json', 'yarn.lock', 'npm-shrinkwrap.json'],
            'dirs': ['node_modules', 'src', 'test', 'tests', 'dist', 'build'],
            'frameworks': {
                'react': ['public/', 'src/App.js', 'src/App.jsx', 'src/App.tsx'],
                'vue': ['vue.config.js', 'src/App.vue'],
                'angular': ['angular.json', 'src/app/'],
                'next': ['next.config.js', 'pages/'],
                'express': ['routes/', 'server.js', 'app.js'],
            }
        },
        'typescript': {
            'files': ['tsconfig.json', 'package.json'],
            'dirs': ['src', 'test', 'tests', 'dist', 'build'],
            'frameworks': {}  # Inherits from javascript
        },
        'java': {
            'files': ['pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle'],
            'dirs': ['src/main/java', 'src/test/java', 'target', 'build'],
            'frameworks': {
                'spring': ['src/main/resources/application.properties', 'src/main/resources/application.yml'],
                'maven': ['pom.xml'],
                'gradle': ['build.gradle', 'build.gradle.kts'],
            }
        },
        'go': {
            'files': ['go.mod', 'go.sum'],
            'dirs': ['cmd', 'pkg', 'internal', 'vendor'],
            'frameworks': {}
        },
        'rust': {
            'files': ['Cargo.toml', 'Cargo.lock'],
            'dirs': ['src', 'target', 'tests'],
            'frameworks': {}
        },
        'ruby': {
            'files': ['Gemfile', 'Gemfile.lock', 'Rakefile'],
            'dirs': ['lib', 'spec', 'test'],
            'frameworks': {
                'rails': ['config/routes.rb', 'app/', 'db/'],
                'sinatra': ['config.ru'],
            }
        }
    }
    
    # Common ignore patterns
    IGNORE_PATTERNS = [
        '*.pyc', '__pycache__', '*.pyo', '*.pyd', '.Python',
        'node_modules', 'bower_components', '.npm',
        '.git', '.svn', '.hg', '.bzr',
        '.vscode', '.idea', '*.swp', '*.swo', '*~',
        '.DS_Store', 'Thumbs.db',
        'venv', 'env', '.env', 'virtualenv', '.venv',
        'dist', 'build', 'target', '*.egg-info',
        '.cache', '.pytest_cache', '.coverage', 'htmlcov',
        '*.log', '*.tmp', '*.temp',
    ]
    
    # File extensions by category
    CODE_EXTENSIONS = {
        'python': ['.py', '.pyw', '.pyx', '.pxd', '.pxi'],
        'javascript': ['.js', '.jsx', '.mjs', '.cjs'],
        'typescript': ['.ts', '.tsx'],
        'java': ['.java'],
        'c_cpp': ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx'],
        'go': ['.go'],
        'rust': ['.rs'],
        'ruby': ['.rb', '.rake'],
        'php': ['.php'],
        'swift': ['.swift'],
        'kotlin': ['.kt', '.kts'],
        'scala': ['.scala'],
        'shell': ['.sh', '.bash', '.zsh', '.fish'],
        'web': ['.html', '.htm', '.css', '.scss', '.sass', '.less'],
        'config': ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'],
        'doc': ['.md', '.rst', '.txt', '.adoc'],
        'data': ['.csv', '.tsv', '.xml', '.sql'],
    }
    
    def __init__(self, root_path: Path = None):
        """Initialize the project analyzer.
        
        Args:
            root_path: Root directory to analyze (defaults to current directory)
        """
        self.root_path = Path(root_path or os.getcwd()).resolve()
        self.project_info: Optional[ProjectInfo] = None
        self._file_cache: Dict[str, List[Path]] = {}
        self._ripgrep_available = self._check_ripgrep()
    
    def _check_ripgrep(self) -> bool:
        """Check if ripgrep (rg) is available."""
        try:
            subprocess.run(['rg', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def analyze_project(self) -> ProjectInfo:
        """Analyze the project structure and detect type."""
        if self.project_info:
            return self.project_info
        
        # Detect project type
        project_type = self._detect_project_type()
        framework = self._detect_framework(project_type)
        
        # Find key directories
        main_dirs = self._find_main_directories(project_type)
        test_dirs = self._find_test_directories(project_type)
        
        # Find build and config files
        build_files = self._find_build_files(project_type)
        config_files = self._find_config_files()
        
        self.project_info = ProjectInfo(
            root_path=self.root_path,
            project_type=project_type,
            framework=framework,
            build_files=build_files,
            main_directories=main_dirs,
            test_directories=test_dirs,
            config_files=config_files
        )
        
        return self.project_info
    
    def _detect_project_type(self) -> str:
        """Detect the primary project type."""
        scores = defaultdict(int)
        
        # Check for project markers
        for lang, markers in self.PROJECT_MARKERS.items():
            for marker_file in markers.get('files', []):
                if (self.root_path / marker_file).exists():
                    scores[lang] += 10
            
            for marker_dir in markers.get('dirs', []):
                if (self.root_path / marker_dir).is_dir():
                    scores[lang] += 5
        
        # Count files by extension
        for lang, extensions in self.CODE_EXTENSIONS.items():
            count = sum(len(list(self.root_path.rglob(f'*{ext}'))) for ext in extensions)
            if count > 0:
                scores[lang] += min(count, 20)  # Cap contribution
        
        # Return the highest scoring language, default to 'unknown'
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return 'unknown'
    
    def _detect_framework(self, project_type: str) -> Optional[str]:
        """Detect the framework being used."""
        if project_type not in self.PROJECT_MARKERS:
            return None
        
        frameworks = self.PROJECT_MARKERS[project_type].get('frameworks', {})
        for framework, markers in frameworks.items():
            for marker in markers:
                if (self.root_path / marker).exists():
                    return framework
        
        return None
    
    def _find_main_directories(self, project_type: str) -> List[Path]:
        """Find main source code directories."""
        common_dirs = ['src', 'lib', 'app', 'source', 'sources']
        lang_specific = {
            'python': ['src', 'lib', project_type],
            'javascript': ['src', 'lib', 'app', 'client', 'server'],
            'java': ['src/main/java', 'src/main/kotlin', 'src'],
            'go': ['cmd', 'pkg', 'internal'],
        }
        
        dirs_to_check = common_dirs + lang_specific.get(project_type, [])
        found_dirs = []
        
        for dir_name in dirs_to_check:
            dir_path = self.root_path / dir_name
            if dir_path.is_dir() and not self._should_ignore(dir_path):
                found_dirs.append(dir_path)
        
        # If no standard directories found, look for directories with code files
        if not found_dirs and project_type in self.CODE_EXTENSIONS:
            extensions = self.CODE_EXTENSIONS[project_type]
            for ext in extensions:
                for file_path in self.root_path.rglob(f'*{ext}'):
                    if not self._should_ignore(file_path):
                        parent = file_path.parent
                        if parent != self.root_path and parent not in found_dirs:
                            found_dirs.append(parent)
        
        return sorted(set(found_dirs))[:5]  # Limit to top 5 directories
    
    def _find_test_directories(self, project_type: str) -> List[Path]:
        """Find test directories."""
        test_patterns = ['test', 'tests', 'spec', 'specs', '__tests__', 'test_*', '*_test']
        lang_specific = {
            'python': ['tests', 'test', 'pytest'],
            'javascript': ['test', 'tests', '__tests__', 'spec'],
            'java': ['src/test/java', 'src/test/kotlin', 'test'],
        }
        
        dirs_to_check = test_patterns + lang_specific.get(project_type, [])
        found_dirs = []
        
        for pattern in dirs_to_check:
            for dir_path in self.root_path.rglob(pattern):
                if dir_path.is_dir() and not self._should_ignore(dir_path):
                    found_dirs.append(dir_path)
        
        return sorted(set(found_dirs))[:3]  # Limit to top 3 test directories
    
    def _find_build_files(self, project_type: str) -> List[Path]:
        """Find build configuration files."""
        build_files = []
        if project_type in self.PROJECT_MARKERS:
            for file_name in self.PROJECT_MARKERS[project_type].get('files', []):
                file_path = self.root_path / file_name
                if file_path.exists():
                    build_files.append(file_path)
        
        # Also look for common build files
        common_build_files = [
            'Makefile', 'makefile', 'CMakeLists.txt', 'setup.cfg',
            '.travis.yml', '.github/workflows/*.yml', 'Dockerfile',
            'docker-compose.yml', 'tox.ini', '.gitlab-ci.yml'
        ]
        
        for pattern in common_build_files:
            for file_path in self.root_path.glob(pattern):
                if file_path.is_file() and file_path not in build_files:
                    build_files.append(file_path)
        
        return build_files
    
    def _find_config_files(self) -> List[Path]:
        """Find configuration files."""
        config_patterns = [
            '*.config.js', '*.config.ts', '*.conf', '*.ini',
            'config/*', 'configs/*', 'configuration/*',
            '.env*', 'settings.py', 'config.py', 'configuration.py'
        ]
        
        config_files = []
        for pattern in config_patterns:
            for file_path in self.root_path.rglob(pattern):
                if file_path.is_file() and not self._should_ignore(file_path):
                    config_files.append(file_path)
        
        return config_files[:10]  # Limit to 10 config files
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        path_str = str(path)
        for pattern in self.IGNORE_PATTERNS:
            if fnmatch.fnmatch(path_str, f'*{pattern}*') or pattern in path_str:
                return True
        return False
    
    def find_files_by_content(self, query: str, file_types: List[str] = None, 
                            max_results: int = 20) -> List[Tuple[Path, List[str]]]:
        """Find files containing specific content using grep/ripgrep.
        
        Args:
            query: Search query (can be regex)
            file_types: List of file types to search (e.g., ['python', 'javascript'])
            max_results: Maximum number of results to return
            
        Returns:
            List of (file_path, matching_lines) tuples
        """
        if file_types is None:
            # Use project type if not specified
            if not self.project_info:
                self.analyze_project()
            file_types = [self.project_info.project_type]
        
        # Get file extensions to search
        extensions = []
        for ft in file_types:
            extensions.extend(self.CODE_EXTENSIONS.get(ft, []))
        
        if self._ripgrep_available:
            return self._ripgrep_search(query, extensions, max_results)
        else:
            return self._python_grep_search(query, extensions, max_results)
    
    def _ripgrep_search(self, query: str, extensions: List[str], 
                       max_results: int) -> List[Tuple[Path, List[str]]]:
        """Search using ripgrep for better performance."""
        cmd = ['rg', '--max-count', '5', '--line-number', '--no-heading']
        
        # Add file type filters
        for ext in extensions:
            cmd.extend(['--glob', f'*{ext}'])
        
        # Add ignore patterns
        for pattern in self.IGNORE_PATTERNS:
            cmd.extend(['--glob', f'!{pattern}'])
        
        cmd.append(query)
        cmd.append(str(self.root_path))
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode not in [0, 1]:  # 0=found, 1=not found
                return []
            
            # Parse results
            files_matches = defaultdict(list)
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = Path(parts[0])
                    line_num = parts[1]
                    content = parts[2]
                    files_matches[file_path].append(f"{line_num}: {content}")
            
            # Convert to list and limit results
            results = [(path, matches) for path, matches in files_matches.items()]
            return results[:max_results]
            
        except Exception as e:
            logger.warning(f"Ripgrep search failed: {e}")
            return []
    
    def _python_grep_search(self, query: str, extensions: List[str], 
                           max_results: int) -> List[Tuple[Path, List[str]]]:
        """Fallback Python-based search."""
        import re
        
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            # If not valid regex, escape it
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        
        results = []
        files_checked = 0
        
        # Search in each directory
        search_dirs = [self.root_path]
        if self.project_info:
            search_dirs.extend(self.project_info.main_directories)
        
        for search_dir in search_dirs:
            for ext in extensions:
                for file_path in search_dir.rglob(f'*{ext}'):
                    if self._should_ignore(file_path) or not file_path.is_file():
                        continue
                    
                    files_checked += 1
                    if files_checked > 1000:  # Limit files checked
                        break
                    
                    try:
                        matches = []
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for i, line in enumerate(f, 1):
                                if pattern.search(line):
                                    matches.append(f"{i}: {line.strip()}")
                                    if len(matches) >= 5:  # Limit matches per file
                                        break
                        
                        if matches:
                            results.append((file_path, matches))
                            if len(results) >= max_results:
                                return results
                    
                    except Exception:
                        continue
        
        return results
    
    def find_files_by_name(self, name_pattern: str, 
                          max_results: int = 20) -> List[Path]:
        """Find files by name pattern.
        
        Args:
            name_pattern: File name pattern (can use wildcards)
            max_results: Maximum number of results
            
        Returns:
            List of matching file paths
        """
        results = []
        
        # Convert simple patterns to glob patterns
        if not any(c in name_pattern for c in ['*', '?', '[', ']']):
            # Exact name search - also search for partial matches
            patterns = [f'*{name_pattern}*', f'{name_pattern}*', f'*{name_pattern}']
        else:
            patterns = [name_pattern]
        
        for pattern in patterns:
            for file_path in self.root_path.rglob(pattern):
                if not self._should_ignore(file_path) and file_path.is_file():
                    results.append(file_path)
                    if len(results) >= max_results:
                        return results
        
        return results
    
    def find_related_files(self, file_path: Path) -> Dict[str, List[Path]]:
        """Find files related to the given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary of related files by category
        """
        related = {
            'imports': [],
            'tests': [],
            'configs': [],
            'similar': []
        }
        
        # Find imports (delegated to smart_context logic)
        # This is a simplified version - the actual implementation would parse the file
        base_name = file_path.stem
        
        # Find test files
        test_patterns = [
            f'test_{base_name}', f'{base_name}_test',
            f'test*{base_name}*', f'*{base_name}*test*'
        ]
        
        for pattern in test_patterns:
            for test_file in self.root_path.rglob(f'{pattern}.*'):
                if test_file != file_path and not self._should_ignore(test_file):
                    related['tests'].append(test_file)
        
        # Find similar files (same extension in nearby directories)
        parent = file_path.parent
        ext = file_path.suffix
        
        for similar in parent.rglob(f'*{ext}'):
            if similar != file_path and not self._should_ignore(similar):
                related['similar'].append(similar)
                if len(related['similar']) >= 5:
                    break
        
        return related
    
    def suggest_files_for_query(self, query: str, 
                               max_suggestions: int = 10) -> List[Path]:
        """Suggest files based on a natural language query.
        
        Args:
            query: Natural language query
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of suggested file paths
        """
        suggestions = []
        
        # Extract potential keywords from query
        keywords = self._extract_keywords(query)
        
        # Search strategies based on query type
        if any(word in query.lower() for word in ['test', 'tests', 'testing']):
            # Focus on test files
            if self.project_info:
                for test_dir in self.project_info.test_directories:
                    for keyword in keywords:
                        suggestions.extend(self.find_files_by_name(
                            f'*{keyword}*', max_results=5
                        ))
        
        elif any(word in query.lower() for word in ['config', 'configuration', 'settings']):
            # Focus on config files
            if self.project_info:
                suggestions.extend(self.project_info.config_files)
        
        elif any(word in query.lower() for word in ['main', 'entry', 'start', 'app']):
            # Look for entry points
            entry_patterns = ['main.*', 'app.*', 'index.*', '__main__.*', 'start.*']
            for pattern in entry_patterns:
                suggestions.extend(self.find_files_by_name(pattern, max_results=3))
        
        # General keyword search
        for keyword in keywords[:3]:  # Limit to top 3 keywords
            # Search by name
            suggestions.extend(self.find_files_by_name(f'*{keyword}*', max_results=5))
            
            # Search by content
            content_results = self.find_files_by_content(keyword, max_results=5)
            suggestions.extend([path for path, _ in content_results])
        
        # Remove duplicates and limit
        seen = set()
        unique_suggestions = []
        for path in suggestions:
            if path not in seen:
                seen.add(path)
                unique_suggestions.append(path)
                if len(unique_suggestions) >= max_suggestions:
                    break
        
        return unique_suggestions
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from a query."""
        # Remove common words
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'as', 'are', 'was',
            'were', 'in', 'to', 'for', 'of', 'with', 'from', 'about', 'where',
            'what', 'when', 'how', 'why', 'can', 'could', 'should', 'would',
            'find', 'show', 'get', 'look', 'search', 'need', 'want', 'help'
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter and prioritize
        keywords = []
        for word in words:
            if word not in stop_words and len(word) > 2:
                keywords.append(word)
        
        # Also look for camelCase or snake_case identifiers
        identifiers = re.findall(r'\b[a-zA-Z_]\w*\b', query)
        for ident in identifiers:
            if ident not in keywords and ident.lower() not in stop_words:
                keywords.insert(0, ident)  # Prioritize identifiers
        
        return keywords
    
    def get_project_summary(self) -> str:
        """Get a human-readable project summary."""
        if not self.project_info:
            self.analyze_project()
        
        info = self.project_info
        summary = [
            f"Project Type: {info.project_type}",
            f"Root: {info.root_path}",
        ]
        
        if info.framework:
            summary.append(f"Framework: {info.framework}")
        
        if info.main_directories:
            summary.append(f"Source Directories: {', '.join(str(d.relative_to(info.root_path)) for d in info.main_directories[:3])}")
        
        if info.test_directories:
            summary.append(f"Test Directories: {', '.join(str(d.relative_to(info.root_path)) for d in info.test_directories[:3])}")
        
        if info.build_files:
            summary.append(f"Build Files: {', '.join(f.name for f in info.build_files[:3])}")
        
        # Count total files
        total_files = sum(1 for _ in info.root_path.rglob('*') if _.is_file() and not self._should_ignore(_))
        summary.append(f"Total Files: {total_files}")
        
        return '\n'.join(summary)