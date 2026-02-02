"""
Search ViewModel for the Search & Explore tab.

Manages:
- Search query and results
- Result selection
- Results with pre-joined metadata (N+1 prevention)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import pyqtSignal

from .base import BaseViewModel
from labindex_core.services.search import SearchService


@dataclass
class SearchResultRow:
    """Pre-formatted search result row for display."""
    file_id: int
    name: str
    path: str
    category: str
    size_bytes: int
    score: float
    content_excerpt: str  # First 60 chars
    full_excerpt: Optional[str]  # Full excerpt for tooltip
    link_count: int
    link_summaries: List[Dict[str, Any]]  # First 6 related files

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SearchResultRow":
        """Create from search_with_metadata dict."""
        return cls(
            file_id=d["file_id"],
            name=d["name"],
            path=d["path"],
            category=d["category"],
            size_bytes=d["size_bytes"],
            score=d["score"],
            content_excerpt=d["content_excerpt"],
            full_excerpt=d.get("full_excerpt"),
            link_count=d["link_count"],
            link_summaries=d["link_summaries"],
        )

    def format_links_tooltip(self) -> str:
        """Format link summaries for tooltip display."""
        if not self.link_summaries:
            return "No links"

        lines = []
        for link in self.link_summaries:
            arrow = "→" if link["direction"] == "to" else "←"
            lines.append(
                f"{arrow} {link['name']} ({link['type']}, {link['confidence']:.0%})"
            )

        if self.link_count > 6:
            lines.append(f"... and {self.link_count - 6} more")

        return "\n".join(lines)


class SearchVM(BaseViewModel):
    """
    ViewModel for search functionality.

    Uses search_with_metadata() to avoid N+1 queries when populating
    the results table.

    Signals:
        results_changed: Emitted when search results change
        selection_changed(int): Emitted when selected result changes (file_id or -1)
        search_started: Emitted when search begins
        search_finished: Emitted when search completes

    State:
        query: Current search query
        search_in_progress: Whether search is running
        results: List of SearchResultRow (pre-joined data)
        selected_file_id: Currently selected file (-1 if none)
    """

    # Signals
    results_changed = pyqtSignal()
    selection_changed = pyqtSignal(int)  # file_id or -1
    search_started = pyqtSignal()
    search_finished = pyqtSignal()

    def __init__(self, search_service: SearchService):
        """
        Initialize the ViewModel.

        Args:
            search_service: Service for search operations
        """
        super().__init__()

        self._search = search_service

        # State
        self._query: str = ""
        self._search_in_progress: bool = False
        self._results: List[SearchResultRow] = []
        self._selected_file_id: int = -1

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def query(self) -> str:
        """Get the current search query."""
        return self._query

    @property
    def search_in_progress(self) -> bool:
        """Check if search is in progress."""
        return self._search_in_progress

    @property
    def results(self) -> List[SearchResultRow]:
        """Get the current search results."""
        return self._results.copy()

    @property
    def result_count(self) -> int:
        """Get the number of results."""
        return len(self._results)

    @property
    def selected_file_id(self) -> int:
        """Get the selected file ID (-1 if none)."""
        return self._selected_file_id

    @property
    def selected_result(self) -> Optional[SearchResultRow]:
        """Get the selected result, or None."""
        for result in self._results:
            if result.file_id == self._selected_file_id:
                return result
        return None

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def search(self, query: str, limit: int = 100) -> None:
        """
        Execute a search query.

        Uses search_with_metadata() to get all display data in batch,
        avoiding N+1 queries.

        Args:
            query: The search query
            limit: Maximum number of results
        """
        self._query = query.strip()

        if not self._query:
            self.clear_results()
            return

        self._search_in_progress = True
        self.search_started.emit()

        try:
            # Use batch method to avoid N+1 queries
            result_dicts = self._search.search_with_metadata(
                self._query,
                limit=limit
            )

            self._results = [
                SearchResultRow.from_dict(d) for d in result_dicts
            ]

            # Clear selection if no longer valid
            if self._selected_file_id != -1:
                if not any(r.file_id == self._selected_file_id for r in self._results):
                    self._selected_file_id = -1
                    self.selection_changed.emit(-1)

        finally:
            self._search_in_progress = False
            self.search_finished.emit()
            self.results_changed.emit()

    def clear_results(self) -> None:
        """Clear search results."""
        self._query = ""
        self._results = []
        self._selected_file_id = -1
        self.results_changed.emit()
        self.selection_changed.emit(-1)

    def select_result(self, file_id: int) -> None:
        """
        Select a result by file ID.

        Args:
            file_id: ID of file to select, or -1 to deselect
        """
        if self._selected_file_id != file_id:
            self._selected_file_id = file_id
            self.selection_changed.emit(file_id)

    def get_result_paths(self) -> List[str]:
        """Get paths of all results (for graph highlighting)."""
        return [r.path for r in self._results]
