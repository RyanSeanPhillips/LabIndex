"""
Read-Only Filesystem Adapter.

SAFETY: This is the ONLY way LabIndex accesses the filesystem.
All operations are strictly read-only. No write, delete, move, or rename.

This class enforces safety at the application level. For additional
protection, mount network shares as read-only at the OS level.
"""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Iterator, Optional, Set

from ..ports.fs_port import FSPort, DirEntry, ReadBudget


class ReadOnlyFS(FSPort):
    """
    Read-only filesystem implementation.

    SAFETY GUARANTEES:
    - No write operations
    - No delete operations
    - No move/rename operations
    - Budgeted reads to prevent hanging on large files
    - Path validation to prevent traversal attacks
    """

    # Extensions that are NEVER read (even for sampling)
    BLOCKED_EXTENSIONS: Set[str] = {
        ".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".sh",
        ".msi", ".scr", ".com", ".pif", ".vbs", ".js",
    }

    def __init__(self, allowed_roots: Optional[list[Path]] = None):
        """
        Initialize the read-only filesystem.

        Args:
            allowed_roots: If provided, only allow access under these paths.
                          This provides additional defense against path traversal.
        """
        self.allowed_roots = [Path(r).resolve() for r in (allowed_roots or [])]
        self._read_count = 0
        self._bytes_read = 0

    def _validate_path(self, path: Path) -> Path:
        """Validate and resolve a path, checking against allowed roots."""
        resolved = Path(path).resolve()

        # Check against allowed roots if configured
        if self.allowed_roots:
            if not any(self._is_under(resolved, root) for root in self.allowed_roots):
                raise PermissionError(
                    f"Path {resolved} is not under any allowed root. "
                    f"Allowed roots: {self.allowed_roots}"
                )

        return resolved

    def _is_under(self, path: Path, root: Path) -> bool:
        """Check if path is under root (handles symlinks safely)."""
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _is_blocked_extension(self, path: Path) -> bool:
        """Check if file has a blocked extension."""
        return path.suffix.lower() in self.BLOCKED_EXTENSIONS

    def scandir(self, path: Path) -> Iterator[DirEntry]:
        """Iterate over entries in a directory."""
        resolved = self._validate_path(path)

        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {resolved}")

        with os.scandir(resolved) as entries:
            for entry in entries:
                try:
                    stat_info = entry.stat(follow_symlinks=False)
                    yield DirEntry(
                        name=entry.name,
                        path=entry.path,
                        is_dir=entry.is_dir(follow_symlinks=False),
                        is_file=entry.is_file(follow_symlinks=False),
                        size_bytes=stat_info.st_size,
                        mtime=datetime.fromtimestamp(stat_info.st_mtime),
                        ctime=datetime.fromtimestamp(stat_info.st_ctime),
                    )
                except (PermissionError, OSError):
                    # Skip entries we can't access
                    continue

    def exists(self, path: Path) -> bool:
        """Check if a path exists."""
        try:
            resolved = self._validate_path(path)
            return resolved.exists()
        except PermissionError:
            return False

    def is_dir(self, path: Path) -> bool:
        """Check if path is a directory."""
        resolved = self._validate_path(path)
        return resolved.is_dir()

    def is_file(self, path: Path) -> bool:
        """Check if path is a file."""
        resolved = self._validate_path(path)
        return resolved.is_file()

    def stat(self, path: Path) -> DirEntry:
        """Get file/directory metadata."""
        resolved = self._validate_path(path)
        stat_info = resolved.stat()

        return DirEntry(
            name=resolved.name,
            path=str(resolved),
            is_dir=resolved.is_dir(),
            is_file=resolved.is_file(),
            size_bytes=stat_info.st_size,
            mtime=datetime.fromtimestamp(stat_info.st_mtime),
            ctime=datetime.fromtimestamp(stat_info.st_ctime),
        )

    def read_bytes(self, path: Path, budget: Optional[ReadBudget] = None) -> bytes:
        """Read file contents as bytes with budget limits."""
        resolved = self._validate_path(path)

        if not resolved.is_file():
            raise FileNotFoundError(f"Not a file: {resolved}")

        if self._is_blocked_extension(resolved):
            raise PermissionError(f"Reading blocked for extension: {resolved.suffix}")

        budget = budget or ReadBudget()
        start_time = time.time()

        with open(resolved, "rb") as f:
            if budget.sample_mode == "head":
                data = f.read(budget.max_bytes)
            elif budget.sample_mode == "tail":
                # Seek to end minus max_bytes
                f.seek(0, 2)  # End of file
                size = f.tell()
                start_pos = max(0, size - budget.max_bytes)
                f.seek(start_pos)
                data = f.read(budget.max_bytes)
            else:  # sample mode - read chunks from different parts
                f.seek(0, 2)
                size = f.tell()
                chunk_size = budget.max_bytes // 3
                chunks = []

                # Head
                f.seek(0)
                chunks.append(f.read(chunk_size))

                # Middle
                if size > chunk_size * 2:
                    f.seek(size // 2 - chunk_size // 2)
                    chunks.append(f.read(chunk_size))

                # Tail
                if size > chunk_size:
                    f.seek(max(0, size - chunk_size))
                    chunks.append(f.read(chunk_size))

                data = b"".join(chunks)

            # Check time budget
            elapsed = time.time() - start_time
            if elapsed > budget.max_seconds:
                # Truncate if we're over time
                pass  # Data already read

        self._read_count += 1
        self._bytes_read += len(data)
        return data

    def read_text(self, path: Path, budget: Optional[ReadBudget] = None,
                  encoding: str = "utf-8") -> str:
        """Read file contents as text with budget limits."""
        data = self.read_bytes(path, budget)
        try:
            return data.decode(encoding, errors="replace")
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="replace")

    @property
    def stats(self) -> dict:
        """Get read statistics."""
        return {
            "read_count": self._read_count,
            "bytes_read": self._bytes_read,
        }

    # =========================================================================
    # SAFETY: The following methods are intentionally NOT implemented.
    # This class is READ-ONLY by design.
    # =========================================================================

    def _forbidden(self, operation: str):
        raise NotImplementedError(
            f"Operation '{operation}' is forbidden. "
            f"ReadOnlyFS is strictly read-only by design."
        )

    # These would exist in a normal FS class, but we explicitly block them
    def write(self, *args, **kwargs):
        self._forbidden("write")

    def delete(self, *args, **kwargs):
        self._forbidden("delete")

    def remove(self, *args, **kwargs):
        self._forbidden("remove")

    def unlink(self, *args, **kwargs):
        self._forbidden("unlink")

    def rmdir(self, *args, **kwargs):
        self._forbidden("rmdir")

    def rename(self, *args, **kwargs):
        self._forbidden("rename")

    def move(self, *args, **kwargs):
        self._forbidden("move")

    def copy(self, *args, **kwargs):
        self._forbidden("copy")

    def mkdir(self, *args, **kwargs):
        self._forbidden("mkdir")

    def chmod(self, *args, **kwargs):
        self._forbidden("chmod")
