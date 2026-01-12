"""Git-backed user storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from git import Repo
from git.exc import InvalidGitRepositoryError

if TYPE_CHECKING:
    from git import Commit

log = structlog.get_logger()


@dataclass
class VersionInfo:
    """Information about a file version."""

    commit_sha: str
    message: str
    author: str
    timestamp: datetime
    is_current: bool = False


@dataclass
class FileDiff:
    """Diff between two versions of a file."""

    old_content: str
    new_content: str
    old_sha: str
    new_sha: str


class GitUserStorage:
    """
    Git-backed storage for a single user.

    Directory structure:
        .data/users/{user_id}/
            .git/
            blocks/
                student.toml
                engagement_strategy.toml
                journey.toml
            pending_diffs/
                {diff_id}.json
            agent_threads/
                {agent_name}/
                    {chat_id}.json

    Each edit creates a git commit for full version history.
    """

    def __init__(self, user_id: str, base_dir: Path | str) -> None:
        """
        Initialize user storage.

        Args:
            user_id: User identifier
            base_dir: Base directory for all user storage (e.g., .data/users)

        """
        self.user_id = user_id
        self.base_dir = Path(base_dir)
        self.user_dir = self.base_dir / user_id
        self.blocks_dir = self.user_dir / "blocks"
        self.diffs_dir = self.user_dir / "pending_diffs"
        self._repo: Repo | None = None
        self.logger = log.bind(user_id=user_id, component="git_storage")

    @property
    def repo(self) -> Repo:
        """Get or initialize the git repository."""
        if self._repo is None:
            try:
                self._repo = Repo(str(self.user_dir))
            except InvalidGitRepositoryError:
                self._repo = self._init_repo()
        return self._repo

    @property
    def exists(self) -> bool:
        """Check if user storage exists."""
        return self.user_dir.exists() and (self.user_dir / ".git").exists()

    def init(self) -> None:
        """Initialize user storage directory and git repo."""
        if self.exists:
            self.logger.debug("storage_already_exists")
            return

        # Create directories
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.diffs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize git repo
        self._repo = self._init_repo()
        self.logger.info("storage_initialized")

    def _init_repo(self) -> Repo:
        """Initialize a new git repository."""
        repo = Repo.init(str(self.user_dir))

        # Configure repo
        with repo.config_writer() as config:
            config.set_value("user", "name", "YouLab System")
            config.set_value("user", "email", "system@youlab.local")

        # Create initial commit
        gitignore = self.user_dir / ".gitignore"
        gitignore.write_text("# YouLab user storage\n*.pyc\n__pycache__/\n")
        repo.index.add([".gitignore"])
        repo.index.commit("Initialize user storage")

        return repo

    def read_block(self, label: str) -> str | None:
        """
        Read a memory block file.

        Args:
            label: Block label (e.g., "student", "journey")

        Returns:
            File content or None if not found

        """
        path = self.blocks_dir / f"{label}.toml"
        if not path.exists():
            return None
        return path.read_text()

    def write_block(
        self,
        label: str,
        content: str,
        message: str | None = None,
        author: str = "user",
    ) -> str:
        """
        Write a memory block and commit.

        Args:
            label: Block label
            content: TOML content
            message: Commit message (auto-generated if None)
            author: Who made the change ("user", "system", or agent name)

        Returns:
            Commit SHA

        """
        # Ensure blocks directory exists
        self.blocks_dir.mkdir(parents=True, exist_ok=True)

        path = self.blocks_dir / f"{label}.toml"
        path.write_text(content)

        # Stage and commit
        rel_path = path.relative_to(self.user_dir)
        self.repo.index.add([str(rel_path)])

        if message is None:
            message = f"Update {label} block"

        commit = self.repo.index.commit(
            f"{message}\n\nAuthor: {author}",
        )

        self.logger.info(
            "block_committed",
            block=label,
            sha=commit.hexsha[:8],
            author=author,
        )

        return commit.hexsha

    def get_block_history(
        self,
        label: str,
        limit: int = 20,
    ) -> list[VersionInfo]:
        """
        Get version history for a block.

        Args:
            label: Block label
            limit: Maximum versions to return

        Returns:
            List of VersionInfo, newest first

        """
        path = self.blocks_dir / f"{label}.toml"
        rel_path = path.relative_to(self.user_dir)

        if not path.exists():
            return []

        versions = []
        for i, commit in enumerate(self.repo.iter_commits(paths=str(rel_path), max_count=limit)):
            msg = self._get_message(commit)
            versions.append(
                VersionInfo(
                    commit_sha=commit.hexsha,
                    message=msg.split("\n")[0],
                    author=self._extract_author(commit),
                    timestamp=datetime.fromtimestamp(commit.committed_date),
                    is_current=(i == 0),
                )
            )

        return versions

    def get_block_at_version(self, label: str, commit_sha: str) -> str | None:
        """
        Get block content at a specific version.

        Args:
            label: Block label
            commit_sha: Git commit SHA

        Returns:
            Content at that version or None

        """
        try:
            commit = self.repo.commit(commit_sha)
            rel_path = f"blocks/{label}.toml"
            blob = commit.tree / rel_path
            return blob.data_stream.read().decode("utf-8")
        except Exception as e:
            self.logger.warning(
                "version_read_failed",
                block=label,
                sha=commit_sha[:8],
                error=str(e),
            )
            return None

    def restore_block(
        self,
        label: str,
        commit_sha: str,
        message: str | None = None,
    ) -> str:
        """
        Restore a block to a previous version.

        Args:
            label: Block label
            commit_sha: Version to restore
            message: Commit message

        Returns:
            New commit SHA

        """
        content = self.get_block_at_version(label, commit_sha)
        if content is None:
            msg = f"Version {commit_sha[:8]} not found for {label}"
            raise ValueError(msg)

        if message is None:
            message = f"Restore {label} to version {commit_sha[:8]}"

        return self.write_block(label, content, message=message, author="user")

    def diff_versions(
        self,
        label: str,
        old_sha: str,
        new_sha: str,
    ) -> FileDiff:
        """
        Get diff between two versions.

        Args:
            label: Block label
            old_sha: Older version SHA
            new_sha: Newer version SHA

        Returns:
            FileDiff with old and new content

        """
        old_content = self.get_block_at_version(label, old_sha) or ""
        new_content = self.get_block_at_version(label, new_sha) or ""

        return FileDiff(
            old_content=old_content,
            new_content=new_content,
            old_sha=old_sha,
            new_sha=new_sha,
        )

    def _get_message(self, commit: Commit) -> str:
        """Get commit message as a string (handles bytes from GitPython)."""
        msg = commit.message
        if isinstance(msg, bytes):
            return msg.decode("utf-8", errors="replace")
        return str(msg)

    def _extract_author(self, commit: Commit) -> str:
        """Extract author from commit message footer."""
        msg = self._get_message(commit)
        lines = msg.strip().split("\n")
        for line in lines:
            if line.startswith("Author: "):
                return line.replace("Author: ", "")
        return "unknown"

    def list_blocks(self) -> list[str]:
        """List all block labels in storage."""
        if not self.blocks_dir.exists():
            return []
        return [p.stem for p in self.blocks_dir.glob("*.toml")]


class GitUserStorageManager:
    """
    Factory for GitUserStorage instances.

    Manages the base directory and provides user storage instances.
    """

    def __init__(self, base_dir: Path | str) -> None:
        """
        Initialize the storage manager.

        Args:
            base_dir: Base directory for all user storage

        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, GitUserStorage] = {}

    def get(self, user_id: str) -> GitUserStorage:
        """Get storage instance for a user (cached)."""
        if user_id not in self._cache:
            self._cache[user_id] = GitUserStorage(user_id, self.base_dir)
        return self._cache[user_id]

    def user_exists(self, user_id: str) -> bool:
        """Check if user storage exists."""
        return self.get(user_id).exists

    def list_users(self) -> list[str]:
        """List all user IDs with storage."""
        return [d.name for d in self.base_dir.iterdir() if d.is_dir() and (d / ".git").exists()]
