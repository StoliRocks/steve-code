#!/usr/bin/env python3
"""Advanced usage examples for Steve Code."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_code_assistant.bedrock_client import BedrockClient, ModelType, Message
from ai_code_assistant.conversation import ConversationHistory
from ai_code_assistant.code_extractor import CodeExtractor
from ai_code_assistant.file_context import FileContextManager


def example_code_review_with_context():
    """Example: Code review with multiple files."""
    print("=== Code Review Example ===\n")
    
    # Create sample project files
    project_dir = Path("sample_project")
    project_dir.mkdir(exist_ok=True)
    
    # Main application file
    (project_dir / "app.py").write_text("""
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect('database.db')
    return conn

@app.route('/users/<user_id>')
def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    user = cursor.fetchone()
    conn.close()
    return jsonify(user)

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        (data['name'], data['email'])
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201
""")
    
    # Database schema file
    (project_dir / "schema.sql").write_text("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
""")
    
    # Initialize file manager
    file_manager = FileContextManager()
    
    # Read all files
    files = [
        project_dir / "app.py",
        project_dir / "schema.sql"
    ]
    
    context = file_manager.create_context_from_files(files)
    
    print("Files included in context:")
    for file in files:
        print(f"  - {file}")
    
    print("\nContext preview:")
    print(context[:500] + "..." if len(context) > 500 else context)
    
    # Example prompt for code review
    prompt = """
Please review this Flask application for:
1. Security vulnerabilities
2. Best practices
3. Performance issues
4. Code quality

Provide specific recommendations for improvements.
"""
    
    print(f"\nReview prompt: {prompt}")
    
    # Clean up
    import shutil
    shutil.rmtree(project_dir)


def example_directory_tree_analysis():
    """Example: Analyze project structure."""
    print("\n=== Directory Tree Analysis ===\n")
    
    # Create sample project structure
    project_dir = Path("sample_web_project")
    
    # Create directories
    (project_dir / "src" / "components").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "utils").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)
    (project_dir / "docs").mkdir(parents=True, exist_ok=True)
    
    # Create files
    (project_dir / "README.md").touch()
    (project_dir / "package.json").touch()
    (project_dir / "src" / "index.js").touch()
    (project_dir / "src" / "components" / "App.js").touch()
    (project_dir / "src" / "components" / "Header.js").touch()
    (project_dir / "src" / "utils" / "api.js").touch()
    (project_dir / "tests" / "App.test.js").touch()
    
    # Get directory tree
    file_manager = FileContextManager()
    tree = file_manager.get_directory_tree(project_dir, max_depth=3)
    
    print("Project structure:")
    print(tree)
    
    # Find specific files
    js_files = file_manager.find_files("*.js", project_dir)
    print(f"\nFound {len(js_files)} JavaScript files:")
    for file in js_files:
        print(f"  - {file.relative_to(project_dir)}")
    
    # Clean up
    import shutil
    shutil.rmtree(project_dir)


def example_conversation_management():
    """Example: Advanced conversation management."""
    print("\n=== Advanced Conversation Management ===\n")
    
    # Create multiple conversations
    conv1 = ConversationHistory()
    conv1.add_message("user", "How do I implement authentication in Django?")
    conv1.add_message("assistant", "To implement authentication in Django...")
    
    conv2 = ConversationHistory()
    conv2.add_message("user", "Explain React hooks")
    conv2.add_message("assistant", "React hooks are functions that...")
    
    # List sessions
    sessions = conv1.list_sessions()
    print(f"Found {len(sessions)} saved sessions")
    
    # Export in different formats
    conv1.export_session(Path("conv_json.json"), format="json")
    conv1.export_session(Path("conv_md.md"), format="markdown")
    
    print("\nExported conversations:")
    print("  - conv_json.json (JSON format)")
    print("  - conv_md.md (Markdown format)")
    
    # Clean up
    Path("conv_json.json").unlink()
    Path("conv_md.md").unlink()


def example_code_generation_workflow():
    """Example: Complete code generation workflow."""
    print("\n=== Code Generation Workflow ===\n")
    
    # Simulate a code generation response
    ai_response = """
I'll create a complete Python package for managing tasks. Here's the implementation:

```python
# filename: task_manager/models.py
from datetime import datetime
from typing import List, Optional
from enum import Enum

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

class Task:
    def __init__(self, title: str, description: str = "", 
                 priority: Priority = Priority.MEDIUM):
        self.id = None
        self.title = title
        self.description = description
        self.priority = priority
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.tags: List[str] = []
    
    def complete(self):
        self.completed_at = datetime.now()
    
    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None
```

```python
# filename: task_manager/manager.py
from typing import List, Optional
from .models import Task, Priority

class TaskManager:
    def __init__(self):
        self._tasks: List[Task] = []
        self._next_id = 1
    
    def add_task(self, task: Task) -> Task:
        task.id = self._next_id
        self._next_id += 1
        self._tasks.append(task)
        return task
    
    def get_task(self, task_id: int) -> Optional[Task]:
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None
    
    def list_tasks(self, completed: Optional[bool] = None) -> List[Task]:
        if completed is None:
            return self._tasks.copy()
        return [t for t in self._tasks if t.is_completed == completed]
```

```python
# filename: task_manager/__init__.py
from .models import Task, Priority
from .manager import TaskManager

__all__ = ['Task', 'Priority', 'TaskManager']
__version__ = '0.1.0'
```
"""
    
    # Extract code blocks
    extractor = CodeExtractor()
    code_blocks = extractor.extract_code_blocks(ai_response)
    
    print(f"Extracted {len(code_blocks)} code blocks")
    
    # Save with proper directory structure
    output_dir = Path("generated_package")
    saved_files = extractor.save_code_blocks(code_blocks, output_dir)
    
    print("\nGenerated package structure:")
    file_manager = FileContextManager()
    tree = file_manager.get_directory_tree(output_dir)
    print(tree)
    
    # Clean up
    import shutil
    shutil.rmtree(output_dir)


def example_multi_file_context():
    """Example: Working with multiple file contexts."""
    print("\n=== Multi-File Context Example ===\n")
    
    # Create a mock project
    project_dir = Path("mock_project")
    project_dir.mkdir(exist_ok=True)
    
    files_content = {
        "config.py": """
DATABASE_URL = "sqlite:///app.db"
DEBUG = True
SECRET_KEY = "development-key"
""",
        "models.py": """
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
""",
        "api.py": """
from flask import Blueprint, jsonify
from models import User

api_bp = Blueprint('api', __name__)

@api_bp.route('/users')
def get_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])
"""
    }
    
    # Create files
    for filename, content in files_content.items():
        (project_dir / filename).write_text(content)
    
    # Read all files and create context
    file_manager = FileContextManager()
    file_paths = [project_dir / name for name in files_content.keys()]
    
    # Read individually
    print("Reading files individually:")
    file_contents = file_manager.read_multiple_files(file_paths)
    
    for path, content in file_contents.items():
        status = "✓" if content else "✗"
        print(f"  {status} {path.name}")
    
    # Create combined context
    context = file_manager.create_context_from_files(file_paths)
    print(f"\nCombined context length: {len(context)} characters")
    
    # Clean up
    import shutil
    shutil.rmtree(project_dir)


if __name__ == "__main__":
    try:
        print("Steve Code - Advanced Examples\n")
        
        # Run examples that don't require AWS credentials
        example_code_review_with_context()
        example_directory_tree_analysis()
        example_conversation_management()
        example_code_generation_workflow()
        example_multi_file_context()
        
        print("\nAdvanced examples completed!")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()