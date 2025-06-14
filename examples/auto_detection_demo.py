#!/usr/bin/env python3
"""Example demonstrating automatic URL and image detection features."""

from pathlib import Path
from ai_code_assistant.auto_detection import AutoDetector

# Create test files
test_image = Path("test_diagram.png")
test_doc = Path("README.md")

# Create a simple test image
try:
    from PIL import Image
    img = Image.new('RGB', (200, 100), color='blue')
    img.save(test_image)
    print(f"Created test image: {test_image}")
except ImportError:
    print("Pillow not installed - skipping image creation")

# Create a test document
test_doc.write_text("""# Test Document
This is a test markdown file for auto-detection demo.
""")
print(f"Created test document: {test_doc}")

# Example usage
print("\n=== Auto-Detection Demo ===\n")

detector = AutoDetector(
    auto_fetch_urls=True,
    auto_detect_images=True,
    auto_detect_files=True
)

# Test various inputs
test_inputs = [
    # URLs
    "Check out the documentation at https://docs.python.org/3/library/asyncio.html",
    "The API endpoint is https://api.example.com/v1/users and returns JSON",
    
    # Image paths
    f"Look at this diagram: {test_image}",
    "The screenshot shows an error in /tmp/error_screenshot.png",
    "I've attached 'design_mockup.jpg' for reference",
    
    # Mixed content
    f"Based on {test_doc} and the image {test_image}, can you help me understand this?",
    
    # Quoted paths
    f'The file "{test_doc}" contains the documentation',
    f"Check `{test_image}` for the visual representation",
]

for i, text in enumerate(test_inputs, 1):
    print(f"\nTest {i}: {text[:60]}...")
    
    # Extract all detections
    detections = detector.extract_all(text)
    
    # Show results
    if detections['urls']:
        print(f"  URLs found: {detections['urls']}")
    if detections['image_paths']:
        print(f"  Images found: {[str(p) for p in detections['image_paths']]}")
    if detections['file_paths']:
        print(f"  Files found: {[str(p) for p in detections['file_paths']]}")
    
    # Show summary
    summary = detector.format_detection_summary(detections)
    if summary:
        print(f"  Summary: {summary}")
    else:
        print("  No detections")

# Demonstrate disabling features
print("\n=== With Auto-Detection Disabled ===")
detector.auto_fetch_urls = False
detector.auto_detect_images = False

text = f"Visit https://example.com and see {test_image}"
detections = detector.extract_all(text)
print(f"Input: {text}")
print(f"Detections: {detector.format_detection_summary(detections) or 'None (all disabled)'}")

# Cleanup
test_image.unlink(missing_ok=True)
test_doc.unlink(missing_ok=True)

print("\n=== How It Works in Interactive Mode ===")
print("""
When you type a message in interactive mode:

1. URLs are automatically detected and fetched:
   >>> Explain the async pattern from https://docs.python.org/3/library/asyncio.html
   [Auto-detected: 1 URL(s)]
   [Fetching https://docs.python.org/3/library/asyncio.html...]

2. Image paths are automatically detected and included:
   >>> What's wrong with this UI? screenshot.png
   [Auto-detected: 1 image(s)]
   [Including 1 image(s) in message]

3. You can control auto-detection with settings:
   >>> /set auto_detect urls      # Toggle URL detection
   >>> /set auto_detect images    # Toggle image detection
   >>> /set auto_detect files     # Toggle file detection
   >>> /set auto_detect all       # Enable all
   >>> /set auto_detect none      # Disable all

4. The content is automatically included in your message context!
""")