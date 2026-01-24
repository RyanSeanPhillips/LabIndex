"""
Database port interface.

Defines the contract for database operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..domain.models import (
    FileRecord, ContentRecord, Edge, IndexRoot, CrawlJob, SearchResult
)
from ..domain.enums import IndexStatus, JobStatus


class DBPort(ABC):
    """
    Abstract interface for database operations.

    Implementations handle SQLite, FTS5, and job queue management.
    """

    # === Root Management ===

    @abstractmethod
    def add_root(self, path: str, label: str, config: Dict[str, Any] = None) -> IndexRoot:
        """Add a new root folder for indexing."""
        pass

    @abstractmethod
    def get_root(self, root_id: int) -> Optional[IndexRoot]:
        """Get a root by ID."""
        pass

    @abstractmethod
    def list_roots(self) -> List[IndexRoot]:
        """List all indexed roots."""
        pass

    @abstractmethod
    def remove_root(self, root_id: int) -> bool:
        """Remove a root and all its files from the index."""
        pass

    # === File Records ===

    @abstractmethod
    def upsert_file(self, file: FileRecord) -> FileRecord:
        """Insert or update a file record."""
        pass

    @abstractmethod
    def get_file(self, file_id: int) -> Optional[FileRecord]:
        """Get a file by ID."""
        pass

    @abstractmethod
    def get_file_by_path(self, root_id: int, path: str) -> Optional[FileRecord]:
        """Get a file by its path within a root."""
        pass

    @abstractmethod
    def list_files(self, root_id: int, parent_path: Optional[str] = None,
                   category: Optional[str] = None, limit: int = 1000) -> List[FileRecord]:
        """List files with optional filters."""
        pass

    @abstractmethod
    def update_file_status(self, file_id: int, status: IndexStatus,
                          error_msg: Optional[str] = None) -> bool:
        """Update a file's indexing status."""
        pass

    # === Content Records ===

    @abstractmethod
    def upsert_content(self, content: ContentRecord) -> ContentRecord:
        """Insert or update content for a file."""
        pass

    @abstractmethod
    def get_content(self, file_id: int) -> Optional[ContentRecord]:
        """Get content record for a file."""
        pass

    # === Edges ===

    @abstractmethod
    def add_edge(self, edge: Edge) -> Edge:
        """Add a relationship edge."""
        pass

    @abstractmethod
    def get_edges_from(self, file_id: int, relation_type: Optional[str] = None) -> List[Edge]:
        """Get edges originating from a file."""
        pass

    @abstractmethod
    def get_edges_to(self, file_id: int, relation_type: Optional[str] = None) -> List[Edge]:
        """Get edges pointing to a file."""
        pass

    # === Search ===

    @abstractmethod
    def search_filename(self, query: str, root_id: Optional[int] = None,
                       limit: int = 100) -> List[SearchResult]:
        """Search by filename (LIKE query)."""
        pass

    @abstractmethod
    def search_fts(self, query: str, root_id: Optional[int] = None,
                  limit: int = 100) -> List[SearchResult]:
        """Full-text search on content."""
        pass

    # === Jobs ===

    @abstractmethod
    def create_job(self, job: CrawlJob) -> CrawlJob:
        """Create a new crawl job."""
        pass

    @abstractmethod
    def claim_job(self, worker_id: str) -> Optional[CrawlJob]:
        """Claim the next available job for processing."""
        pass

    @abstractmethod
    def complete_job(self, job_id: int, status: JobStatus,
                    error_msg: Optional[str] = None) -> bool:
        """Mark a job as completed or failed."""
        pass

    @abstractmethod
    def get_job_stats(self) -> Dict[str, int]:
        """Get counts of jobs by status."""
        pass

    # === Maintenance ===

    @abstractmethod
    def vacuum(self) -> None:
        """Optimize database storage."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass
