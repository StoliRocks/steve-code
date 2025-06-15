"""Dynamic execution planning using Bedrock AI."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import os

from .bedrock_client import BedrockClient, Message
from rich.console import Console

logger = logging.getLogger(__name__)


class ExecutionPlanner:
    """Create intelligent execution plans using Bedrock without hardcoded assumptions."""
    
    def __init__(self, bedrock_client: BedrockClient, console: Console):
        """Initialize the execution planner.
        
        Args:
            bedrock_client: Bedrock client for AI calls
            console: Rich console for output
        """
        self.bedrock_client = bedrock_client
        self.console = console
        
    def create_plan(self, user_input: str, verbose: bool = False) -> Dict[str, Any]:
        """Create an execution plan for the user's request.
        
        Args:
            user_input: The user's request
            verbose: Whether to show verbose output
            
        Returns:
            Complete execution plan with discovery results
        """
        # Step 1: Get initial plan with discovery commands
        initial_plan = self._get_initial_plan(user_input)
        
        if verbose:
            self.console.print("[dim]Initial interpretation:[/dim]", initial_plan.get('interpretation', 'Unknown'))
        
        # Step 2: Execute discovery commands
        discovery_results = self._execute_discovery(initial_plan.get('discovery_commands', []), verbose)
        
        # Step 3: Create final plan based on discoveries
        final_plan = self._create_final_plan(user_input, initial_plan, discovery_results)
        
        return final_plan
    
    def _get_initial_plan(self, user_input: str) -> Dict[str, Any]:
        """Get initial plan with discovery commands."""
        prompt = f"""You are an expert software developer helping with a code repository.

User Request: "{user_input}"

Current Directory: {os.getcwd()}

You have access to these tools:
- File operations: read, write, search for files
- Command execution: run any shell command
- Git operations: status, diff, commit, etc.
- Web search: search for current information
- Image analysis: analyze visual content of images

Based on the user's request, create an execution plan. Return ONLY valid JSON with:

1. "interpretation": What you understand the user wants
2. "information_needed": List of what you need to discover
3. "discovery_commands": List of commands to understand the project, each with:
   - "cmd": The shell command to run
   - "purpose": Why we're running it
   - "timeout": Max seconds to wait (default 5)
4. "initial_strategy": Your approach after discovery

Make NO assumptions about:
- Programming language (could be Python, Java, JS, Rust, Go, C++, etc.)
- Project structure or build tools
- Operating system specifics
- File locations or naming conventions

Start with simple, safe commands that work cross-platform.

