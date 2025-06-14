"""Parser for structured action output from LLM."""

import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class StructuredAction:
    """Represents a structured action from the LLM."""
    action_type: str  # 'file' or 'command'
    description: str
    content: Dict[str, Any]  # command/path/content depending on type


class StructuredActionParser:
    """Parses structured actions from LLM responses."""
    
    def __init__(self):
        self.action_pattern = re.compile(r'<actions>(.*?)</actions>', re.DOTALL)
    
    def extract_actions(self, response: str) -> Tuple[List[StructuredAction], str]:
        """Extract structured actions from response.
        
        Args:
            response: The LLM response
            
        Returns:
            Tuple of (actions, remaining_response)
        """
        actions = []
        remaining_response = response
        
        # Find all action blocks
        matches = list(self.action_pattern.finditer(response))
        
        if not matches:
            return [], response
        
        # Process each action block
        for match in matches:
            actions_xml = match.group(1)
            try:
                # Parse the XML
                root = ET.fromstring(f"<actions>{actions_xml}</actions>")
                
                for action_elem in root.findall('action'):
                    action_type = action_elem.get('type')
                    description_elem = action_elem.find('description')
                    description = description_elem.text if description_elem is not None else ""
                    
                    if action_type == 'command':
                        command_elem = action_elem.find('command')
                        if command_elem is not None:
                            actions.append(StructuredAction(
                                action_type='command',
                                description=description,
                                content={'command': command_elem.text}
                            ))
                    
                    elif action_type == 'file':
                        path_elem = action_elem.find('path')
                        content_elem = action_elem.find('content')
                        if path_elem is not None and content_elem is not None:
                            actions.append(StructuredAction(
                                action_type='file',
                                description=description,
                                content={'path': path_elem.text, 'content': content_elem.text.strip()}
                            ))
                
                # Remove this action block from the response
                remaining_response = remaining_response.replace(match.group(0), '[Actions hidden - see action queue below]')
                
            except ET.ParseError as e:
                logger.warning(f"Failed to parse action XML: {e}")
                continue
        
        return actions, remaining_response.strip()
    
    def detect_unstructured_actions(self, response: str) -> bool:
        """Detect if response contains unstructured file/command instructions.
        
        This helps identify when the LLM didn't use structured format.
        """
        indicators = [
            # File creation indicators
            r'create.*file',
            r'creating.*\.json',
            r'create.*\.ts',
            r'create.*\.py',
            r'package\.json.*:',
            r'tsconfig\.json.*:',
            # Command indicators  
            r'```(?:bash|sh|shell)',
            r'run.*command',
            r'execute.*:',
            r'mkdir\s+-p',
            r'npm\s+init',
            r'npm\s+install',
        ]
        
        response_lower = response.lower()
        for indicator in indicators:
            if re.search(indicator, response_lower, re.IGNORECASE):
                return True
        
        return False
    
    def suggest_structured_format(self, response: str) -> Optional[str]:
        """Suggest how to convert unstructured response to structured format.
        
        This can be sent back to the LLM to get structured output.
        """
        if not self.detect_unstructured_actions(response):
            return None
        
        return """I notice you're trying to create files or run commands. 
Please reformat your response using the structured XML format:

<actions>
  <action type="command">
    <description>What this command does</description>
    <command>the bash command</command>
  </action>
  
  <action type="file">
    <description>What this file is for</description>
    <path>relative/path/to/file</path>
    <content><![CDATA[
file content here
]]></content>
  </action>
</actions>

This allows me to execute your instructions step by step with user confirmation."""