"""Git integration for Steve Code."""

import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GitStatus:
    """Represents the current git status."""
    branch: str
    staged: List[str]
    modified: List[str]
    untracked: List[str]
    ahead: int
    behind: int
    is_clean: bool


class GitIntegration:
    """Handle git operations for the assistant."""
    
    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize git integration.
        
        Args:
            repo_path: Path to git repository. Defaults to current directory.
        """
        self.repo_path = repo_path or Path.cwd()
        self._verify_git_repo()
    
    def _verify_git_repo(self) -> None:
        """Verify that we're in a git repository."""
        try:
            self._run_git_command(["status"])
        except subprocess.CalledProcessError:
            raise RuntimeError(f"{self.repo_path} is not a git repository")
    
    def _run_git_command(self, args: List[str]) -> str:
        """Run a git command and return output.
        
        Args:
            args: Git command arguments
            
        Returns:
            Command output
        """
        cmd = ["git"] + args
        result = subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    
    def get_status(self) -> GitStatus:
        """Get the current git status.
        
        Returns:
            GitStatus object with current repository state
        """
        # Get branch name
        try:
            branch = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        except subprocess.CalledProcessError:
            branch = "detached"
        
        # Get status porcelain for parsing
        status_output = self._run_git_command(["status", "--porcelain"])
        
        staged = []
        modified = []
        untracked = []
        
        for line in status_output.splitlines():
            if not line:
                continue
            
            status_code = line[:2]
            filename = line[3:].strip()
            
            if status_code[0] in ['A', 'M', 'D', 'R', 'C']:
                staged.append(filename)
            if status_code[1] in ['M', 'D']:
                modified.append(filename)
            elif status_code == '??':
                untracked.append(filename)
        
        # Get ahead/behind counts
        ahead = 0
        behind = 0
        try:
            # Get upstream branch
            upstream = self._run_git_command(["rev-parse", "--abbrev-ref", "@{u}"])
            if upstream:
                # Get ahead/behind counts
                counts = self._run_git_command(["rev-list", "--left-right", "--count", f"HEAD...@{{u}}"])
                if counts:
                    parts = counts.split()
                    if len(parts) >= 2:
                        ahead = int(parts[0])
                        behind = int(parts[1])
        except subprocess.CalledProcessError:
            # No upstream branch
            pass
        
        is_clean = not (staged or modified or untracked)
        
        return GitStatus(
            branch=branch,
            staged=staged,
            modified=modified,
            untracked=untracked,
            ahead=ahead,
            behind=behind,
            is_clean=is_clean
        )
    
    def get_diff(self, staged: bool = False, file_path: Optional[str] = None) -> str:
        """Get git diff output.
        
        Args:
            staged: Whether to show staged changes
            file_path: Specific file to diff
            
        Returns:
            Diff output
        """
        cmd = ["diff"]
        if staged:
            cmd.append("--cached")
        if file_path:
            cmd.append(file_path)
        
        try:
            return self._run_git_command(cmd)
        except subprocess.CalledProcessError:
            return ""
    
    def get_log(self, limit: int = 10, oneline: bool = True) -> str:
        """Get git log output.
        
        Args:
            limit: Number of commits to show
            oneline: Whether to use oneline format
            
        Returns:
            Log output
        """
        cmd = ["log", f"-{limit}"]
        if oneline:
            cmd.append("--oneline")
        else:
            cmd.extend(["--pretty=format:%h %an %ar: %s"])
        
        return self._run_git_command(cmd)
    
    def stage_files(self, files: List[str]) -> None:
        """Stage files for commit.
        
        Args:
            files: List of file paths to stage
        """
        if not files:
            return
        
        cmd = ["add"] + files
        self._run_git_command(cmd)
    
    def unstage_files(self, files: List[str]) -> None:
        """Unstage files.
        
        Args:
            files: List of file paths to unstage
        """
        if not files:
            return
        
        cmd = ["reset", "HEAD", "--"] + files
        self._run_git_command(cmd)
    
    def commit(self, message: str, files: Optional[List[str]] = None) -> str:
        """Create a git commit.
        
        Args:
            message: Commit message
            files: Optional list of files to stage before committing
            
        Returns:
            Commit hash
        """
        if files:
            self.stage_files(files)
        
        # Check if there are changes to commit
        status = self.get_status()
        if not status.staged:
            raise RuntimeError("No changes staged for commit")
        
        # Create commit
        self._run_git_command(["commit", "-m", message])
        
        # Get commit hash
        return self._run_git_command(["rev-parse", "HEAD"])
    
    def get_current_branch(self) -> str:
        """Get the current branch name.
        
        Returns:
            Branch name
        """
        return self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    
    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get the URL of a remote.
        
        Args:
            remote: Remote name
            
        Returns:
            Remote URL or None
        """
        try:
            return self._run_git_command(["remote", "get-url", remote])
        except subprocess.CalledProcessError:
            return None
    
    def format_status_for_display(self, status: GitStatus) -> str:
        """Format git status for display.
        
        Args:
            status: GitStatus object
            
        Returns:
            Formatted status string
        """
        lines = [f"On branch: {status.branch}"]
        
        if status.ahead or status.behind:
            sync_status = []
            if status.ahead:
                sync_status.append(f"{status.ahead} ahead")
            if status.behind:
                sync_status.append(f"{status.behind} behind")
            lines.append(f"Branch is {' and '.join(sync_status)} of upstream")
        
        if status.is_clean:
            lines.append("\nWorking tree clean")
        else:
            if status.staged:
                lines.append(f"\nStaged changes ({len(status.staged)}):")
                for file in status.staged[:10]:  # Limit display
                    lines.append(f"  • {file}")
                if len(status.staged) > 10:
                    lines.append(f"  ... and {len(status.staged) - 10} more")
            
            if status.modified:
                lines.append(f"\nModified files ({len(status.modified)}):")
                for file in status.modified[:10]:
                    lines.append(f"  • {file}")
                if len(status.modified) > 10:
                    lines.append(f"  ... and {len(status.modified) - 10} more")
            
            if status.untracked:
                lines.append(f"\nUntracked files ({len(status.untracked)}):")
                for file in status.untracked[:10]:
                    lines.append(f"  • {file}")
                if len(status.untracked) > 10:
                    lines.append(f"  ... and {len(status.untracked) - 10} more")
        
        return "\n".join(lines)
    
    def suggest_commit_message(self, diff: str) -> str:
        """Suggest a commit message based on the diff.
        
        Args:
            diff: Git diff output
            
        Returns:
            Suggested commit message
        """
        # This is a simple implementation
        # In practice, you might use the AI to generate this
        if not diff:
            return "Update files"
        
        # Count changes
        lines = diff.splitlines()
        files_changed = set()
        additions = 0
        deletions = 0
        
        for line in lines:
            if line.startswith("+++") or line.startswith("---"):
                if line[4:].startswith("b/"):
                    files_changed.add(line[6:])
                elif line[4:].startswith("a/"):
                    files_changed.add(line[6:])
            elif line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
        
        # Generate message based on changes
        if len(files_changed) == 1:
            file = list(files_changed)[0]
            base_name = Path(file).stem
            if additions > deletions:
                return f"Add functionality to {base_name}"
            elif deletions > additions:
                return f"Refactor {base_name}"
            else:
                return f"Update {base_name}"
        else:
            return f"Update {len(files_changed)} files"