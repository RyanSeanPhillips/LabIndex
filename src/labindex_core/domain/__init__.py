"""
Domain models for LabIndex.

Contains DTOs, enums, and data structures used throughout the application.
"""

from .models import (
    FileRecord,
    ContentRecord,
    Edge,
    IndexRoot,
    CrawlJob,
    SearchResult,
)
from .enums import (
    FileCategory,
    IndexStatus,
    EdgeType,
    JobStatus,
)

__all__ = [
    # Models
    "FileRecord",
    "ContentRecord",
    "Edge",
    "IndexRoot",
    "CrawlJob",
    "SearchResult",
    # Enums
    "FileCategory",
    "IndexStatus",
    "EdgeType",
    "JobStatus",
]
