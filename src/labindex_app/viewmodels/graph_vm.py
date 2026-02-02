"""
Graph ViewModel for the graph visualization.

Manages:
- File index data
- Navigation state (current path, breadcrumb, back history)
- Display settings (layout, colors, visibility)
- Highlighted paths (search results)
- Relationship edges (links between files)

The GraphCanvas widget receives state from this ViewModel and focuses
purely on rendering.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Any
from pathlib import Path
from PyQt6.QtCore import pyqtSignal

from .base import BaseViewModel
from labindex_core.services.crawler import CrawlerService
from labindex_core.services.search import SearchService
from labindex_core.ports.db_port import DBPort


@dataclass
class GraphSettings:
    """Graph display settings."""
    layout_type: str = "Tree"  # Tree, Radial, Balloon, Spring, Circular
    tree_direction: str = "Top-Down"  # Top-Down, Left-Right, Bottom-Up, Right-Left
    color_mode: str = "Uniform"  # Uniform, Category, Depth, Size
    show_files: bool = True
    show_labels: bool = True
    show_links: bool = False
    link_threshold: float = 0.70

    # Layout tuning
    node_spacing: int = 60
    layer_spacing: int = 80
    node_size: int = 12
    font_size: int = 9


class GraphVM(BaseViewModel):
    """
    ViewModel for graph visualization.

    Signals:
        file_index_changed: Emitted when file data changes
        settings_changed: Emitted when display settings change
        navigation_changed: Emitted when navigation state changes
        highlights_changed: Emitted when highlighted paths change
        links_changed: Emitted when relationship edges change

    State:
        file_index: Dict with 'root', 'total_files', 'files' list
        settings: GraphSettings for display configuration
        current_path: Current navigation path (None = root)
        breadcrumb: List of path components for navigation
        can_go_back: Whether back navigation is available
        highlighted_paths: Set of paths to highlight (search results)
        relationship_edges: List of link dicts
    """

    # Signals
    file_index_changed = pyqtSignal()
    settings_changed = pyqtSignal()
    navigation_changed = pyqtSignal()
    highlights_changed = pyqtSignal()
    links_changed = pyqtSignal()

    def __init__(
        self,
        crawler: CrawlerService,
        search: SearchService,
        db: DBPort,
    ):
        """
        Initialize the ViewModel.

        Args:
            crawler: Service for getting roots
            search: Service for listing files
            db: Database for getting edges
        """
        super().__init__()

        self._crawler = crawler
        self._search = search
        self._db = db

        # State
        self._file_index: Optional[Dict[str, Any]] = None
        self._full_file_index: Optional[Dict[str, Any]] = None  # Original, unfiltered
        self._settings = GraphSettings()
        self._current_path: Optional[str] = None
        self._navigation_history: List[str] = []
        self._highlighted_paths: Set[str] = set()
        self._relationship_edges: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def file_index(self) -> Optional[Dict[str, Any]]:
        """Get the current file index for display."""
        return self._file_index

    @property
    def settings(self) -> GraphSettings:
        """Get current display settings."""
        return self._settings

    @property
    def current_path(self) -> Optional[str]:
        """Get current navigation path (None = root)."""
        return self._current_path

    @property
    def breadcrumb(self) -> List[str]:
        """Get breadcrumb path for navigation display."""
        if self._current_path is None:
            return []
        return list(Path(self._current_path).parts)

    @property
    def can_go_back(self) -> bool:
        """Check if back navigation is available."""
        return len(self._navigation_history) > 0

    @property
    def highlighted_paths(self) -> Set[str]:
        """Get paths to highlight (search results)."""
        return self._highlighted_paths.copy()

    @property
    def relationship_edges(self) -> List[Dict[str, Any]]:
        """Get relationship edges for display."""
        return self._relationship_edges.copy()

    # -------------------------------------------------------------------------
    # Data Loading Commands
    # -------------------------------------------------------------------------

    def load_root(self, root_id: Optional[int] = None) -> bool:
        """
        Load file data for a root.

        Args:
            root_id: ID of root to load (uses first root if None)

        Returns:
            True if data was loaded
        """
        roots = self._crawler.get_roots()
        if not roots:
            return False

        if root_id is None:
            root_id = roots[0].root_id

        root = self._db.get_root(root_id)
        if not root:
            return False

        # Get files
        files = self._search.list_files(root_id, limit=5000)

        # Build file index dict for GraphCanvas
        file_index = {
            'root': root.root_path,
            'total_files': len(files),
            'files': []
        }

        for f in files:
            file_info = {
                'name': f.name,
                'path': f.path,
                'full_path': str(Path(root.root_path) / f.path),
                'parent': f.parent_path,
                'is_dir': f.is_dir,
                'category': f.category.value,
                'size_kb': f.size_bytes // 1024,
            }
            file_index['files'].append(file_info)

        self._full_file_index = file_index
        self._file_index = file_index
        self._current_path = None
        self._navigation_history = []

        self.file_index_changed.emit()
        self.navigation_changed.emit()

        # Load relationship edges if show_links is enabled
        if self._settings.show_links:
            self._load_relationship_edges(root_id)

        return True

    def _load_relationship_edges(self, root_id: int) -> None:
        """Load relationship edges from database."""
        files = self._db.list_files(root_id, limit=10000)

        # Build edges list
        edges = []
        for f in files:
            for edge in self._db.get_edges_from(f.file_id):
                dst_file = self._db.get_file(edge.dst_file_id)
                if dst_file and edge.confidence >= self._settings.link_threshold:
                    edges.append({
                        'src_path': f.path,
                        'dst_path': dst_file.path,
                        'relation_type': edge.relation_type.value,
                        'confidence': edge.confidence,
                        'evidence': edge.evidence,
                    })

        self._relationship_edges = edges
        self.links_changed.emit()

    # -------------------------------------------------------------------------
    # Navigation Commands
    # -------------------------------------------------------------------------

    def drill_down(self, path: str) -> None:
        """
        Navigate into a folder.

        Args:
            path: Path to drill into
        """
        if self._current_path is not None:
            self._navigation_history.append(self._current_path)
        self._current_path = path

        # Filter file index to only show children of this path
        self._update_filtered_index()
        self.navigation_changed.emit()

    def navigate_back(self) -> bool:
        """
        Navigate back to previous folder.

        Returns:
            True if navigation occurred
        """
        if not self._navigation_history:
            return False

        self._current_path = self._navigation_history.pop()
        self._update_filtered_index()
        self.navigation_changed.emit()
        return True

    def navigate_home(self) -> None:
        """Navigate to root."""
        self._current_path = None
        self._navigation_history = []
        self._file_index = self._full_file_index
        self.file_index_changed.emit()
        self.navigation_changed.emit()

    def _update_filtered_index(self) -> None:
        """Update file index to show only current folder contents."""
        if self._full_file_index is None:
            return

        if self._current_path is None:
            self._file_index = self._full_file_index
        else:
            # Filter files to those in current path
            filtered_files = [
                f for f in self._full_file_index['files']
                if f['path'].startswith(self._current_path + '/') or
                   f['path'] == self._current_path
            ]

            self._file_index = {
                'root': self._current_path,
                'total_files': len(filtered_files),
                'files': filtered_files,
            }

        self.file_index_changed.emit()

    # -------------------------------------------------------------------------
    # Settings Commands
    # -------------------------------------------------------------------------

    def set_layout(self, layout_type: str) -> None:
        """Set the graph layout type."""
        if self._settings.layout_type != layout_type:
            self._settings.layout_type = layout_type
            self.settings_changed.emit()

    def set_tree_direction(self, direction: str) -> None:
        """Set the tree direction."""
        if self._settings.tree_direction != direction:
            self._settings.tree_direction = direction
            self.settings_changed.emit()

    def set_color_mode(self, mode: str) -> None:
        """Set the color mode."""
        if self._settings.color_mode != mode:
            self._settings.color_mode = mode
            self.settings_changed.emit()

    def set_show_files(self, show: bool) -> None:
        """Set whether to show file nodes."""
        if self._settings.show_files != show:
            self._settings.show_files = show
            self.settings_changed.emit()

    def set_show_labels(self, show: bool) -> None:
        """Set whether to show labels."""
        if self._settings.show_labels != show:
            self._settings.show_labels = show
            self.settings_changed.emit()

    def set_show_links(self, show: bool, root_id: Optional[int] = None) -> None:
        """
        Set whether to show relationship links.

        Args:
            show: Whether to show links
            root_id: Root to load links for (if show=True)
        """
        if self._settings.show_links != show:
            self._settings.show_links = show
            if show and root_id is not None:
                self._load_relationship_edges(root_id)
            elif not show:
                self._relationship_edges = []
                self.links_changed.emit()
            self.settings_changed.emit()

    def set_link_threshold(self, threshold: float, root_id: Optional[int] = None) -> None:
        """
        Set the minimum confidence for showing links.

        Args:
            threshold: Minimum confidence (0.0-1.0)
            root_id: Root to reload links for
        """
        if self._settings.link_threshold != threshold:
            self._settings.link_threshold = threshold
            if self._settings.show_links and root_id is not None:
                self._load_relationship_edges(root_id)
            self.settings_changed.emit()

    def update_layout_params(
        self,
        node_spacing: Optional[int] = None,
        layer_spacing: Optional[int] = None,
        node_size: Optional[int] = None,
        font_size: Optional[int] = None,
    ) -> None:
        """Update layout tuning parameters."""
        changed = False
        if node_spacing is not None and self._settings.node_spacing != node_spacing:
            self._settings.node_spacing = node_spacing
            changed = True
        if layer_spacing is not None and self._settings.layer_spacing != layer_spacing:
            self._settings.layer_spacing = layer_spacing
            changed = True
        if node_size is not None and self._settings.node_size != node_size:
            self._settings.node_size = node_size
            changed = True
        if font_size is not None and self._settings.font_size != font_size:
            self._settings.font_size = font_size
            changed = True

        if changed:
            self.settings_changed.emit()

    # -------------------------------------------------------------------------
    # Highlight Commands
    # -------------------------------------------------------------------------

    def highlight_search_results(self, paths: List[str]) -> None:
        """
        Highlight paths from search results.

        Args:
            paths: List of paths to highlight
        """
        self._highlighted_paths = set(paths)
        self.highlights_changed.emit()

    def clear_highlights(self) -> None:
        """Clear all highlights."""
        if self._highlighted_paths:
            self._highlighted_paths = set()
            self.highlights_changed.emit()
