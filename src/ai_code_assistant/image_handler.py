"""Image and screenshot handling for multimodal analysis."""

import base64
import logging
from pathlib import Path
from typing import Optional, List, Dict, Union
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ImageHandler:
    """Handles image processing for multimodal AI analysis."""
    
    # Supported image formats
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    
    # Maximum dimensions (to avoid sending huge images)
    MAX_WIDTH = 2048
    MAX_HEIGHT = 2048
    
    def __init__(self):
        """Initialize the image handler."""
        self.logger = logging.getLogger(__name__)
    
    def is_image_file(self, file_path: Path) -> bool:
        """Check if a file is a supported image.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if the file is a supported image
        """
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def process_image(self, file_path: Path) -> Optional[Dict[str, Union[str, Dict]]]:
        """Process an image file for AI analysis.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Processed image data ready for Bedrock API or None if failed
        """
        try:
            if not file_path.exists():
                self.logger.error(f"Image file not found: {file_path}")
                return None
            
            if not self.is_image_file(file_path):
                self.logger.error(f"Unsupported image format: {file_path}")
                return None
            
            # Open and potentially resize image
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (for formats like PNG with transparency)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # Resize if too large
                if img.width > self.MAX_WIDTH or img.height > self.MAX_HEIGHT:
                    img.thumbnail((self.MAX_WIDTH, self.MAX_HEIGHT), Image.Resampling.LANCZOS)
                    self.logger.info(f"Resized image from {file_path.name} to fit within {self.MAX_WIDTH}x{self.MAX_HEIGHT}")
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # Return in Bedrock-compatible format
                return {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error processing image {file_path}: {e}")
            return None
    
    def create_multimodal_content(self, text: str, image_paths: List[Path]) -> List[Dict]:
        """Create multimodal content combining text and images.
        
        Args:
            text: Text content
            image_paths: List of image file paths
            
        Returns:
            List of content blocks for Bedrock API
        """
        content_blocks = []
        
        # Add text block first
        if text:
            content_blocks.append({
                "type": "text",
                "text": text
            })
        
        # Process and add images
        for image_path in image_paths:
            image_data = self.process_image(image_path)
            if image_data:
                content_blocks.append(image_data)
                self.logger.info(f"Added image: {image_path.name}")
            else:
                self.logger.warning(f"Failed to process image: {image_path}")
        
        return content_blocks
    
    def extract_images_from_paths(self, paths: List[Path]) -> tuple[List[Path], List[Path]]:
        """Separate image files from other files.
        
        Args:
            paths: List of file paths
            
        Returns:
            Tuple of (non_image_paths, image_paths)
        """
        image_paths = []
        non_image_paths = []
        
        for path in paths:
            if self.is_image_file(path):
                image_paths.append(path)
            else:
                non_image_paths.append(path)
        
        return non_image_paths, image_paths
    
    def describe_image_for_context(self, image_path: Path) -> str:
        """Create a text description for an image in context.
        
        Args:
            image_path: Path to the image
            
        Returns:
            Text description
        """
        try:
            with Image.open(image_path) as img:
                return (f"[Image: {image_path.name}]\n"
                       f"Format: {img.format}\n"
                       f"Dimensions: {img.width}x{img.height}\n"
                       f"Mode: {img.mode}")
        except Exception as e:
            return f"[Image: {image_path.name}] (Error reading: {e})"


class ScreenshotCapture:
    """Handles screenshot capture functionality."""
    
    def __init__(self):
        """Initialize screenshot capture."""
        self.logger = logging.getLogger(__name__)
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if screenshot dependencies are available."""
        self.has_pyautogui = False
        
        # First do a lightweight check for tkinter
        import subprocess
        import sys
        
        # Check if tkinter is available without importing it
        result = subprocess.run(
            [sys.executable, "-c", "import tkinter"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self.logger.debug("tkinter not installed - screenshot capture unavailable")
            return
        
        try:
            # Suppress warnings and output during import
            import warnings
            import io
            
            old_stderr = sys.stderr
            old_stdout = sys.stdout
            sys.stderr = io.StringIO()
            sys.stdout = io.StringIO()
            
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore")
                    import pyautogui
                self.has_pyautogui = True
            finally:
                sys.stderr = old_stderr
                sys.stdout = old_stdout
                
        except (ImportError, SystemExit) as e:
            self.logger.debug(f"pyautogui unavailable: {type(e).__name__}")
        except Exception as e:
            self.logger.debug(f"Screenshot capture unavailable: {e}")
    
    def capture_screenshot(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Capture a screenshot.
        
        Args:
            output_path: Where to save the screenshot (optional)
            
        Returns:
            Path to the saved screenshot or None if failed
        """
        if not self.has_pyautogui:
            self.logger.error("Screenshot capture requires pyautogui: pip install pyautogui")
            return None
        
        try:
            import pyautogui
            from datetime import datetime
            
            # Generate filename if not provided
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path.cwd() / f"screenshot_{timestamp}.png"
            
            # Capture screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(output_path)
            
            self.logger.info(f"Screenshot saved to: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}")
            return None
    
    def capture_region(self, x: int, y: int, width: int, height: int, 
                      output_path: Optional[Path] = None) -> Optional[Path]:
        """Capture a specific region of the screen.
        
        Args:
            x: X coordinate of the region
            y: Y coordinate of the region
            width: Width of the region
            height: Height of the region
            output_path: Where to save the screenshot
            
        Returns:
            Path to the saved screenshot or None if failed
        """
        if not self.has_pyautogui:
            self.logger.error("Screenshot capture requires pyautogui")
            return None
        
        try:
            import pyautogui
            from datetime import datetime
            
            # Generate filename if not provided
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path.cwd() / f"screenshot_region_{timestamp}.png"
            
            # Capture region
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            screenshot.save(output_path)
            
            self.logger.info(f"Region screenshot saved to: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to capture region: {e}")
            return None