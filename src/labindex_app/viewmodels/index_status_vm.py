"""
IndexStatus ViewModel for the Index & Build tab.

Manages:
- Root folder list
- Crawl/extract/link operations
- Progress tracking
- Index statistics
"""

from dataclasses import dataclass
from typing import Optional, List
from PyQt6.QtCore import pyqtSignal

from .base import BaseViewModel
from labindex_core.services.crawler import CrawlerService
from labindex_core.services.extractor import ExtractorService
from labindex_core.services.linker import LinkerService
from labindex_core.services.search import SearchService
from labindex_core.domain.models import IndexRoot


@dataclass
class IndexStats:
    """Statistics about the current index state."""
    file_count: int = 0
    roots_count: int = 0
    indexed_count: int = 0
    links_count: int = 0


class IndexStatusVM(BaseViewModel):
    """
    ViewModel for Index & Build tab.

    Signals:
        roots_changed: Emitted when the roots list changes
        progress_changed(int, str): Emitted during operations (percent, message)
        operation_started(str): Emitted when an operation starts (operation_type)
        operation_finished(bool, str): Emitted when operation completes (success, message)
        stats_changed: Emitted when index statistics change
        selected_root_changed(int): Emitted when selected root changes (root_id or -1)

    State:
        roots: List of indexed root folders
        selected_root_id: Currently selected root (-1 if none)
        operation_in_progress: Whether an operation is running
        operation_type: Current operation type ("crawl", "extract", "link", "")
        progress_percent: Current progress (0-100)
        progress_message: Current status message
        stats: Current index statistics
    """

    # Signals
    roots_changed = pyqtSignal()
    progress_changed = pyqtSignal(int, str)  # percent, message
    operation_started = pyqtSignal(str)  # operation_type
    operation_finished = pyqtSignal(bool, str)  # success, message
    stats_changed = pyqtSignal()
    selected_root_changed = pyqtSignal(int)  # root_id or -1

    def __init__(
        self,
        crawler: CrawlerService,
        extractor: ExtractorService,
        linker: LinkerService,
        search: SearchService,
    ):
        """
        Initialize the ViewModel.

        Args:
            crawler: Service for crawling directories
            extractor: Service for extracting content
            linker: Service for finding links
            search: Service for getting statistics
        """
        super().__init__()

        self._crawler = crawler
        self._extractor = extractor
        self._linker = linker
        self._search = search

        # State
        self._roots: List[IndexRoot] = []
        self._selected_root_id: int = -1
        self._operation_in_progress: bool = False
        self._operation_type: str = ""
        self._progress_percent: int = 0
        self._progress_message: str = "Ready to scan"
        self._stats = IndexStats()

        # Worker thread reference
        self._current_worker = None

        # Load initial data
        self._refresh_roots()
        self._refresh_stats()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def roots(self) -> List[IndexRoot]:
        """Get the list of indexed roots."""
        return self._roots.copy()

    @property
    def selected_root_id(self) -> int:
        """Get the currently selected root ID (-1 if none)."""
        return self._selected_root_id

    @property
    def selected_root(self) -> Optional[IndexRoot]:
        """Get the currently selected root, or None."""
        for root in self._roots:
            if root.root_id == self._selected_root_id:
                return root
        return None

    @property
    def operation_in_progress(self) -> bool:
        """Check if an operation is in progress."""
        return self._operation_in_progress

    @property
    def operation_type(self) -> str:
        """Get the current operation type."""
        return self._operation_type

    @property
    def progress_percent(self) -> int:
        """Get current progress percentage (0-100)."""
        return self._progress_percent

    @property
    def progress_message(self) -> str:
        """Get current status message."""
        return self._progress_message

    @property
    def stats(self) -> IndexStats:
        """Get current index statistics."""
        return self._stats

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def select_root(self, root_id: int) -> None:
        """
        Select a root folder.

        Args:
            root_id: ID of root to select, or -1 to deselect
        """
        if self._selected_root_id != root_id:
            self._selected_root_id = root_id
            self.selected_root_changed.emit(root_id)

    def add_root(self, folder_path: str) -> Optional[IndexRoot]:
        """
        Add a new root folder.

        Args:
            folder_path: Path to the folder to add

        Returns:
            The created IndexRoot, or None if failed
        """
        try:
            root = self._crawler.add_root(folder_path)
            self._refresh_roots()
            self._refresh_stats()
            return root
        except Exception as e:
            # Let caller handle the error
            raise

    def remove_root(self, root_id: int) -> bool:
        """
        Remove a root from the index.

        Args:
            root_id: ID of the root to remove

        Returns:
            True if removed successfully
        """
        result = self._crawler.remove_root(root_id)
        if result:
            if self._selected_root_id == root_id:
                self._selected_root_id = -1
                self.selected_root_changed.emit(-1)
            self._refresh_roots()
            self._refresh_stats()
        return result

    def start_crawl(self, root_id: Optional[int] = None) -> bool:
        """
        Start crawling a root folder.

        Args:
            root_id: ID of root to crawl (uses selected if None)

        Returns:
            True if crawl was started
        """
        if self._operation_in_progress:
            return False

        target_id = root_id if root_id is not None else self._selected_root_id
        if target_id < 0:
            return False

        from ..workers import CrawlWorker

        self._operation_in_progress = True
        self._operation_type = "crawl"
        self._progress_percent = 0
        self._progress_message = "Starting crawl..."
        self.operation_started.emit("crawl")

        self._current_worker = CrawlWorker(self._crawler, target_id)
        self._current_worker.progress.connect(self._on_crawl_progress)
        self._current_worker.finished.connect(self._on_crawl_finished)
        self._current_worker.start()

        return True

    def stop_crawl(self) -> None:
        """Stop the current crawl operation."""
        if self._operation_type == "crawl":
            self._crawler.cancel()
            self._progress_message = "Stopping..."
            self.progress_changed.emit(self._progress_percent, self._progress_message)

    def start_extraction(self, root_id: Optional[int] = None) -> bool:
        """
        Start content extraction for a root.

        Args:
            root_id: ID of root to extract (uses first root if None)

        Returns:
            True if extraction was started
        """
        if self._operation_in_progress:
            return False

        # Use first root if none specified
        if root_id is None:
            if self._roots:
                root_id = self._roots[0].root_id
            else:
                return False

        from ..workers import ExtractWorker

        self._operation_in_progress = True
        self._operation_type = "extract"
        self._progress_percent = 0
        self._progress_message = "Starting extraction..."
        self.operation_started.emit("extract")

        self._current_worker = ExtractWorker(self._extractor, root_id)
        self._current_worker.progress.connect(self._on_extract_progress)
        self._current_worker.finished.connect(self._on_extract_finished)
        self._current_worker.start()

        return True

    def start_linking(self, root_id: Optional[int] = None) -> bool:
        """
        Start auto-linking for a root.

        Args:
            root_id: ID of root to link (uses first root if None)

        Returns:
            True if linking was started
        """
        if self._operation_in_progress:
            return False

        # Use first root if none specified
        if root_id is None:
            if self._roots:
                root_id = self._roots[0].root_id
            else:
                return False

        from ..workers import LinkWorker

        self._operation_in_progress = True
        self._operation_type = "link"
        self._progress_percent = 0
        self._progress_message = "Finding relationships..."
        self.operation_started.emit("link")

        self._current_worker = LinkWorker(self._linker, root_id)
        self._current_worker.progress.connect(self._on_link_progress)
        self._current_worker.finished.connect(self._on_link_finished)
        self._current_worker.start()

        return True

    def clear_links(self, root_id: Optional[int] = None) -> int:
        """
        Clear all auto-generated links for a root.

        Args:
            root_id: ID of root to clear links from (clears all if None)

        Returns:
            Number of links removed
        """
        total_removed = 0

        if root_id is not None:
            total_removed = self._linker.clear_links(root_id)
        else:
            for root in self._roots:
                total_removed += self._linker.clear_links(root.root_id)

        self._progress_message = f"Cleared {total_removed:,} links"
        self.progress_changed.emit(0, self._progress_message)
        self._refresh_stats()

        return total_removed

    def refresh(self) -> None:
        """Refresh roots and stats from the database."""
        self._refresh_roots()
        self._refresh_stats()

    # -------------------------------------------------------------------------
    # Internal: Progress handlers
    # -------------------------------------------------------------------------

    def _on_crawl_progress(self, dirs: int, files: int, current: str):
        """Handle crawl progress update."""
        self._progress_message = f"Scanning: {current}"
        # We don't know total, so just report files found
        self._stats.file_count = files
        self.progress_changed.emit(self._progress_percent, self._progress_message)
        self.stats_changed.emit()

    def _on_crawl_finished(self, success: bool, message: str):
        """Handle crawl completion."""
        self._operation_in_progress = False
        self._operation_type = ""
        self._progress_message = message
        self._progress_percent = 100 if success else 0
        self._current_worker = None

        self._refresh_stats()
        self.operation_finished.emit(success, message)

    def _on_extract_progress(self, processed: int, total: int, current: str):
        """Handle extraction progress update."""
        self._progress_message = f"Extracting: {current}"
        if total > 0:
            self._progress_percent = int(processed * 100 / total)
        self.progress_changed.emit(self._progress_percent, self._progress_message)

    def _on_extract_finished(self, success: bool, message: str):
        """Handle extraction completion."""
        self._operation_in_progress = False
        self._operation_type = ""
        self._progress_message = message
        self._progress_percent = 100 if success else 0
        self._current_worker = None

        self._refresh_stats()
        self.operation_finished.emit(success, message)

    def _on_link_progress(self, message: str):
        """Handle linking progress update."""
        self._progress_message = message
        self.progress_changed.emit(self._progress_percent, self._progress_message)

    def _on_link_finished(self, success: bool, message: str):
        """Handle linking completion."""
        self._operation_in_progress = False
        self._operation_type = ""
        self._progress_message = message
        self._progress_percent = 0
        self._current_worker = None

        self._refresh_stats()
        self.operation_finished.emit(success, message)

    # -------------------------------------------------------------------------
    # Internal: Data refresh
    # -------------------------------------------------------------------------

    def _refresh_roots(self) -> None:
        """Refresh the roots list from the database."""
        self._roots = self._crawler.get_roots()
        self.roots_changed.emit()

    def _refresh_stats(self) -> None:
        """Refresh statistics from the database."""
        stats = self._search.get_stats()
        self._stats = IndexStats(
            file_count=stats.get("file_count", 0),
            roots_count=stats.get("roots", 0),
            indexed_count=stats.get("indexed_count", 0),
            links_count=stats.get("edge_count", 0),
        )
        self.stats_changed.emit()
