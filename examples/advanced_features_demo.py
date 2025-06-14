#!/usr/bin/env python3
"""Example demonstrating advanced features: smart context, web search, images, and autocomplete."""

from pathlib import Path
from ai_code_assistant.smart_context import SmartContextManager
from ai_code_assistant.web_search import WebSearcher
from ai_code_assistant.image_handler import ImageHandler
from ai_code_assistant.file_context import FileContextManager

# Example 1: Smart File Context
print("=== Smart File Context Demo ===")

# Create a test Python file with imports
test_file = Path("example_module.py")
test_file.write_text("""
import json
import os
from pathlib import Path
from .utils import helper_function
from .config import Settings

class ExampleClass:
    def __init__(self):
        self.settings = Settings()
    
    def process_data(self, data):
        return helper_function(data)
""")

# Create related files
utils_file = Path("utils.py")
utils_file.write_text("""
def helper_function(data):
    return data.upper()
""")

config_file = Path("config.py")
config_file.write_text("""
class Settings:
    DEBUG = True
    API_KEY = "example"
""")

test_test_file = Path("test_example_module.py")
test_test_file.write_text("""
import pytest
from example_module import ExampleClass

def test_example():
    obj = ExampleClass()
    assert obj.process_data("hello") == "HELLO"
""")

try:
    # Use smart context to find related files
    smart_context = SmartContextManager()
    related_files = smart_context.find_related_files(test_file)
    
    print(f"Original file: {test_file}")
    print(f"Found {len(related_files)} related files:")
    for f in related_files:
        print(f"  - {f.name}")
    
    # Create context with all related files
    file_manager = FileContextManager()
    context = file_manager.create_context_from_files(list(related_files))
    print(f"\nContext size: {len(context)} characters")
    print("Context includes imports, test files, and related modules automatically!")
    
finally:
    # Cleanup
    for f in [test_file, utils_file, config_file, test_test_file]:
        f.unlink(missing_ok=True)

# Example 2: Web Search
print("\n=== Web Search Demo ===")

searcher = WebSearcher(max_results=3)

# Search for programming information
query = "python asyncio vs threading performance"
print(f"Searching for: {query}")

results = searcher.search(query)
print(f"\nFound {len(results)} results:")

for i, result in enumerate(results, 1):
    print(f"\n{i}. {result['title']}")
    print(f"   URL: {result['url']}")
    if result['snippet']:
        print(f"   Snippet: {result['snippet'][:100]}...")

# Example 3: Image Handling
print("\n=== Image Handling Demo ===")

# Create a simple test image
try:
    from PIL import Image
    import io
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    img_path = Path("test_image.png")
    img.save(img_path)
    
    # Use image handler
    handler = ImageHandler()
    
    # Check if file is an image
    print(f"Is {img_path} an image? {handler.is_image_file(img_path)}")
    
    # Process for AI
    processed = handler.process_image(img_path)
    if processed:
        print(f"Image processed successfully!")
        print(f"Format: {processed['source']['media_type']}")
        print(f"Data size: {len(processed['source']['data'])} characters (base64)")
    
    # Create multimodal content
    content = handler.create_multimodal_content(
        "What color is this image?",
        [img_path]
    )
    print(f"\nMultimodal content blocks: {len(content)}")
    print(f"Block types: {[block['type'] for block in content]}")
    
    # Cleanup
    img_path.unlink(missing_ok=True)
    
except ImportError:
    print("Pillow not installed - skipping image demo")

# Example 4: Path Autocomplete
print("\n=== Path Autocomplete Demo ===")
print("In interactive mode, you now have:")
print("1. Command autocomplete - type '/' and press TAB")
print("2. File path autocomplete - type '/files ' and press TAB")
print("3. Smart filtering - ignores .git, __pycache__, etc.")
print("\nExample:")
print(">>> /fi<TAB>              # Completes to /files")
print(">>> /files src/<TAB>      # Shows files in src/")
print(">>> /files src/main<TAB>  # Completes to src/main.py")

print("\n✨ All advanced features are ready to use!")
print("Try them in interactive mode with 'sc -i'")