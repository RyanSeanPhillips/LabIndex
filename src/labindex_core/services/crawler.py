"""
Crawler Service - Tier 0 Inventory.

Scans directories and populates the file index.
Uses only scandir/stat - does not read file contents.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List
from dataclasses import dataclass

from ..ports.fs_port import FSPort
from ..ports.db_port import DBPort
from ..domain.models import FileRecord, CrawlJob, IndexRoot
from ..domain.enums import FileCategory, IndexStatus, JobStatus


@dataclass
class CrawlProgress:
    """Progress information for a crawl operation."""
    root_id: int
    dirs_scanned: int
    files_found: int
    errors: int
    current_path: str
    is_complete: bool = False


class CrawlerService:
    """
    Service for scanning directories and building the file inventory.

    This is Tier 0 indexing - only scandir/stat, no file content reads.
    """

    def __init__(self, fs: FSPort, db: DBPort):
        """
        Initialize the crawler service.

        Args:
            fs: Filesystem adapter (must be read-only)
            db: Database adapter
        """
        self.fs = fs
        self.db = db
        self._cancelled = False

    def add_root(self, path: str, label: Optional[str] = None) -> IndexRoot:
        """
        Add a new root folder for indexing.

        Args:
            path: Path to the folder
            label: Human-readable label (defaults to folder name)

        Returns:
            The created IndexRoot
        """
        path_obj = Path(path)
        if not self.fs.exists(path_obj):
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not self.fs.is_dir(path_obj):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        label = label or path_obj.name
        return self.db.add_root(str(path_obj.resolve()), label)

    def crawl_root(
        self,
        root_id: int,
        progress_callback: Optional[Callable[[CrawlProgress], None]] = None,
        max_depth: Optional[int] = None,
    ) -> CrawlProgress:
        """
        Crawl a root folder and populate the file index.

        Args:
            root_id: ID of the root to crawl
            progress_callback: Called periodically with progress updates
            max_depth: Maximum directory depth (None = unlimited)

        Returns:
            Final CrawlProgress
        """
        root = self.db.get_root(root_id)
        if not root:
            raise ValueError(f"Root not found: {root_id}")

        self._cancelled = False
        progress = CrawlProgress(
            root_id=root_id,
            dirs_scanned=0,
            files_found=0,
            errors=0,
            current_path=root.root_path,
        )

        # Crawl recursively
        self._crawl_directory(
            root_id=root_id,
            root_path=Path(root.root_path),
            dir_path=Path(root.root_path),
            progress=progress,
            progress_callback=progress_callback,
            current_depth=0,
            max_depth=max_depth,
        )

        progress.is_complete = True
        if progress_callback:
            progress_callback(progress)

        return progress

    def _crawl_directory(
        self,
        root_id: int,
        root_path: Path,
        dir_path: Path,
        progress: CrawlProgress,
        progress_callback: Optional[Callable[[CrawlProgress], None]],
        current_depth: int,
        max_depth: Optional[int],
    ):
        """Recursively crawl a directory."""
        if self._cancelled:
            return

        if max_depth is not None and current_depth > max_depth:
            return

        progress.current_path = str(dir_path)
        progress.dirs_scanned += 1

        # Report progress periodically
        if progress_callback and progress.dirs_scanned % 10 == 0:
            progress_callback(progress)

        subdirs: List[Path] = []

        try:
            for entry in self.fs.scandir(dir_path):
                if self._cancelled:
                    return

                # Calculate relative path from root
                full_path = Path(entry.path)
                try:
                    rel_path = full_path.relative_to(root_path)
                except ValueError:
                    rel_path = full_path

                parent_path = str(rel_path.parent) if rel_path.parent != Path(".") else ""

                # Create file record
                file_record = FileRecord(
                    file_id=0,  # Will be set by upsert
                    root_id=root_id,
                    path=str(rel_path),
                    parent_path=parent_path,
                    name=entry.name,
                    ext=Path(entry.name).suffix.lower().lstrip("."),
                    is_dir=entry.is_dir,
                    size_bytes=entry.size_bytes,
                    mtime=entry.mtime,
                    ctime=entry.ctime,
                    category=FileCategory.from_extension(Path(entry.name).suffix),
                    status=IndexStatus.INVENTORY_OK,
                    last_indexed_at=datetime.now(),
                )

                # Save to database
                self.db.upsert_file(file_record)
                progress.files_found += 1

                # Queue subdirectories for recursive crawl
                if entry.is_dir:
                    subdirs.append(full_path)

        except PermissionError as e:
            progress.errors += 1
        except OSError as e:
            progress.errors += 1

        # Recurse into subdirectories
        for subdir in subdirs:
            self._crawl_directory(
                root_id=root_id,
                root_path=root_path,
                dir_path=subdir,
                progress=progress,
                progress_callback=progress_callback,
                current_depth=current_depth + 1,
                max_depth=max_depth,
            )

    def cancel(self):
        """Cancel an in-progress crawl."""
        self._cancelled = True

    def get_roots(self) -> List[IndexRoot]:
        """Get all indexed roots."""
        return self.db.list_roots()

    def remove_root(self, root_id: int) -> bool:
        """Remove a root and all its files from the index."""
        return self.db.remove_root(root_id)
