"""Check for updates to Steve Code."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple
import subprocess
import sys

import requests
from packaging import version

from .version import __version__

logger = logging.getLogger(__name__)


class UpdateChecker:
    """Check for updates from GitHub releases."""
    
    GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
    CACHE_FILE = Path.home() / ".steve_code" / "update_check_cache.json"
    CHECK_INTERVAL = timedelta(minutes=30)  # Check every 30 minutes
    
    def __init__(self, owner: str = "StoliRocks", repo: str = "steve-code"):
        """Initialize update checker.
        
        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
        """
        self.owner = owner
        self.repo = repo
        self.api_url = self.GITHUB_API_URL.format(owner=owner, repo=repo)
        
        # Ensure cache directory exists
        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def check_for_update(self, force: bool = False) -> Optional[Tuple[str, str]]:
        """Check if a new version is available.
        
        Args:
            force: Force check even if recently checked
            
        Returns:
            Tuple of (latest_version, download_url) if update available, None otherwise
        """
        # Check cache first
        if not force and self._is_cache_valid():
            cache_data = self._read_cache()
            if cache_data and not cache_data.get("update_available"):
                return None
        
        try:
            # Fetch latest release info
            response = requests.get(
                self.api_url,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=5
            )
            
            if response.status_code == 404:
                # No releases yet
                self._write_cache({"update_available": False})
                return None
            
            response.raise_for_status()
            release_data = response.json()
            
            # Extract version from tag
            tag_name = release_data.get("tag_name", "")
            latest_version = tag_name.lstrip("v")
            
            if not latest_version:
                return None
            
            # Compare versions
            current = version.parse(__version__)
            latest = version.parse(latest_version)
            
            logger.debug(f"Version check: current={current}, latest={latest}")
            
            if latest > current:
                download_url = release_data.get("html_url", "")
                self._write_cache({
                    "update_available": True,
                    "latest_version": latest_version,
                    "download_url": download_url,
                    "checked_at": datetime.now().isoformat()
                })
                return (latest_version, download_url)
            else:
                self._write_cache({"update_available": False})
                return None
                
        except Exception as e:
            logger.debug(f"Error checking for updates: {e}")
            return None
    
    def auto_update(self, confirm: bool = True) -> bool:
        """Attempt to auto-update the package.
        
        Args:
            confirm: Whether to ask for user confirmation
            
        Returns:
            True if update was successful
        """
        update_info = self.check_for_update()
        if not update_info:
            return False
        
        latest_version, download_url = update_info
        
        if confirm:
            print(f"\nNew version available: {latest_version} (current: {__version__})")
            print(f"Release: {download_url}")
            response = input("Would you like to update now? (y/N): ")
            if response.lower() != 'y':
                return False
        
        print("Updating Steve Code...")
        
        try:
            # Try to update using pip
            cmd = [
                sys.executable, "-m", "pip", "install", "--upgrade",
                f"git+https://github.com/{self.owner}/{self.repo}.git@v{latest_version}"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✓ Successfully updated to version {latest_version}")
                print("Please restart Steve Code to use the new version.")
                return True
            else:
                print(f"Error updating: {result.stderr}")
                print(f"\nTo update manually, run:")
                print(f"  pip install --upgrade git+https://github.com/{self.owner}/{self.repo}.git")
                return False
                
        except Exception as e:
            print(f"Error during update: {e}")
            print(f"\nTo update manually, run:")
            print(f"  pip install --upgrade git+https://github.com/{self.owner}/{self.repo}.git")
            return False
    
    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid."""
        try:
            if not self.CACHE_FILE.exists():
                return False
            
            cache_data = self._read_cache()
            if not cache_data or "checked_at" not in cache_data:
                return False
            
            checked_at = datetime.fromisoformat(cache_data["checked_at"])
            return datetime.now() - checked_at < self.CHECK_INTERVAL
            
        except Exception:
            return False
    
    def _read_cache(self) -> Optional[dict]:
        """Read the cache file."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return None
    
    def _write_cache(self, data: dict):
        """Write to the cache file."""
        try:
            data["checked_at"] = datetime.now().isoformat()
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


def get_update_message() -> Optional[str]:
    """Get a formatted update message if an update is available.
    
    Returns:
        Formatted update message or None
    """
    checker = UpdateChecker()
    update_info = checker.check_for_update()
    
    if update_info:
        latest_version, _ = update_info
        return (
            f"[yellow]📦 Update available: v{latest_version} "
            f"(current: v{__version__})[/yellow]\n"
            f"[dim]Run 'sc --update' to update[/dim]"
        )
    
    return None