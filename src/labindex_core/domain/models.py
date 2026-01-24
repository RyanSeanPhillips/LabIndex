"""
Domain models (DTOs) for LabIndex.

These are pure data classes with no database or filesystem dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from .enums import FileCategory, IndexStatus, EdgeType, JobStatus


@dataclass
class IndexRoot:
    """A root folder that has been added for indexing."""
    root_id: int
    root_path: str
    label: str
    scan_config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_scan_at: Optional[datetime] = None

    @property
    def path(self) -> Path:
        return Path(self.root_path)


@dataclass
class FileRecord:
    """A file or directory in the index."""
    file_id: int
    root_id: int
    path: str                    # Full path relative to root
    parent_path: str             # Parent directory path
    name: str                    # Filename with extension
    ext: str                     # Extension (lowercase, no dot)
    is_dir: bool
    size_bytes: int
    mtime: datetime              # Last modified time
    ctime: datetime              # Creation time
    category: FileCategory
    status: IndexStatus = IndexStatus.PENDING
    error_msg: Optional[str] = None
    last_indexed_at: Optional[datetime] = None

    @property
    def full_path(self) -> Path:
        return Path(self.path)

    @property
    def stem(self) -> str:
        """Filename without extension."""
        return Path(self.name).stem


@dataclass
class ContentRecord:
    """Extracted content for a file (Tier 1/2/3)."""
    file_id: int
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)  # {type: [values]}
    content_excerpt: Optional[str] = None  # First N chars/lines
    extraction_version: str = "1.0"
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class Edge:
    """A relationship between two files."""
    edge_id: int
    src_file_id: int
    dst_file_id: int
    relation_type: EdgeType
    confidence: float = 1.0      # 0.0 to 1.0
    evidence: Optional[str] = None  # Snippet/reason for the link
    evidence_file_id: Optional[int] = None  # Where evidence was found
    created_by: str = "rule"     # "rule", "llm", "user"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CrawlJob:
    """A job to crawl a directory."""
    job_id: int
    root_id: int
    dir_path: str
    status: JobStatus = JobStatus.PENDING
    priority: int = 0            # Higher = more important
    attempts: int = 0
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_msg: Optional[str] = None


@dataclass
class SearchResult:
    """A search result with ranking info."""
    file_id: int
    file_record: FileRecord
    score: float                 # Relevance score
    match_type: str              # "fts", "filename", "fuzzy", "edge"
    snippet: Optional[str] = None  # Matching text snippet
    highlight_positions: List[tuple] = field(default_factory=list)  # (start, end) pairs

    @property
    def path(self) -> str:
        return self.file_record.path

    @property
    def name(self) -> str:
        return self.file_record.name
