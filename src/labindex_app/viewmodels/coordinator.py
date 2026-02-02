"""
App Coordinator for cross-ViewModel communication.

Handles:
- Search results → Graph highlights
- Crawl completion → Graph refresh
- File selection → Inspector update
- Tab changes → Data refresh
"""

from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from .index_status_vm import IndexStatusVM
from .search_vm import SearchVM
from .graph_vm import GraphVM
from .agent_vm import AgentVM
from .inspector_vm import InspectorVM
from .candidate_review_vm import CandidateReviewVM


class AppCoordinator(QObject):
    """
    Coordinates communication between ViewModels.

    This allows ViewModels to remain decoupled while still responding
    to changes in other ViewModels.

    Responsibilities:
    - When search completes: highlight results in graph
    - When crawl completes: refresh graph data
    - When file selected: load in inspector
    - When links change: refresh graph links
    """

    # Signal emitted when status bar should update
    status_message = pyqtSignal(str, int)  # message, timeout_ms

    def __init__(
        self,
        index_vm: IndexStatusVM,
        search_vm: SearchVM,
        graph_vm: GraphVM,
        agent_vm: AgentVM,
        inspector_vm: InspectorVM,
        review_vm: CandidateReviewVM,
    ):
        """
        Initialize the coordinator.

        Args:
            index_vm: Index & Build ViewModel
            search_vm: Search ViewModel
            graph_vm: Graph ViewModel
            agent_vm: Agent/Chat ViewModel
            inspector_vm: File Inspector ViewModel
            review_vm: Candidate Review ViewModel
        """
        super().__init__()

        self._index_vm = index_vm
        self._search_vm = search_vm
        self._graph_vm = graph_vm
        self._agent_vm = agent_vm
        self._inspector_vm = inspector_vm
        self._review_vm = review_vm

        self._root_path: Optional[str] = None

        # Wire up cross-VM connections
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect cross-ViewModel signals."""

        # Index tab: when crawl finishes, refresh graph
        self._index_vm.operation_finished.connect(self._on_index_operation_finished)
        self._index_vm.roots_changed.connect(self._on_roots_changed)
        self._index_vm.stats_changed.connect(self._on_stats_changed)

        # Search: when results change, highlight in graph
        self._search_vm.results_changed.connect(self._on_search_results_changed)
        self._search_vm.selection_changed.connect(self._on_search_selection_changed)

        # Graph: when navigation changes, update breadcrumb
        self._graph_vm.navigation_changed.connect(self._on_graph_navigation_changed)

    # -------------------------------------------------------------------------
    # Index Tab Handlers
    # -------------------------------------------------------------------------

    def _on_index_operation_finished(self, success: bool, message: str) -> None:
        """Handle index operation completion."""
        self.status_message.emit(message, 5000)

        if success:
            # Refresh graph after crawl/link operations
            roots = self._index_vm.roots
            if roots:
                self._root_path = roots[0].root_path
                self._graph_vm.load_root(roots[0].root_id)

            # Refresh review tab stats
            self._review_vm.refresh_candidates()

    def _on_roots_changed(self) -> None:
        """Handle roots list change."""
        roots = self._index_vm.roots
        if roots and self._root_path is None:
            # First root added - load graph
            self._root_path = roots[0].root_path
            self._graph_vm.load_root(roots[0].root_id)

    def _on_stats_changed(self) -> None:
        """Handle stats change (for status bar update)."""
        stats = self._index_vm.stats
        message = (
            f"Files: {stats.file_count:,} | "
            f"Indexed: {stats.indexed_count:,} | "
            f"Links: {stats.links_count:,}"
        )
        self.status_message.emit(message, 0)  # Persistent

    # -------------------------------------------------------------------------
    # Search Tab Handlers
    # -------------------------------------------------------------------------

    def _on_search_results_changed(self) -> None:
        """Handle search results change - highlight in graph."""
        paths = self._search_vm.get_result_paths()
        self._graph_vm.highlight_search_results(paths)

    def _on_search_selection_changed(self, file_id: int) -> None:
        """Handle search selection - load in inspector."""
        if file_id >= 0:
            self._inspector_vm.load_file(file_id, self._root_path)
        else:
            self._inspector_vm.clear()

    # -------------------------------------------------------------------------
    # Graph Handlers
    # -------------------------------------------------------------------------

    def _on_graph_navigation_changed(self) -> None:
        """Handle graph navigation change."""
        # Could be used to update a breadcrumb display
        pass

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def set_root_path(self, path: str) -> None:
        """Set the root path for file operations."""
        self._root_path = path

    def refresh_all(self) -> None:
        """Refresh all ViewModels from database."""
        self._index_vm.refresh()

        roots = self._index_vm.roots
        if roots:
            self._root_path = roots[0].root_path
            self._graph_vm.load_root(roots[0].root_id)

        self._review_vm.refresh_strategies()
        self._review_vm.refresh_candidates()

    def on_tab_changed(self, tab_index: int) -> None:
        """
        Handle tab change - refresh data as needed.

        Args:
            tab_index: Index of newly selected tab
        """
        if tab_index == 0:
            # Index & Build tab
            self._index_vm.refresh()
        elif tab_index == 1:
            # Search & Explore tab - graph already loaded
            pass
        elif tab_index == 2:
            # Link Review tab
            self._review_vm.refresh_strategies()
            self._review_vm.refresh_candidates()

    def load_file_in_inspector(self, file_id: int) -> None:
        """Load a file in the inspector panel."""
        self._inspector_vm.load_file(file_id, self._root_path)
