"""
Search Service - Query the file index.

Provides filename search, FTS5 full-text search, and graph traversal.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path

from ..ports.db_port import DBPort
from ..domain.models import FileRecord, SearchResult, Edge
from ..domain.enums import EdgeType


class SearchService:
    """
    Service for searching the file index.

    Supports:
    - Filename search (LIKE queries)
    - Full-text search (FTS5)
    - Graph traversal (find related files)
    """

    def __init__(self, db: DBPort):
        """
        Initialize the search service.

        Args:
            db: Database adapter
        """
        self.db = db

    def search(
        self,
        query: str,
        root_id: Optional[int] = None,
        search_type: str = "auto",
        limit: int = 100,
    ) -> List[SearchResult]:
        """
        Search for files.

        Args:
            query: Search query
            root_id: Limit to specific root (None = all roots)
            search_type: "filename", "fts", or "auto" (tries both)
            limit: Maximum results

        Returns:
            List of SearchResult objects
        """
        if not query.strip():
            return []

        if search_type == "filename":
            return self.db.search_filename(query, root_id, limit)
        elif search_type == "fts":
            return self.db.search_fts(query, root_id, limit)
        else:  # auto
            # Try FTS first, fall back to filename
            results = self.db.search_fts(query, root_id, limit)
            if not results:
                results = self.db.search_filename(query, root_id, limit)
            return results

    def search_filename(
        self,
        query: str,
        root_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[SearchResult]:
        """Search by filename pattern."""
        return self.db.search_filename(query, root_id, limit)

    def search_fts(
        self,
        query: str,
        root_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[SearchResult]:
        """Full-text search on content."""
        return self.db.search_fts(query, root_id, limit)

    def get_file(self, file_id: int) -> Optional[FileRecord]:
        """Get a file by ID."""
        return self.db.get_file(file_id)

    def get_file_by_path(self, root_id: int, path: str) -> Optional[FileRecord]:
        """Get a file by its path within a root."""
        return self.db.get_file_by_path(root_id, path)

    def list_files(
        self,
        root_id: int,
        parent_path: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 1000,
    ) -> List[FileRecord]:
        """List files with optional filters."""
        return self.db.list_files(root_id, parent_path, category, limit)

    # === Graph Navigation ===

    def get_related(
        self,
        file_id: int,
        relation_types: Optional[List[str]] = None,
        direction: str = "both",
    ) -> List[tuple[Edge, FileRecord]]:
        """
        Get files related to a given file.

        Args:
            file_id: Source file ID
            relation_types: Filter by relation types (None = all)
            direction: "from", "to", or "both"

        Returns:
            List of (Edge, FileRecord) tuples
        """
        results = []

        if direction in ("from", "both"):
            for rel_type in (relation_types or [None]):
                edges = self.db.get_edges_from(file_id, rel_type)
                for edge in edges:
                    file = self.db.get_file(edge.dst_file_id)
                    if file:
                        results.append((edge, file))

        if direction in ("to", "both"):
            for rel_type in (relation_types or [None]):
                edges = self.db.get_edges_to(file_id, rel_type)
                for edge in edges:
                    file = self.db.get_file(edge.src_file_id)
                    if file:
                        results.append((edge, file))

        return results

    def find_notes_for_file(self, file_id: int) -> List[FileRecord]:
        """
        Find notes/documentation for a data file.

        Looks for edges of type NOTES_FOR, SURGERY_NOTES, etc.
        """
        note_types = [EdgeType.NOTES_FOR.value, EdgeType.SURGERY_NOTES.value]
        notes = []

        for edge_type in note_types:
            edges = self.db.get_edges_to(file_id, edge_type)
            for edge in edges:
                file = self.db.get_file(edge.src_file_id)
                if file:
                    notes.append(file)

        return notes

    def find_data_for_notes(self, file_id: int) -> List[FileRecord]:
        """
        Find data files that a notes document describes.

        Looks for edges of type NOTES_FOR, DESCRIBES, etc.
        """
        data_types = [EdgeType.NOTES_FOR.value, EdgeType.ANALYSIS_OF.value]
        data_files = []

        for edge_type in data_types:
            edges = self.db.get_edges_from(file_id, edge_type)
            for edge in edges:
                file = self.db.get_file(edge.dst_file_id)
                if file:
                    data_files.append(file)

        return data_files

    # === Statistics ===

    def get_stats(self, root_id: Optional[int] = None) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "file_count": self.db.get_file_count(root_id),
            "indexed_count": self.db.get_indexed_count(root_id),
            "edge_count": self.db.count_edges(root_id),
            "roots": len(self.db.list_roots()),
        }
