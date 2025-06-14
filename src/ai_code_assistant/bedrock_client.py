"""AWS Bedrock client for Claude model interactions."""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .system_prompts import get_system_prompt, get_interactive_prompt
from .retry_utils import retry_with_backoff


class ModelType(Enum):
    """Supported Claude models."""
    # Current generation models with .us. prefix for load balancing
    CLAUDE_SONNET_4 = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    CLAUDE_OPUS_4 = "us.anthropic.claude-opus-4-20250514-v1:0"
    CLAUDE_3_7_SONNET = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    
    # Legacy model names (kept for backward compatibility)
    CLAUDE_3_5_SONNET_V2 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    CLAUDE_3_5_SONNET = "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
    CLAUDE_3_OPUS = "us.anthropic.claude-3-opus-20240229-v1:0"
    
    @property
    def short_name(self) -> str:
        """Get the short name for system prompt lookup."""
        mapping = {
            self.CLAUDE_SONNET_4: "sonnet-4",
            self.CLAUDE_OPUS_4: "opus-4",
            self.CLAUDE_3_7_SONNET: "sonnet-3.7",
            self.CLAUDE_3_5_SONNET_V2: "sonnet-3.5-v2",
            self.CLAUDE_3_5_SONNET: "sonnet-3.5",
            self.CLAUDE_3_OPUS: "opus-3"
        }
        return mapping.get(self, "sonnet-4")


@dataclass
class Message:
    """Represents a message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: Union[str, List[Dict[str, Any]]]  # String or multimodal content blocks


class BedrockClient:
    """Client for interacting with AWS Bedrock Claude models."""
    
    def __init__(
        self,
        model_type: ModelType = ModelType.CLAUDE_SONNET_4,
        region_name: str = "us-east-1",
        max_tokens: int = 128000,
        temperature: float = 0.7
    ):
        """Initialize the Bedrock client.
        
        Args:
            model_type: The Claude model to use
            region_name: AWS region name
            max_tokens: Maximum tokens in response
            temperature: Model temperature (0-1)
        """
        self.model_type = model_type
        self.region_name = region_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logging.getLogger(__name__)
        
        try:
            self.client = boto3.client(
                service_name='bedrock-runtime',
                region_name=region_name
            )
        except NoCredentialsError:
            raise RuntimeError(
                "AWS credentials not found. Please configure your AWS credentials:\n"
                "  - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                "  - Or run 'aws configure' to set up credentials\n"
                "  - Or use IAM roles if running on EC2"
            )
    
    def create_prompt(self, messages: List[Message], system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Create a prompt in the format expected by Bedrock.
        
        Args:
            messages: List of conversation messages
            system_prompt: Optional system prompt
            
        Returns:
            Dictionary with the prompt configuration
        """
        formatted_messages = []
        for msg in messages:
            # Handle both string and multimodal content
            if isinstance(msg.content, str):
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            else:
                # Multimodal content (list of content blocks)
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        body = {
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "anthropic_version": "bedrock-2023-05-31"
        }
        
        if system_prompt:
            body["system"] = system_prompt
        
        return body
    
    @retry_with_backoff(max_retries=3, backoff_factor=2.0, max_delay=30.0)
    def send_message(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        stream: bool = True
    ) -> Any:
        """Send a message to the Claude model with automatic retry logic.
        
        Args:
            messages: List of conversation messages
            system_prompt: Optional system prompt
            stream: Whether to stream the response
            
        Returns:
            Response from the model (generator if streaming, dict otherwise)
        """
        body = self.create_prompt(messages, system_prompt)
        
        try:
            if stream:
                response = self.client.invoke_model_with_response_stream(
                    modelId=self.model_type.value,
                    body=json.dumps(body),
                    contentType='application/json',
                    accept='application/json'
                )
                return self._process_stream(response)
            else:
                response = self.client.invoke_model(
                    modelId=self.model_type.value,
                    body=json.dumps(body),
                    contentType='application/json',
                    accept='application/json'
                )
                response_body = json.loads(response['body'].read())
                return response_body
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            # Non-retryable errors
            if error_code == 'AccessDeniedException':
                raise RuntimeError(
                    f"Access denied to model {self.model_type.value}. "
                    "Please ensure your AWS account has access to this model."
                )
            elif error_code == 'ValidationException':
                raise RuntimeError(f"Invalid request: {error_message}")
            else:
                # Let retry logic handle other errors
                raise
    
    def _process_stream(self, response):
        """Process streaming response from Bedrock.
        
        Args:
            response: Streaming response from Bedrock
            
        Yields:
            Text chunks from the response
        """
        event_stream = response.get('body')
        if not event_stream:
            return
        
        for event in event_stream:
            chunk = event.get('chunk')
            if chunk:
                try:
                    chunk_data = json.loads(chunk.get('bytes').decode())
                    
                    if chunk_data.get('type') == 'content_block_delta':
                        delta = chunk_data.get('delta', {})
                        if delta.get('type') == 'text_delta':
                            text = delta.get('text', '')
                            if text:
                                yield text
                    
                    elif chunk_data.get('type') == 'message_stop':
                        return
                        
                except json.JSONDecodeError:
                    self.logger.error("Failed to decode chunk")
                    continue
    
    def switch_model(self, model_type: ModelType):
        """Switch to a different Claude model.
        
        Args:
            model_type: The new model to use
        """
        self.model_type = model_type
        self.logger.info(f"Switched to model: {model_type.value}")
    
    def get_default_system_prompt(self, interactive: bool = False, project_context: str = "") -> str:
        """Get the default system prompt for the current model.
        
        Args:
            interactive: Whether to use interactive mode prompt
            
        Returns:
            The appropriate system prompt
        """
        model_name = self.model_type.short_name
        if interactive:
            return get_interactive_prompt(model_name)
        return get_system_prompt(model_name)