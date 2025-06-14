"""Configuration management for AI Code Assistant."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class Config:
    """Configuration settings for the AI Code Assistant."""
    model: str = "sonnet-3.7"
    region: str = "us-east-1"
    temperature: float = 0.7
    max_tokens: int = 128000
    compact_mode: bool = False
    history_dir: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create Config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Config to dictionary."""
        return asdict(self)


class ConfigManager:
    """Manages application configuration with persistence."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory to store configuration files
        """
        if config_dir is None:
            config_dir = Path.home() / ".steve_code"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        # Load or create default config
        self.config = self.load_config()
    
    def load_config(self) -> Config:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return Config.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Return default config
        return Config()
    
    def save_config(self):
        """Save current configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)
    
    def update_config(self, **kwargs):
        """Update configuration values.
        
        Args:
            **kwargs: Configuration values to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self.save_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return getattr(self.config, key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            self.save_config()
    
    def reset(self):
        """Reset configuration to defaults."""
        self.config = Config()
        self.save_config()
    
    def load_from_env(self):
        """Load configuration from environment variables."""
        env_mapping = {
            'AI_ASSISTANT_MODEL': 'model',
            'AI_ASSISTANT_REGION': 'region',
            'AI_ASSISTANT_TEMPERATURE': 'temperature',
            'AI_ASSISTANT_MAX_TOKENS': 'max_tokens',
            'AI_ASSISTANT_COMPACT_MODE': 'compact_mode',
            'AI_ASSISTANT_HISTORY_DIR': 'history_dir',
        }
        
        for env_key, config_key in env_mapping.items():
            if env_key in os.environ:
                value = os.environ[env_key]
                
                # Convert types
                if config_key == 'temperature':
                    value = float(value)
                elif config_key == 'max_tokens':
                    value = int(value)
                elif config_key == 'compact_mode':
                    value = value.lower() in ('true', '1', 'yes')
                
                setattr(self.config, config_key, value)