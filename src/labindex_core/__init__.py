"""
LabIndex Core - Headless library for lab drive indexing.

This module provides the core functionality for indexing lab drives,
searching files, and linking related content. It has no UI dependencies
and can be embedded in other applications.

Safety: All file operations are READ-ONLY by design.
"""

__version__ = "0.1.0"
__author__ = "PhysioMetrics Team"

# Lazy imports to avoid loading everything at once
def __getattr__(name):
    if name == "ReadOnlyFS":
        from .adapters.readonly_fs import ReadOnlyFS
        return ReadOnlyFS
    elif name == "SqliteDB":
        from .adapters.sqlite_db import SqliteDB
        return SqliteDB
    elif name == "CrawlerService":
        from .services.crawler import CrawlerService
        return CrawlerService
    elif name == "SearchService":
        from .services.search import SearchService
        return SearchService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "__version__",
    "ReadOnlyFS",
    "SqliteDB",
    "CrawlerService",
    "SearchService",
]
