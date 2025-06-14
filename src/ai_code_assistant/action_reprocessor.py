"""Reprocess LLM responses to extract structured actions."""

from typing import List, Optional, Dict, Any
import logging
from .bedrock_client import BedrockClient, Message
from .structured_action_parser import StructuredActionParser, StructuredAction

logger = logging.getLogger(__name__)


class ActionReprocessor:
    """Reprocesses LLM responses to extract structured actions."""
    
    def __init__(self, bedrock_client: BedrockClient):
        self.bedrock_client = bedrock_client
        self.parser = StructuredActionParser()
    
    def reprocess_for_actions(self, original_response: str) -> Optional[List[StructuredAction]]:
        """Ask the LLM to reprocess its response into structured actions.
        
        Args:
            original_response: The original LLM response
            
        Returns:
            List of structured actions, or None if no actions needed
        """
        # First check if there are likely actions in the response
        if not self.parser.detect_unstructured_actions(original_response):
            return None
        
        # Create a prompt to reprocess the response
        reprocess_prompt = f"""I need to execute the file creations and commands from your previous response.
Please convert your instructions into structured XML format so I can execute them step by step.

Your previous response was:
---
{original_response[:2000]}  # Limit to prevent token overflow
---

Please output ONLY the structured actions in this format, nothing else:

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

Important:
- Include ALL files and commands from your previous response
- Use exact file paths and content
- Order actions logically (create directories before files)
- Each action should be atomic
"""
        
        try:
            # Get structured response
            messages = [Message(role="user", content=reprocess_prompt)]
            
            structured_response = ""
            for chunk in self.bedrock_client.send_message(messages, system_prompt="You are a helpful assistant that converts instructions into structured XML format."):
                structured_response += chunk
            
            # Parse the structured actions
            actions, _ = self.parser.extract_actions(structured_response)
            
            if actions:
                logger.info(f"Successfully reprocessed {len(actions)} actions")
                return actions
            else:
                logger.warning("No actions found in reprocessed response")
                return None
                
        except Exception as e:
            logger.error(f"Failed to reprocess actions: {e}")
            return None
    
    def create_step_by_step_prompt(self, actions: List[StructuredAction], completed: int = 0) -> str:
        """Create a prompt for step-by-step execution.
        
        Args:
            actions: List of all actions
            completed: Number of actions already completed
            
        Returns:
            Prompt for the next action
        """
        if completed >= len(actions):
            return "All actions have been completed!"
        
        next_action = actions[completed]
        total = len(actions)
        
        prompt = f"Step {completed + 1} of {total}:\n\n"
        
        if next_action.action_type == 'command':
            prompt += f"Execute command: {next_action.description}\n"
            prompt += f"Command: `{next_action.content['command']}`"
        
        elif next_action.action_type == 'file':
            prompt += f"Create file: {next_action.description}\n"
            prompt += f"Path: `{next_action.content['path']}`\n"
            prompt += f"Content preview: {next_action.content['content'][:100]}..."
        
        return prompt