Example response:
{{
  "interpretation": "User wants to analyze screenshot images in the project",
  "information_needed": ["image files present", "project structure", "file types"],
  "discovery_commands": [
    {{"cmd": "find . -type f -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' 2>/dev/null | head -20", "purpose": "Find image files", "timeout": 5}},
    {{"cmd": "ls -la | head -20", "purpose": "See top-level structure", "timeout": 2}},
    {{"cmd": "find . -maxdepth 2 -type f | grep -E '\\.(png|jpg|jpeg|gif|webp)$' | wc -l", "purpose": "Count image files", "timeout": 5}}
  ],
  "initial_strategy": "Find and analyze image files based on discovery"
}}"""
        
        try:
            response = self._call_bedrock(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Failed to get initial plan: {e}")
            return {
                "interpretation": "Failed to analyze request",
                "discovery_commands": [
                    {"cmd": "ls -la", "purpose": "Basic directory listing", "timeout": 2}
                ]
            }
    
    def _execute_discovery(self, commands: List[Dict[str, Any]], verbose: bool) -> Dict[str, Any]:
        """Execute discovery commands and collect results."""
        results = {}
        
        if not commands:
            return results
        
        if verbose:
            self.console.print(f"[dim]Running {len(commands)} discovery commands...[/dim]")
        
        for cmd_info in commands:
            cmd = cmd_info.get('cmd', '')
            purpose = cmd_info.get('purpose', 'Unknown')
            timeout = cmd_info.get('timeout', 5)
            
            if verbose:
                self.console.print(f"[dim]  • {purpose}: {cmd}[/dim]")
            
            try:
                # Run command with timeout
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                output = result.stdout
                if result.returncode != 0 and result.stderr:
                    output = f"Error: {result.stderr}"
                
                results[purpose] = {
                    "command": cmd,
                    "output": output[:1000],  # Limit output size
                    "success": result.returncode == 0
                }
                
            except subprocess.TimeoutExpired:
                results[purpose] = {
                    "command": cmd,
                    "output": "Command timed out",
                    "success": False
                }
            except Exception as e:
                results[purpose] = {
                    "command": cmd,
                    "output": f"Error: {str(e)}",
                    "success": False
                }
        
        return results
    
    def _create_final_plan(self, user_input: str, initial_plan: Dict[str, Any], 
                          discovery_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create final execution plan based on discovery results."""
        prompt = f"""Based on discovery results, create the final execution plan.

Original request: "{user_input}"
Initial interpretation: {initial_plan.get('interpretation', 'Unknown')}

Discovery results:
{json.dumps(discovery_results, indent=2)}

Now create a SPECIFIC execution plan. Return ONLY valid JSON with:

1. "project_info": What we learned about the project
   - "languages": List of programming languages found
   - "project_type": Type of project (web, cli, library, etc.)
   - "build_tools": Build tools/package managers found
   - "key_directories": Important directories identified
   
2. "files_to_analyze": List of specific files or patterns, each with:
   - "pattern": File pattern (e.g., "*.png", "src/**/*.js")
   - "purpose": Why we need these files
   - "max_files": Maximum number to include
   
3. "actions": List of specific actions to take, each with:
   - "type": "read_file", "run_command", "analyze_image", "search_code"
   - "target": File path, command, or search pattern
   - "purpose": Why we're doing this
   
4. "analysis_approach": How to analyze based on what we found
5. "expected_output": What results the user expects
6. "output_format": How to present results (summary, detailed, code blocks, etc.)

Focus on what the user ACTUALLY wants based on their request and what we discovered.

Example: If user said "summarize screenshots" and we found PNG files:
{{
  "project_info": {{
    "languages": ["python"],
    "has_images": true,
    "image_files_found": 4
  }},
  "files_to_analyze": [
    {{"pattern": "*.png", "purpose": "Analyze screenshot images", "max_files": 20}},
    {{"pattern": "*screenshot*.png", "purpose": "Priority screenshot files", "max_files": 10}}
  ],
  "actions": [
    {{"type": "analyze_image", "target": "each found image", "purpose": "Extract visual content"}}
  ],
  "analysis_approach": "Visual analysis of each screenshot",
  "expected_output": "Description of what's shown in each screenshot",
  "output_format": "structured summary with image descriptions"
}}"""
        
        try:
            response = self._call_bedrock(prompt)
            plan = self._parse_json_response(response)
            
            # Add discovery results to plan for reference
            plan['discovery_results'] = discovery_results
            plan['user_request'] = user_input
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create final plan: {e}")
            return {
                "error": str(e),
                "discovery_results": discovery_results,
                "files_to_analyze": [],
                "actions": []
            }
    
    def _call_bedrock(self, prompt: str) -> str:
        """Call Bedrock and get response."""
        messages = [Message(role="user", content=prompt)]
        response = ""
        
        for chunk in self.bedrock_client.send_message(messages, stream=True):
            response += chunk
            
        return response
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Bedrock response."""
        import re
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                logger.debug(f"Response was: {response}")
        
        # Fallback
        return {"error": "Failed to parse response", "raw_response": response[:500]}
    
    def execute_plan(self, plan: Dict[str, Any], file_handler=None, image_handler=None) -> List[Any]:
        """Execute the plan and return results.
        
        Args:
            plan: The execution plan
            file_handler: Handler for file operations
            image_handler: Handler for image operations
            
        Returns:
            List of results from executing the plan
        """
        results = []
        
        # Process files to analyze
        files_found = []
        for file_spec in plan.get('files_to_analyze', []):
            pattern = file_spec.get('pattern', '')
            max_files = file_spec.get('max_files', 10)
            
            # Find files matching pattern
            if '**' in pattern:
                matches = list(Path.cwd().rglob(pattern.replace('**/', '')))
            else:
                matches = list(Path.cwd().glob(pattern))
            
            # Limit number of files
            for match in matches[:max_files]:
                if match.is_file():
                    files_found.append({
                        'path': match,
                        'purpose': file_spec.get('purpose', 'Analysis')
                    })
        
        # Return found files for now - actual execution would happen in interactive.py
        return {
            'files_found': files_found,
            'plan': plan
        }