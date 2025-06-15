"""Enhanced smart context with automatic file discovery based on queries."""

import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
import re

from .project_analyzer import ProjectAnalyzer, ProjectInfo
from .file_context import FileContextManager
from .smart_context import SmartContextManager

logger = logging.getLogger(__name__)


@dataclass
class QueryContext:
    """Context derived from analyzing a user query."""
    intent: str  # 'debug', 'review', 'implement', 'test', 'refactor', etc.
    targets: List[str]  # Specific functions, classes, or concepts mentioned
    scope: str  # 'specific', 'module', 'project'
    file_hints: List[str]  # File names or paths mentioned
    keywords: List[str]  # Important keywords extracted


class SmartContextV2:
    """Enhanced smart context that automatically discovers relevant files."""
    
    # Intent patterns
    INTENT_PATTERNS = {
        'debug': [
            r'\b(debug|fix|error|bug|issue|problem|crash|exception)\b',
            r'\b(not working|broken|fails?|failing)\b',
            r'\b(traceback|stack trace|error message)\b'
        ],
        'review': [
            r'\b(review|check|analyze|audit|inspect|look at)\b',
            r'\b(code review|feedback|suggestions?|improvements?)\b'
        ],
        'implement': [
            r'\b(implement|add|create|build|write|develop)\b',
            r'\b(new feature|functionality|method|function|class)\b'
        ],
        'test': [
            r'\b(test|tests?|testing|unit test|integration test)\b',
            r'\b(coverage|assert|mock|pytest|jest)\b'
        ],
        'refactor': [
            r'\b(refactor|restructure|reorganize|clean up|optimize)\b',
            r'\b(performance|efficiency|readability|maintainability)\b'
        ],
        'explain': [
            r'\b(explain|understand|how does|what is|why)\b',
            r'\b(documentation|clarify|describe)\b'
        ]
    }
    
    def __init__(self, project_root: Path = None):
        """Initialize enhanced smart context.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_analyzer = ProjectAnalyzer(project_root)
        self.file_manager = FileContextManager()
        self.smart_context = SmartContextManager()
        self.project_info: Optional[ProjectInfo] = None
        
    def analyze_query(self, query: str) -> QueryContext:
        """Analyze a user query to understand intent and extract hints.
        
        Args:
            query: User's natural language query
            
        Returns:
            QueryContext with analyzed information
        """
        query_lower = query.lower()
        
        # Detect intent
        intent = 'general'
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    intent = intent_type
                    break
            if intent != 'general':
                break
        
        # Extract file hints (files mentioned in the query)
        file_hints = []
        # Look for file paths
        path_patterns = [
            r'(?:^|\s)([./][\w/.-]+\.\w+)',  # Paths starting with ./ or /
            r'(?:^|\s)([\w/]+\.\w+)',  # Simple file names with extensions
            r'`([^`]+\.\w+)`',  # Files in backticks
            r'"([^"]+\.\w+)"',  # Files in quotes
            r'\'([^\']+\.\w+)\'',  # Files in single quotes
        ]
        
        for pattern in path_patterns:
            matches = re.findall(pattern, query)
            file_hints.extend(matches)
        
        # Extract potential function/class names
        # Look for CamelCase, snake_case, or identified code elements
        code_patterns = [
            r'\b([A-Z][a-zA-Z0-9]+)\b',  # CamelCase (classes)
            r'\b([a-z_][a-z0-9_]{2,})\b',  # snake_case (functions/variables)
            r'`([^`]+)`',  # Anything in backticks
            r'def\s+(\w+)',  # Function definitions
            r'class\s+(\w+)',  # Class definitions
        ]
        
        targets = []
        for pattern in code_patterns:
            matches = re.findall(pattern, query)
            targets.extend(matches)
        
        # Remove common words from targets
        common_words = {
            'the', 'this', 'that', 'with', 'from', 'into', 'about',
            'what', 'where', 'when', 'how', 'why', 'can', 'should'
        }
        targets = [t for t in targets if t.lower() not in common_words]
        
        # Extract keywords
        keywords = self.project_analyzer._extract_keywords(query)
        
        # Determine scope
        scope = 'specific'
        if any(word in query_lower for word in ['project', 'codebase', 'entire', 'all']):
            scope = 'project'
        elif any(word in query_lower for word in ['module', 'package', 'directory']):
            scope = 'module'
        
        return QueryContext(
            intent=intent,
            targets=targets[:10],  # Limit targets
            scope=scope,
            file_hints=file_hints[:10],  # Limit hints
            keywords=keywords[:10]  # Limit keywords
        )
    
    def get_relevant_files(self, query: str, max_files: int = 20) -> List[Path]:
        """Get relevant files based on the user's query.
        
        Args:
            query: User's natural language query
            max_files: Maximum number of files to return
            
        Returns:
            List of relevant file paths
        """
        # Analyze the query
        context = self.analyze_query(query)
        
        # Get project info
        if not self.project_info:
            self.project_info = self.project_analyzer.analyze_project()
        
        relevant_files = []
        scores: Dict[Path, float] = {}
        
        # 1. Check explicit file hints first
        for hint in context.file_hints:
            hint_path = Path(hint)
            if hint_path.is_absolute():
                if hint_path.exists():
                    relevant_files.append(hint_path)
            else:
                # Search for the file
                found = self.project_analyzer.find_files_by_name(hint_path.name)
                relevant_files.extend(found[:2])  # Take top 2 matches
        
        # 2. Search by targets (function/class names)
        for target in context.targets:
            # Search in code
            results = self.project_analyzer.find_files_by_content(
                f'\\b{re.escape(target)}\\b',
                max_results=5
            )
            for file_path, matches in results:
                scores[file_path] = scores.get(file_path, 0) + len(matches) * 2
        
        # 3. Search by keywords based on intent
        if context.intent == 'test':
            # Focus on test files
            for keyword in context.keywords[:3]:
                test_files = []
                for test_dir in self.project_info.test_directories:
                    test_files.extend(
                        self.project_analyzer.find_files_by_name(
                            f'*{keyword}*',
                            max_results=3
                        )
                    )
                for f in test_files:
                    scores[f] = scores.get(f, 0) + 1.5
        
        elif context.intent == 'debug':
            # Look for files with errors or recent changes
            for keyword in context.keywords[:3]:
                # Search for error-related content
                error_patterns = [keyword, f'raise.*{keyword}', f'except.*{keyword}']
                for pattern in error_patterns:
                    results = self.project_analyzer.find_files_by_content(
                        pattern,
                        max_results=5
                    )
                    for file_path, matches in results:
                        scores[file_path] = scores.get(file_path, 0) + len(matches) * 1.5
        
        else:
            # General keyword search
            for keyword in context.keywords[:5]:
                # By name
                name_results = self.project_analyzer.find_files_by_name(
                    f'*{keyword}*',
                    max_results=3
                )
                for f in name_results:
                    scores[f] = scores.get(f, 0) + 1
                
                # By content
                content_results = self.project_analyzer.find_files_by_content(
                    keyword,
                    max_results=5
                )
                for file_path, matches in content_results:
                    scores[file_path] = scores.get(file_path, 0) + len(matches) * 0.5
        
        # 4. Add high-value files based on project structure
        if context.scope in ['module', 'project']:
            # Add main entry points
            entry_files = self.project_analyzer.find_files_by_name('main.*')
            entry_files.extend(self.project_analyzer.find_files_by_name('__init__.py'))
            entry_files.extend(self.project_analyzer.find_files_by_name('index.*'))
            
            for f in entry_files[:3]:
                scores[f] = scores.get(f, 0) + 0.5
            
            # Add important config files
            if self.project_info.config_files:
                for f in self.project_info.config_files[:2]:
                    scores[f] = scores.get(f, 0) + 0.3
        
        # 5. Sort by score and combine with explicit files
        scored_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Combine explicit files with scored files
        final_files = []
        seen = set()
        
        # Add explicit files first
        for f in relevant_files:
            if f not in seen:
                final_files.append(f)
                seen.add(f)
        
        # Add scored files
        for f, score in scored_files:
            if f not in seen:
                final_files.append(f)
                seen.add(f)
            if len(final_files) >= max_files:
                break
        
        # 6. If we have main files, use smart context to add their dependencies
        if final_files and len(final_files) < max_files:
            # Use smart context to find related files for top results
            for main_file in final_files[:3]:
                related = self.smart_context.find_related_files(
                    main_file,
                    max_depth=1
                )
                
                for rel_file in related:
                    if rel_file not in seen:
                        final_files.append(rel_file)
                        seen.add(rel_file)
                    if len(final_files) >= max_files:
                        break
        
        return final_files[:max_files]
    
    def create_context_for_query(self, query: str, 
                                additional_files: List[Path] = None,
                                max_files: int = 15) -> str:
        """Create file context automatically based on a query.
        
        Args:
            query: User's natural language query
            additional_files: Additional files to include
            max_files: Maximum number of files to include
            
        Returns:
            Formatted context string
        """
        # Get relevant files
        relevant_files = self.get_relevant_files(query, max_files)
        
        # Add any additional files
        if additional_files:
            for f in additional_files:
                if f not in relevant_files:
                    relevant_files.append(f)
        
        # Create context
        if not relevant_files:
            return ""
        
        # Sort files intelligently using get_smart_context
        sorted_files = self.smart_context.get_smart_context(relevant_files)
        
        # Create context using file manager
        context_parts = []
        
        # Add project summary if scope is broad
        query_context = self.analyze_query(query)
        if query_context.scope in ['module', 'project']:
            context_parts.append(
                "=== Project Summary ===\n" +
                self.project_analyzer.get_project_summary() +
                "\n=== End Project Summary ===\n"
            )
        
        # Separate text files from image files
        from .image_handler import ImageHandler
        image_handler = ImageHandler()
        
        text_files = []
        image_files = []
        
        for file_path in sorted_files:
            if image_handler.is_image_file(file_path):
                image_files.append(file_path)
            else:
                text_files.append(file_path)
        
        # Add text file contents
        if text_files:
            file_context = self.file_manager.create_context_from_files(text_files)
        else:
            file_context = ""
        context_parts.append(file_context)
        
        return '\n'.join(context_parts)
    
    def explain_file_selection(self, query: str, files: List[Path]) -> str:
        """Explain why certain files were selected for a query.
        
        Args:
            query: The user's query
            files: The selected files
            
        Returns:
            Human-readable explanation
        """
        context = self.analyze_query(query)
        
        explanation = [
            f"Query Analysis:",
            f"  Intent: {context.intent}",
            f"  Scope: {context.scope}",
        ]
        
        if context.targets:
            explanation.append(f"  Code elements: {', '.join(context.targets[:5])}")
        
        if context.file_hints:
            explanation.append(f"  Files mentioned: {', '.join(context.file_hints[:5])}")
        
        explanation.append(f"\nSelected {len(files)} relevant files:")
        
        # Group files by why they were selected
        for i, file in enumerate(files[:10], 1):
            rel_path = file.relative_to(self.project_analyzer.root_path)
            explanation.append(f"  {i}. {rel_path}")
            
            # Add reason (simplified - in reality would track this during selection)
            if file.name in [Path(h).name for h in context.file_hints]:
                explanation.append(f"     → Explicitly mentioned in query")
            elif 'test' in str(file) and context.intent == 'test':
                explanation.append(f"     → Test file relevant to testing intent")
            elif file in (self.project_info.config_files if self.project_info else []):
                explanation.append(f"     → Configuration file")
            else:
                explanation.append(f"     → Contains relevant code/keywords")
        
        if len(files) > 10:
            explanation.append(f"  ... and {len(files) - 10} more files")
        
        return '\n'.join(explanation)