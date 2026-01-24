"""
Filesystem port interface.

Defines the contract for filesystem access.
All implementations MUST be read-only.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DirEntry:
    """A directory entry from scandir."""
    name: str
    path: str
    is_dir: bool
    is_file: bool
    size_bytes: int
    mtime: datetime
    ctime: datetime


@dataclass
class ReadBudget:
    """Limits for read operations."""
    max_bytes: int = 10_000      # Max bytes to read
    max_seconds: float = 5.0     # Max time for operation
    sample_mode: str = "head"    # "head", "tail", or "sample"


class FSPort(ABC):
    """
    Abstract interface for filesystem operations.

    IMPORTANT: All implementations MUST be read-only.
    No write, delete, move, or rename operations allowed.
    """

    @abstractmethod
    def scandir(self, path: Path) -> Iterator[DirEntry]:
        """
        Iterate over entries in a directory.

        Args:
            path: Directory to scan

        Yields:
            DirEntry for each item in the directory
        """
        pass

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Check if a path exists."""
        pass

    @abstractmethod
    def is_dir(self, path: Path) -> bool:
        """Check if path is a directory."""
        pass

    @abstractmethod
    def is_file(self, path: Path) -> bool:
        """Check if path is a file."""
        pass

    @abstractmethod
    def stat(self, path: Path) -> DirEntry:
        """Get file/directory metadata."""
        pass

    @abstractmethod
    def read_bytes(self, path: Path, budget: Optional[ReadBudget] = None) -> bytes:
        """
        Read file contents as bytes.

        Args:
            path: File to read
            budget: Optional limits on how much to read

        Returns:
            File contents (possibly truncated per budget)
        """
        pass

    @abstractmethod
    def read_text(self, path: Path, budget: Optional[ReadBudget] = None,
                  encoding: str = "utf-8") -> str:
        """
        Read file contents as text.

        Args:
            path: File to read
            budget: Optional limits on how much to read
            encoding: Text encoding

        Returns:
            File contents as string (possibly truncated per budget)
        """
        pass

    # SAFETY: These methods must NOT exist in implementations
    # write, delete, move, rename, chmod, etc.
