"""
GraphScene - QGraphicsScene subclass for managing graph items.

Handles item management, selection, and provides efficient lookups.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from .items import FolderItem, FileItem, EdgeItem
from .style_manager import StyleManager, LODLevel


@dataclass
class FilterState:
    """Filter configuration for graph visualization."""
    enabled_categories: Set[str] = field(default_factory=set)  # Empty = show all
    fade_opacity: float = 0.2
    hide_non_matching: bool = False  # False = fade, True = hide
    branch_aware: bool = True  # Keep parent folders of matching files visible

    def is_active(self) -> bool:
        """Check if any filter is active."""
        return len(self.enabled_categories) > 0

    def matches_category(self, category: str) -> bool:
        """Check if a category matches the filter."""
        if not self.enabled_categories:
            return True  # No filter = everything matches
        return category in self.enabled_categories


@dataclass
class GraphNode:
    """Data for a node in the graph."""
    node_id: int
    name: str
    path: str
    is_dir: bool
    category: str
    depth: int
    parent_id: Optional[int]
    file_count: int = 0
    total_size_kb: int = 0

    # Position (set by layout)
    x: float = 0.0
    y: float = 0.0


class GraphScene(QGraphicsScene):
    """
    QGraphicsScene for managing the graph visualization.

    Responsibilities:
    - Manages FolderItem, FileItem, and EdgeItem instances
    - Provides efficient lookups by ID and path
    - Handles selection state
    - Coordinates with StyleManager for LOD updates
    """

    # Signals
    node_selected = pyqtSignal(int, str)   # node_id, path
    node_double_clicked = pyqtSignal(int, str)  # node_id, path (for drill-down)

    def __init__(self, style_manager: Optional[StyleManager] = None):
        super().__init__()

        self._style = style_manager or StyleManager()

        # Item lookups
        self._folder_items: Dict[int, FolderItem] = {}  # node_id -> FolderItem
        self._file_items: Dict[int, FileItem] = {}      # file_id -> FileItem
        self._edge_items: Dict[int, EdgeItem] = {}      # edge_id -> EdgeItem (relationship edges)
        self._tree_edge_items: List[EdgeItem] = []      # Tree structure edges (parent-child folders)
        self._file_edge_items: List[EdgeItem] = []      # Folder-to-file edges

        # Path lookups for quick access
        self._path_to_folder: Dict[str, FolderItem] = {}
        self._path_to_file: Dict[str, FileItem] = {}

        # Visibility flags
        self._show_tree_edges = True  # Tree edges visible by default

        # Filter state
        self._filter_state = FilterState()
        self._folder_has_matching_children: Dict[int, bool] = {}  # Cache for branch-aware filtering

        # Node data (for rebuilding after LOD change)
        self._nodes: Dict[int, GraphNode] = {}
        self._file_data: Dict[int, Dict[str, Any]] = {}
        self._edge_data: Dict[int, Dict[str, Any]] = {}

        # Parent-child relationships
        self._children: Dict[int, List[int]] = {}  # parent_id -> [child_ids]
        self._parent: Dict[int, int] = {}          # child_id -> parent_id

        # Root node
        self._root_id: Optional[int] = None
        self._root_path: str = ""

        # Selection state
        self._selected_node_id: Optional[int] = None

        # Set background
        self.setBackgroundBrush(QBrush(self._style.style.bg_color))

    @property
    def style_manager(self) -> StyleManager:
        return self._style

    @style_manager.setter
    def style_manager(self, value: StyleManager):
        self._style = value
        self.setBackgroundBrush(QBrush(self._style.style.bg_color))
        # Update all items
        for item in self._folder_items.values():
            item.set_style_manager(self._style)
        for item in self._file_items.values():
            item.set_style_manager(self._style)
        for item in self._edge_items.values():
            item.set_style_manager(self._style)

    # -------------------------------------------------------------------------
    # Building the Graph
    # -------------------------------------------------------------------------

    def clear_graph(self):
        """Clear all items and data."""
        self.clear()
        self._folder_items.clear()
        self._file_items.clear()
        self._edge_items.clear()
        self._tree_edge_items.clear()
        self._file_edge_items.clear()
        self._path_to_folder.clear()
        self._path_to_file.clear()
        self._nodes.clear()
        self._file_data.clear()
        self._edge_data.clear()
        self._children.clear()
        self._parent.clear()
        self._root_id = None
        self._selected_node_id = None

    def build_from_file_index(
        self,
        file_index: Dict[str, Any],
        positions: Optional[Dict[str, Tuple[float, float]]] = None,
    ):
        """
        Build graph from file index dict.

        Args:
            file_index: Dict with 'root', 'total_files', 'files' list
            positions: Optional pre-computed positions {path: (x, y)}
        """
        self.clear_graph()

        root_path = file_index.get('root', 'Root')
        self._root_path = root_path
        files = file_index.get('files', [])

        # First pass: build folder hierarchy
        folders: Dict[str, GraphNode] = {}  # path -> GraphNode
        folder_files: Dict[str, List[Dict]] = {}  # folder_path -> [file_dicts]
        folder_sizes: Dict[str, int] = {}  # folder_path -> total_size
        folder_counts: Dict[str, int] = {}  # folder_path -> file_count

        # Create root node
        from pathlib import Path
        root_name = Path(root_path).name or 'Root'
        root_node = GraphNode(
            node_id=0,
            name=root_name,
            path="",
            is_dir=True,
            category="folder",
            depth=0,
            parent_id=None,
        )
        folders[""] = root_node
        folder_files[""] = []
        folder_sizes[""] = 0
        folder_counts[""] = 0
        self._root_id = 0

        next_id = 1

        # Process all files
        for f in files:
            path = f.get('path', '')
            parts = Path(path).parts
            size_kb = f.get('size_kb', 0)
            category = f.get('category', 'other')
            is_dir = f.get('is_dir', False)

            if is_dir:
                # This is a folder
                folder_path = path
                if folder_path not in folders:
                    # Determine parent
                    parent_path = str(Path(folder_path).parent)
                    if parent_path == '.':
                        parent_path = ""

                    folders[folder_path] = GraphNode(
                        node_id=next_id,
                        name=parts[-1] if parts else path,
                        path=folder_path,
                        is_dir=True,
                        category="folder",
                        depth=len(parts),
                        parent_id=folders.get(parent_path, root_node).node_id if parent_path in folders else 0,
                    )
                    folder_files[folder_path] = []
                    folder_sizes[folder_path] = 0
                    folder_counts[folder_path] = 0
                    next_id += 1
            else:
                # This is a file
                # Ensure parent folders exist
                current_path = ""
                for i, part in enumerate(parts[:-1]):
                    current_path = '/'.join(parts[:i+1])
                    if current_path not in folders:
                        parent_path = '/'.join(parts[:i]) if i > 0 else ""
                        folders[current_path] = GraphNode(
                            node_id=next_id,
                            name=part,
                            path=current_path,
                            is_dir=True,
                            category="folder",
                            depth=i + 1,
                            parent_id=folders.get(parent_path, root_node).node_id,
                        )
                        folder_files[current_path] = []
                        folder_sizes[current_path] = 0
                        folder_counts[current_path] = 0
                        next_id += 1

                # Add file to its parent folder
                parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ""
                if parent_path not in folder_files:
                    folder_files[parent_path] = []
                folder_files[parent_path].append(f)

                # Update folder stats up the tree
                current = parent_path
                while current is not None:
                    folder_sizes[current] = folder_sizes.get(current, 0) + size_kb
                    folder_counts[current] = folder_counts.get(current, 0) + 1
                    if current == "":
                        break
                    current = '/'.join(Path(current).parts[:-1]) if '/' in current else ""

        # Update folder nodes with stats
        for path, node in folders.items():
            node.file_count = folder_counts.get(path, 0)
            node.total_size_kb = folder_sizes.get(path, 0)
            self._nodes[node.node_id] = node

        # Build parent-child relationships
        for path, node in folders.items():
            if node.parent_id is not None:
                if node.parent_id not in self._children:
                    self._children[node.parent_id] = []
                self._children[node.parent_id].append(node.node_id)
                self._parent[node.node_id] = node.parent_id

        # Store file data for later (LOD-dependent creation)
        file_id = 10000  # Start file IDs high to avoid collision with folder IDs
        for folder_path, files_list in folder_files.items():
            for f in files_list:
                self._file_data[file_id] = {
                    'file_id': file_id,
                    'name': f.get('name', ''),
                    'path': f.get('path', ''),
                    'category': f.get('category', 'other'),
                    'size_kb': f.get('size_kb', 0),
                    'parent_path': folder_path,
                }
                file_id += 1

        # Create folder items
        self._create_folder_items(positions)

        # Create tree edges (parent-child folder connections) - visible by default
        self._create_tree_edges()

        # Always create file items (visibility controlled by LOD)
        self._create_file_items(positions)

        # Create edges from folders to their files
        self._create_file_edges()

        # Apply initial LOD visibility
        show_files = self._style.should_show_files()
        show_file_labels = self._style.should_show_file_labels()
        show_folder_labels = self._style.should_show_folder_labels()

        for item in self._file_items.values():
            item.setVisible(show_files)
            item.show_label = show_file_labels

        for item in self._folder_items.values():
            item.show_label = show_folder_labels

    def _create_folder_items(
        self,
        positions: Optional[Dict[str, Tuple[float, float]]] = None,
    ):
        """Create FolderItem instances for all folders."""
        for node_id, node in self._nodes.items():
            item = FolderItem(
                node_id=node.node_id,
                name=node.name,
                path=node.path,
                category=node.category,
                depth=node.depth,
                file_count=node.file_count,
                total_size_kb=node.total_size_kb,
                is_root=(node.node_id == self._root_id),
                style_manager=self._style,
            )

            # Set position
            if positions and node.path in positions:
                x, y = positions[node.path]
            else:
                x, y = node.x, node.y
            item.setPos(x, y)

            self.addItem(item)
            self._folder_items[node_id] = item
            self._path_to_folder[node.path] = item

    def _create_tree_edges(self):
        """Create edges connecting parent folders to child folders."""
        from PyQt6.QtCore import QPointF

        self._tree_edge_items.clear()

        # Create an edge for each parent-child relationship
        for child_id, parent_id in self._parent.items():
            parent_item = self._folder_items.get(parent_id)
            child_item = self._folder_items.get(child_id)

            if parent_item and child_item:
                edge = EdgeItem(
                    edge_id=-1,  # Tree edges use -1 as they're not relationship edges
                    src_pos=parent_item.pos(),
                    dst_pos=child_item.pos(),
                    relation_type="tree",  # Special type for tree edges
                    confidence=1.0,
                    evidence=None,
                    style_manager=self._style,
                )
                edge.setVisible(self._show_tree_edges)
                self.addItem(edge)
                self._tree_edge_items.append(edge)

    def set_show_tree_edges(self, show: bool):
        """Toggle visibility of tree structure edges."""
        self._show_tree_edges = show
        for edge in self._tree_edge_items:
            edge.setVisible(show)

    def update_tree_edge_positions(self):
        """Update tree edge positions to match current folder positions."""
        idx = 0
        for child_id, parent_id in self._parent.items():
            if idx >= len(self._tree_edge_items):
                break
            parent_item = self._folder_items.get(parent_id)
            child_item = self._folder_items.get(child_id)
            if parent_item and child_item:
                self._tree_edge_items[idx].set_positions(
                    parent_item.pos(),
                    child_item.pos()
                )
            idx += 1

    def _create_file_items(
        self,
        positions: Optional[Dict[str, Tuple[float, float]]] = None,
    ):
        """Create FileItem instances for all files."""
        for file_id, data in self._file_data.items():
            item = FileItem(
                file_id=file_id,
                name=data['name'],
                path=data['path'],
                category=data['category'],
                size_kb=data['size_kb'],
                style_manager=self._style,
            )

            # Set position (relative to parent folder or from positions dict)
            if positions and data['path'] in positions:
                x, y = positions[data['path']]
            else:
                # Position near parent folder
                parent_path = data['parent_path']
                if parent_path in self._path_to_folder:
                    parent_item = self._path_to_folder[parent_path]
                    parent_pos = parent_item.pos()
                    # Offset from parent (will be properly positioned by layout)
                    x = parent_pos.x() + 20
                    y = parent_pos.y() + 20
                else:
                    x, y = 0, 0

            item.setPos(x, y)
            item.show_label = self._style.should_show_labels()

            self.addItem(item)
            self._file_items[file_id] = item
            self._path_to_file[data['path']] = item

    def _create_file_edges(self):
        """Create edges connecting folders to their child files."""
        from PyQt6.QtCore import QPointF

        self._file_edge_items.clear()

        # Create an edge for each file to its parent folder
        for file_id, data in self._file_data.items():
            file_item = self._file_items.get(file_id)
            parent_path = data.get('parent_path', '')
            parent_item = self._path_to_folder.get(parent_path)

            if file_item and parent_item:
                edge = EdgeItem(
                    edge_id=-2,  # File edges use -2 to distinguish from tree edges (-1)
                    src_pos=parent_item.pos(),
                    dst_pos=file_item.pos(),
                    relation_type="file",  # Special type for file edges
                    confidence=1.0,
                    evidence=None,
                    style_manager=self._style,
                )
                # File edges visibility tied to file visibility
                edge.setVisible(self._style.should_show_files())
                self.addItem(edge)
                self._file_edge_items.append(edge)

    def update_file_edge_positions(self):
        """Update file edge positions to match current file and folder positions."""
        idx = 0
        for file_id, data in self._file_data.items():
            if idx >= len(self._file_edge_items):
                break
            file_item = self._file_items.get(file_id)
            parent_path = data.get('parent_path', '')
            parent_item = self._path_to_folder.get(parent_path)
            if file_item and parent_item:
                self._file_edge_items[idx].set_positions(
                    parent_item.pos(),
                    file_item.pos()
                )
            idx += 1

    def set_show_file_edges(self, show: bool):
        """Toggle visibility of folder-to-file edges."""
        for edge in self._file_edge_items:
            edge.setVisible(show)

    # -------------------------------------------------------------------------
    # Edge Management
    # -------------------------------------------------------------------------

    def add_edges(self, edges: List[Dict[str, Any]]):
        """
        Add relationship edges.

        Args:
            edges: List of dicts with src_path, dst_path, relation_type, confidence, evidence
        """
        edge_id = 0
        added_count = 0
        for edge in edges:
            src_path = edge.get('src_path', '')
            dst_path = edge.get('dst_path', '')

            # Find source and destination items
            src_item = self._path_to_file.get(src_path) or self._path_to_folder.get(src_path)
            dst_item = self._path_to_file.get(dst_path) or self._path_to_folder.get(dst_path)

            if src_item and dst_item:
                edge_item = EdgeItem(
                    edge_id=edge_id,
                    src_pos=src_item.pos(),
                    dst_pos=dst_item.pos(),
                    relation_type=edge.get('relation_type', 'notes_for'),
                    confidence=edge.get('confidence', 1.0),
                    evidence=edge.get('evidence'),
                    style_manager=self._style,
                )
                self.addItem(edge_item)
                self._edge_items[edge_id] = edge_item
                self._edge_data[edge_id] = edge
                edge_id += 1

    def clear_edges(self):
        """Remove all edge items."""
        for item in self._edge_items.values():
            self.removeItem(item)
        self._edge_items.clear()
        self._edge_data.clear()

    def update_edge_positions(self):
        """Update edge positions to match current node positions."""
        for edge_id, edge_item in self._edge_items.items():
            data = self._edge_data.get(edge_id)
            if data:
                src_item = self._path_to_file.get(data['src_path']) or self._path_to_folder.get(data['src_path'])
                dst_item = self._path_to_file.get(data['dst_path']) or self._path_to_folder.get(data['dst_path'])
                if src_item and dst_item:
                    edge_item.set_positions(src_item.pos(), dst_item.pos())

    # -------------------------------------------------------------------------
    # LOD Updates
    # -------------------------------------------------------------------------

    def update_lod(self, show_files: bool, show_labels: bool):
        """
        Update item visibility based on LOD.

        Args:
            show_files: Whether to show file items
            show_labels: Whether to show labels (legacy parameter)
        """
        # Get granular LOD settings from style manager
        show_file_labels = self._style.should_show_file_labels()
        show_folder_labels = self._style.should_show_folder_labels()

        # Update file visibility and labels
        for item in self._file_items.values():
            item.setVisible(show_files)
            item.show_label = show_file_labels  # File labels appear later than folder labels

        # Update folder labels (appear earlier than file labels)
        for item in self._folder_items.values():
            item.show_label = show_folder_labels

        # Update file edge visibility (show when files are shown)
        for edge in self._file_edge_items:
            edge.setVisible(show_files)

    # -------------------------------------------------------------------------
    # Positioning
    # -------------------------------------------------------------------------

    def set_node_positions(self, positions: Dict[str, Tuple[float, float]]):
        """
        Set positions for all nodes.

        Args:
            positions: Dict mapping path -> (x, y)
        """
        for path, (x, y) in positions.items():
            if path in self._path_to_folder:
                self._path_to_folder[path].setPos(x, y)
            if path in self._path_to_file:
                self._path_to_file[path].setPos(x, y)

        # Update edges
        self.update_edge_positions()

    def get_node_positions(self) -> Dict[str, Tuple[float, float]]:
        """Get current positions of all nodes."""
        positions = {}
        for path, item in self._path_to_folder.items():
            pos = item.pos()
            positions[path] = (pos.x(), pos.y())
        for path, item in self._path_to_file.items():
            pos = item.pos()
            positions[path] = (pos.x(), pos.y())
        return positions

    # -------------------------------------------------------------------------
    # Selection
    # -------------------------------------------------------------------------

    def select_node(self, node_id: Optional[int]):
        """Select a node by ID."""
        # Deselect previous
        if self._selected_node_id is not None:
            if self._selected_node_id in self._folder_items:
                self._folder_items[self._selected_node_id].selected = False
            if self._selected_node_id in self._file_items:
                self._file_items[self._selected_node_id].selected = False

        self._selected_node_id = node_id

        # Select new
        if node_id is not None:
            if node_id in self._folder_items:
                self._folder_items[node_id].selected = True
            if node_id in self._file_items:
                self._file_items[node_id].selected = True

    def get_selected_node(self) -> Optional[Tuple[int, str]]:
        """Get the selected node (id, path) or None."""
        if self._selected_node_id is None:
            return None
        if self._selected_node_id in self._folder_items:
            item = self._folder_items[self._selected_node_id]
            return (item.node_id, item.path)
        if self._selected_node_id in self._file_items:
            item = self._file_items[self._selected_node_id]
            return (item.file_id, item.path)
        return None

    # -------------------------------------------------------------------------
    # Highlighting
    # -------------------------------------------------------------------------

    def highlight_paths(self, paths: Set[str]):
        """Highlight nodes at the given paths."""
        # Clear existing highlights
        for item in self._folder_items.values():
            item.highlighted = False
        for item in self._file_items.values():
            item.highlighted = False

        # Set new highlights
        for path in paths:
            if path in self._path_to_folder:
                self._path_to_folder[path].highlighted = True
            if path in self._path_to_file:
                self._path_to_file[path].highlighted = True

    def clear_highlights(self):
        """Clear all highlights."""
        for item in self._folder_items.values():
            item.highlighted = False
        for item in self._file_items.values():
            item.highlighted = False

    # -------------------------------------------------------------------------
    # Filtering
    # -------------------------------------------------------------------------

    def set_filter(self, categories: Set[str], fade_opacity: float = 0.2,
                   hide_non_matching: bool = False, branch_aware: bool = True):
        """
        Set the file type filter.

        Args:
            categories: Set of category names to show (empty = show all)
            fade_opacity: Opacity for non-matching items (0.0-1.0)
            hide_non_matching: If True, hide instead of fade
            branch_aware: If True, keep parent folders of matching files visible
        """
        self._filter_state = FilterState(
            enabled_categories=categories,
            fade_opacity=fade_opacity,
            hide_non_matching=hide_non_matching,
            branch_aware=branch_aware,
        )

        # Recompute which folders have matching children
        if branch_aware and categories:
            self._compute_folder_matching_children()

        # Apply filter to all items
        self._apply_filter()

    def clear_filter(self):
        """Clear the filter (show all items)."""
        self._filter_state = FilterState()
        self._folder_has_matching_children.clear()

        # Restore all items to full opacity and visibility
        for item in self._folder_items.values():
            item.opacity = 1.0
            item.setVisible(True)
        for item in self._file_items.values():
            item.opacity = 1.0
            item.setVisible(True)

    def _compute_folder_matching_children(self):
        """Compute which folders contain matching files (for branch-aware filtering)."""
        self._folder_has_matching_children.clear()

        # Check each file
        for file_id, data in self._file_data.items():
            category = data.get('category', 'other')
            if self._filter_state.matches_category(category):
                # Mark all ancestor folders as having matching children
                parent_path = data.get('parent_path', '')
                self._mark_ancestors_as_matching(parent_path)

    def _mark_ancestors_as_matching(self, folder_path: str):
        """Mark a folder and all its ancestors as having matching children."""
        # Find the folder item
        folder_item = self._path_to_folder.get(folder_path)
        if folder_item:
            self._folder_has_matching_children[folder_item.node_id] = True

            # Mark parent
            parent_id = self._parent.get(folder_item.node_id)
            if parent_id is not None:
                parent_item = self._folder_items.get(parent_id)
                if parent_item:
                    self._mark_ancestors_as_matching(parent_item.path)

    def _apply_filter(self):
        """Apply current filter state to all items."""
        fs = self._filter_state

        if not fs.is_active():
            # No filter - show everything
            for item in self._folder_items.values():
                item.opacity = 1.0
                item.setVisible(True)
            for item in self._file_items.values():
                item.opacity = 1.0
                item.setVisible(True)
            return

        # Apply filter to folders
        for node_id, item in self._folder_items.items():
            if fs.branch_aware:
                # Show if folder has matching children
                has_match = self._folder_has_matching_children.get(node_id, False)
                # Root always visible
                is_root = (node_id == self._root_id)
                matches = has_match or is_root
            else:
                matches = False  # Folders don't match file categories

            if matches:
                item.opacity = 1.0
                item.setVisible(True)
            elif fs.hide_non_matching:
                item.setVisible(False)
            else:
                item.opacity = fs.fade_opacity
                item.setVisible(True)

        # Apply filter to files
        for file_id, item in self._file_items.items():
            data = self._file_data.get(file_id, {})
            category = data.get('category', 'other')
            matches = fs.matches_category(category)

            if matches:
                item.opacity = 1.0
                item.setVisible(True)
            elif fs.hide_non_matching:
                item.setVisible(False)
            else:
                item.opacity = fs.fade_opacity
                item.setVisible(True)

    def get_matching_file_positions(self) -> List[Tuple[float, float]]:
        """Get positions of files that match the current filter (for force layout)."""
        if not self._filter_state.is_active():
            return []

        positions = []
        for file_id, item in self._file_items.items():
            data = self._file_data.get(file_id, {})
            category = data.get('category', 'other')
            if self._filter_state.matches_category(category):
                pos = item.pos()
                positions.append((pos.x(), pos.y()))

        return positions

    def get_filter_state(self) -> FilterState:
        """Get current filter state."""
        return self._filter_state

    def set_filter_opacity(self, matching_paths: Set[str], opacity: float = 0.2):
        """
        Legacy method - Set opacity for filtered nodes by path.

        Args:
            matching_paths: Paths that match the filter (full opacity)
            opacity: Opacity for non-matching nodes (0.0-1.0)
        """
        for path, item in self._path_to_folder.items():
            if matching_paths and path not in matching_paths:
                item.opacity = opacity
            else:
                item.opacity = 1.0

        for path, item in self._path_to_file.items():
            if matching_paths and path not in matching_paths:
                item.opacity = opacity
            else:
                item.opacity = 1.0

    # -------------------------------------------------------------------------
    # Accessors
    # -------------------------------------------------------------------------

    def get_folder_item(self, node_id: int) -> Optional[FolderItem]:
        """Get a folder item by ID."""
        return self._folder_items.get(node_id)

    def get_file_item(self, file_id: int) -> Optional[FileItem]:
        """Get a file item by ID."""
        return self._file_items.get(file_id)

    def get_item_at_path(self, path: str) -> Optional[FolderItem | FileItem]:
        """Get an item by path."""
        return self._path_to_folder.get(path) or self._path_to_file.get(path)

    def get_children(self, node_id: int) -> List[int]:
        """Get child node IDs for a folder."""
        return self._children.get(node_id, [])

    def get_parent(self, node_id: int) -> Optional[int]:
        """Get parent node ID."""
        return self._parent.get(node_id)
