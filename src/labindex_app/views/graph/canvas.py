"""
ModernGraphCanvas - QGraphicsView-based graph visualization.

Features:
- Smooth pan and zoom
- Level of Detail (LOD) switching
- Tree and Force-directed layouts
- Right-click context menu
- Selection and navigation
"""

import math
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum

from PyQt6.QtWidgets import (
    QGraphicsView, QMenu, QApplication, QPushButton, QHBoxLayout, QWidget,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QWheelEvent, QMouseEvent, QKeyEvent,
    QPainter, QTransform,
)

from .scene import GraphScene, GraphNode
from .style_manager import StyleManager, LODLevel, ColorMode


class LayoutType(Enum):
    """Layout algorithms."""
    TREE = "Tree"
    FORCE = "Force"
    RADIAL = "Radial"


class TreeDirection(Enum):
    """Tree layout direction."""
    TOP_DOWN = "Top-Down"
    LEFT_RIGHT = "Left-Right"
    BOTTOM_UP = "Bottom-Up"
    RIGHT_LEFT = "Right-Left"


class ModernGraphCanvas(QGraphicsView):
    """
    Modern QGraphicsView-based graph visualization.

    Signals:
        node_clicked: Emitted when a node is clicked (path)
        node_double_clicked: Emitted for drill-down (path)
        navigation_changed: Emitted when navigation state changes
        scale_changed: Emitted when zoom level changes
    """

    # Signals
    node_clicked = pyqtSignal(str)
    node_double_clicked = pyqtSignal(str)
    navigation_changed = pyqtSignal(list)  # breadcrumb
    scale_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Style manager
        self._style = StyleManager()

        # Create scene
        self._scene = GraphScene(self._style)
        self.setScene(self._scene)

        # Layout settings
        self._layout_type = LayoutType.TREE
        self._tree_direction = TreeDirection.TOP_DOWN
        self._node_spacing = 60
        self._layer_spacing = 80

        # Zoom settings - essentially unlimited for semantic zoom
        self._min_zoom = 0.001  # Extremely zoomed out
        self._max_zoom = 1000.0  # Extremely zoomed in
        self._zoom_factor = 1.25  # Faster zoom steps

        # Pan state
        self._panning = False
        self._pan_start = QPointF()
        self._last_mouse_pos = QPointF()

        # Data
        self._file_index: Optional[Dict[str, Any]] = None
        self._full_file_index: Optional[Dict[str, Any]] = None
        self._current_root_path: Optional[str] = None
        self._navigation_history: List[str] = []

        # Visibility settings
        self._show_files = True
        self._show_labels = True
        self._show_links = False

        # Filter state
        self._active_filter_categories: Set[str] = set()

        # Configure view
        self._setup_view()

        # Floating navigation buttons
        self._setup_nav_buttons()

    def _setup_view(self):
        """Configure the QGraphicsView."""
        # Use OpenGL for GPU-accelerated rendering
        try:
            gl_widget = QOpenGLWidget()
            self.setViewport(gl_widget)
        except Exception:
            pass  # Fall back to software rendering if OpenGL unavailable

        # Rendering
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Optimization
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)

        # Interaction
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Size
        self.setMinimumSize(400, 300)

    def _setup_nav_buttons(self):
        """Create floating navigation icons in top-left corner."""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import QSize

        # Container widget for buttons - fully transparent
        self._nav_container = QWidget(self)
        self._nav_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        nav_layout = QHBoxLayout(self._nav_container)
        nav_layout.setContentsMargins(12, 12, 12, 12)
        nav_layout.setSpacing(12)

        # Back button - transparent icon style
        self._back_btn = QPushButton("◀")
        self._back_btn.setFixedSize(28, 28)
        self._back_btn.setToolTip("Go back")
        self._back_btn.clicked.connect(self._on_back_clicked)
        self._back_btn.setEnabled(False)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(200, 200, 200, 200);
                border: none;
                font-size: 18px;
            }
            QPushButton:hover { color: rgba(255, 255, 255, 255); }
            QPushButton:pressed { color: rgba(150, 200, 255, 255); }
            QPushButton:disabled { color: rgba(80, 80, 80, 100); }
        """)
        nav_layout.addWidget(self._back_btn)

        # Home button - transparent icon style
        self._home_btn = QPushButton("⌂")
        self._home_btn.setFixedSize(28, 28)
        self._home_btn.setToolTip("Go to root")
        self._home_btn.clicked.connect(self._on_home_clicked)
        self._home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._home_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(200, 200, 200, 200);
                border: none;
                font-size: 20px;
            }
            QPushButton:hover { color: rgba(255, 255, 255, 255); }
            QPushButton:pressed { color: rgba(150, 200, 255, 255); }
        """)
        nav_layout.addWidget(self._home_btn)

        nav_layout.addStretch()

        # Fit size to contents
        self._nav_container.adjustSize()

    def _on_back_clicked(self):
        """Handle back button click."""
        self.navigate_back()

    def _on_home_clicked(self):
        """Handle home button click."""
        self.navigate_to_root()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def style_manager(self) -> StyleManager:
        return self._style

    @property
    def layout_type(self) -> LayoutType:
        return self._layout_type

    @layout_type.setter
    def layout_type(self, value: LayoutType):
        if self._layout_type != value:
            self._layout_type = value
            self._recalculate_layout()

    @property
    def tree_direction(self) -> TreeDirection:
        return self._tree_direction

    @tree_direction.setter
    def tree_direction(self, value: TreeDirection):
        if self._tree_direction != value:
            self._tree_direction = value
            if self._layout_type == LayoutType.TREE:
                self._recalculate_layout()

    @property
    def current_scale(self) -> float:
        return self.transform().m11()

    # -------------------------------------------------------------------------
    # Data Loading
    # -------------------------------------------------------------------------

    def build_graph(self, file_index: Dict[str, Any], preserve_full_index: bool = False):
        """
        Build graph from file index.

        Args:
            file_index: Dict with 'root', 'total_files', 'files' list
            preserve_full_index: If True, don't overwrite stored full index
        """
        if not preserve_full_index:
            self._full_file_index = file_index
            self._current_root_path = None
            self._navigation_history.clear()

        self._file_index = file_index

        # Build scene
        self._scene.build_from_file_index(file_index)

        # Calculate layout
        self._recalculate_layout()

        # Fit in view
        QTimer.singleShot(50, self._fit_in_view)

    def set_relationship_edges(self, edges: List[Dict[str, Any]]):
        """Set relationship edges to display."""
        self._scene.clear_edges()
        if self._show_links:
            self._scene.add_edges(edges)

    def clear_relationship_edges(self):
        """Clear all relationship edges."""
        self._scene.clear_edges()

    # -------------------------------------------------------------------------
    # Layout Calculation
    # -------------------------------------------------------------------------

    def _recalculate_layout(self):
        """Recalculate node positions based on current layout settings."""
        if not self._file_index:
            return

        # Get all nodes from scene
        positions = {}

        if self._layout_type == LayoutType.TREE:
            positions = self._calculate_tree_layout()
        elif self._layout_type == LayoutType.FORCE:
            positions = self._calculate_force_layout()
        elif self._layout_type == LayoutType.RADIAL:
            positions = self._calculate_radial_layout()

        # Apply positions to nodes
        self._scene.set_node_positions(positions)

        # Update edge positions to follow nodes
        self._scene.update_tree_edge_positions()
        self._scene.update_file_edge_positions()
        self._scene.update_edge_positions()

    def _calculate_tree_layout(self) -> Dict[str, Tuple[float, float]]:
        """Calculate hierarchical tree layout that fits within the viewport."""
        positions: Dict[str, Tuple[float, float]] = {}

        # Get nodes from scene
        nodes = self._scene._nodes
        children = self._scene._children
        root_id = self._scene._root_id

        if root_id is None:
            return positions

        # Get viewport size for scaling
        viewport = self.viewport()
        view_width = max(600, viewport.width()) if viewport else 800
        view_height = max(400, viewport.height()) if viewport else 600
        margin = 60

        # Calculate max depth for layer spacing
        max_depth = 0
        for node in nodes.values():
            max_depth = max(max_depth, node.depth)
        max_depth = max(1, max_depth)

        # Calculate subtree widths (accounts for files to prevent overlap)
        def get_subtree_width(node_id: int) -> float:
            node = nodes.get(node_id)
            child_ids = children.get(node_id, [])

            # Base width for the folder itself
            # More files = more width needed for the arc of files
            file_count = node.file_count if node else 0
            # Each file needs some horizontal space in the arc
            file_width = min(file_count * 0.15, 3.0)  # Cap at 3 units for huge folders

            if not child_ids:
                # Leaf folder: base width + file width
                return 1.0 + file_width

            # Non-leaf: sum of children + own file width
            children_width = sum(get_subtree_width(cid) for cid in child_ids)
            return children_width + file_width

        # Position nodes recursively, scaling to fit viewport
        def position_subtree(node_id: int, depth: int, start_pos: float, end_pos: float):
            node = nodes.get(node_id)
            if not node:
                return

            # Get position based on direction
            center_pos = (start_pos + end_pos) / 2

            # Calculate depth position based on direction
            if self._tree_direction in (TreeDirection.TOP_DOWN, TreeDirection.BOTTOM_UP):
                # Horizontal spread, vertical depth
                available_depth = view_height - 2 * margin
                layer_step = available_depth / max(1, max_depth)

                if self._tree_direction == TreeDirection.TOP_DOWN:
                    x, y = center_pos, margin + depth * layer_step
                else:  # BOTTOM_UP
                    x, y = center_pos, view_height - margin - depth * layer_step
            else:
                # Vertical spread, horizontal depth
                available_depth = view_width - 2 * margin
                layer_step = available_depth / max(1, max_depth)

                if self._tree_direction == TreeDirection.LEFT_RIGHT:
                    x, y = margin + depth * layer_step, center_pos
                else:  # RIGHT_LEFT
                    x, y = view_width - margin - depth * layer_step, center_pos

            positions[node.path] = (x, y)
            node.x, node.y = x, y

            # Position children - scale their widths to fit available space
            child_ids = children.get(node_id, [])
            if child_ids:
                child_widths = [get_subtree_width(cid) for cid in child_ids]
                total_width = sum(child_widths)

                # Scale to fit in our range
                available = end_pos - start_pos
                scale = available / total_width if total_width > 0 else 1

                current_pos = start_pos
                for cid, child_width in zip(child_ids, child_widths):
                    scaled_width = child_width * scale
                    position_subtree(cid, depth + 1, current_pos, current_pos + scaled_width)
                    current_pos += scaled_width

        # Start layout - use full viewport width/height for spread direction
        if self._tree_direction in (TreeDirection.TOP_DOWN, TreeDirection.BOTTOM_UP):
            position_subtree(root_id, 0, margin, view_width - margin)
        else:
            position_subtree(root_id, 0, margin, view_height - margin)

        # Position files near their parent folders
        positions.update(self._position_files(positions))

        return positions

    def _calculate_force_layout(self) -> Dict[str, Tuple[float, float]]:
        """
        Calculate force-directed layout with tree constraints.

        Forces:
        1. Strong springs for parent-child (maintain hierarchy)
        2. Repulsion between siblings (spread out)
        3. Attraction between filtered files (cluster when filter active)
        """
        # Start with tree layout as initial positions
        positions = self._calculate_tree_layout()

        nodes = self._scene._nodes
        children = self._scene._children

        if not nodes:
            return positions

        # Get viewport for bounds
        viewport = self.viewport()
        view_width = max(600, viewport.width()) if viewport else 800
        view_height = max(400, viewport.height()) if viewport else 600
        margin = 60

        # Get positions of filtered files (for attraction)
        filter_state = self._scene.get_filter_state()
        filtered_paths: Set[str] = set()
        if filter_state.is_active():
            for file_id, data in self._scene._file_data.items():
                category = data.get('category', 'other')
                if filter_state.matches_category(category):
                    filtered_paths.add(data['path'])

        # Force simulation parameters
        iterations = 100
        cooling = 0.95  # Temperature decay

        # Spring constants
        parent_child_spring = 0.5      # Strong spring for hierarchy
        sibling_repulsion = 1000       # Repulsion between same-depth nodes
        filter_attraction = 0.3        # Attraction between filtered files

        # Convert to mutable dict
        pos = {path: list(xy) for path, xy in positions.items()}

        temperature = 10.0  # Initial movement magnitude

        for iteration in range(iterations):
            forces: Dict[str, List[float]] = {path: [0.0, 0.0] for path in pos}

            # 1. Parent-child springs (keep hierarchy structure)
            for child_id, parent_id in self._scene._parent.items():
                child_node = nodes.get(child_id)
                parent_node = nodes.get(parent_id)
                if child_node and parent_node:
                    child_path = child_node.path
                    parent_path = parent_node.path
                    if child_path in pos and parent_path in pos:
                        dx = pos[parent_path][0] - pos[child_path][0]
                        dy = pos[parent_path][1] - pos[child_path][1]
                        dist = max(1, math.sqrt(dx*dx + dy*dy))

                        # Ideal distance based on layer spacing
                        ideal_dist = self._layer_spacing
                        force = parent_child_spring * (dist - ideal_dist)

                        fx = force * dx / dist
                        fy = force * dy / dist

                        forces[child_path][0] += fx
                        forces[child_path][1] += fy
                        forces[parent_path][0] -= fx * 0.3  # Parent moves less
                        forces[parent_path][1] -= fy * 0.3

            # 2. Repulsion between nodes at same depth
            for node_id, node in nodes.items():
                if node.path not in pos:
                    continue

                for other_id, other in nodes.items():
                    if other_id <= node_id or other.path not in pos:
                        continue
                    if other.depth != node.depth:
                        continue

                    dx = pos[other.path][0] - pos[node.path][0]
                    dy = pos[other.path][1] - pos[node.path][1]
                    dist = max(1, math.sqrt(dx*dx + dy*dy))

                    if dist < self._node_spacing * 3:
                        force = sibling_repulsion / (dist * dist)
                        fx = force * dx / dist
                        fy = force * dy / dist

                        forces[node.path][0] -= fx
                        forces[node.path][1] -= fy
                        forces[other.path][0] += fx
                        forces[other.path][1] += fy

            # 3. Attraction between filtered files (when filter active)
            if filtered_paths:
                filtered_list = list(filtered_paths)
                for i, path1 in enumerate(filtered_list):
                    if path1 not in pos:
                        continue
                    for path2 in filtered_list[i+1:]:
                        if path2 not in pos:
                            continue

                        dx = pos[path2][0] - pos[path1][0]
                        dy = pos[path2][1] - pos[path1][1]
                        dist = max(1, math.sqrt(dx*dx + dy*dy))

                        # Attract filtered files toward each other
                        force = filter_attraction * dist * 0.01
                        fx = force * dx / dist
                        fy = force * dy / dist

                        forces[path1][0] += fx
                        forces[path1][1] += fy
                        forces[path2][0] -= fx
                        forces[path2][1] -= fy

            # Apply forces with temperature
            for path, force_xy in forces.items():
                if path == "":  # Don't move root
                    continue

                fx, fy = force_xy
                # Limit force magnitude
                mag = math.sqrt(fx*fx + fy*fy)
                if mag > temperature:
                    fx = fx / mag * temperature
                    fy = fy / mag * temperature

                pos[path][0] += fx
                pos[path][1] += fy

                # Keep in bounds
                pos[path][0] = max(margin, min(view_width - margin, pos[path][0]))
                pos[path][1] = max(margin, min(view_height - margin, pos[path][1]))

            temperature *= cooling

        # Convert back to tuples
        positions = {path: (xy[0], xy[1]) for path, xy in pos.items()}

        # Position files near their parent folders
        positions.update(self._position_files(positions))

        return positions

    def _calculate_radial_layout(self) -> Dict[str, Tuple[float, float]]:
        """Calculate radial layout with root at center, scaled to fit viewport."""
        positions: Dict[str, Tuple[float, float]] = {}

        nodes = self._scene._nodes
        children = self._scene._children
        root_id = self._scene._root_id

        if root_id is None:
            return positions

        # Get viewport size for scaling
        viewport = self.viewport()
        view_width = max(600, viewport.width()) if viewport else 800
        view_height = max(400, viewport.height()) if viewport else 600
        margin = 60

        # Center position
        center_x = view_width / 2
        center_y = view_height / 2

        # Group nodes by depth
        nodes_by_depth: Dict[int, List[int]] = {}
        for node_id, node in nodes.items():
            depth = node.depth
            if depth not in nodes_by_depth:
                nodes_by_depth[depth] = []
            nodes_by_depth[depth].append(node_id)

        max_depth = max(nodes_by_depth.keys()) if nodes_by_depth else 0

        # Calculate max radius to fit in viewport
        max_radius = min(view_width, view_height) / 2 - margin

        # Position nodes in concentric rings
        for depth, node_ids in nodes_by_depth.items():
            if depth == 0:
                # Root at center
                for nid in node_ids:
                    node = nodes[nid]
                    positions[node.path] = (center_x, center_y)
                    node.x, node.y = center_x, center_y
            else:
                # Scale radius to fit viewport
                radius = (depth / max(1, max_depth)) * max_radius
                angle_step = 2 * math.pi / len(node_ids) if node_ids else 0

                for i, nid in enumerate(node_ids):
                    node = nodes[nid]
                    angle = i * angle_step - math.pi / 2
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions[node.path] = (x, y)
                    node.x, node.y = x, y

        # Position files
        positions.update(self._position_files(positions))

        return positions

    def _position_files(
        self,
        folder_positions: Dict[str, Tuple[float, float]],
    ) -> Dict[str, Tuple[float, float]]:
        """Position file items as leaves around their parent folders.

        Creates an arc/fan effect where files spread out from their parent folder
        in the direction of tree growth. Uses seeded random for consistent positioning.
        Files are positioned close to their parent with varying distances for visual interest.
        Distance scales with zoom level - closer when zoomed out, spread when zoomed in.
        """
        import random

        file_positions: Dict[str, Tuple[float, float]] = {}

        # Group files by parent folder
        files_by_folder: Dict[str, List[Dict]] = {}
        for file_id, data in self._scene._file_data.items():
            parent = data['parent_path']
            if parent not in files_by_folder:
                files_by_folder[parent] = []
            files_by_folder[parent].append(data)

        # Dynamic distance based on zoom level
        # When zoomed out (scale < 0.5), files cluster tight
        # When zoomed in (scale > 1.5), files spread out
        scale = self._style.view_scale
        distance_scale = max(0.3, min(2.0, scale))  # Clamp between 0.3x and 2x

        # Arc parameters - scale with zoom
        min_distance = 12 * distance_scale    # 4-24 based on zoom
        max_distance = 30 * distance_scale    # 10-60 based on zoom
        max_fan_angle = 1.2     # ~70 degrees total spread for full arc
        max_files_shown = 30    # Limit per folder for performance

        # Position files in an arc around each folder
        for folder_path, files in files_by_folder.items():
            if folder_path not in folder_positions:
                continue

            fx, fy = folder_positions[folder_path]
            num_files = len(files)

            if num_files == 0:
                continue

            files_to_show = min(num_files, max_files_shown)

            # Use seeded random for consistent positioning per folder
            folder_seed = hash(folder_path) % 10000
            rng = random.Random(folder_seed)

            # Calculate fan angle based on file count (more files = wider arc)
            fan_angle = min(max_fan_angle, files_to_show * 0.08 + 0.2)

            for i, data in enumerate(files[:files_to_show]):
                # Calculate angle offset within the arc
                if files_to_show == 1:
                    angle_offset = 0
                else:
                    # Spread evenly across the arc
                    t = i / (files_to_show - 1)  # 0 to 1
                    base_offset = -fan_angle / 2 + t * fan_angle
                    # Add small random jitter
                    angle_offset = base_offset + rng.uniform(-0.05, 0.05)

                # Arc shape: center files closer, edge files further
                # This creates a curved/bowl shape
                t_centered = abs(i - (files_to_show - 1) / 2) / max(1, (files_to_show - 1) / 2)
                # Quadratic falloff for smooth arc
                arc_factor = t_centered * t_centered
                distance = min_distance + (max_distance - min_distance) * arc_factor
                # Add random variation for organic feel
                distance += rng.uniform(-3, 5)

                # Convert polar to cartesian offset
                sideways = distance * math.sin(angle_offset)
                forward = distance * math.cos(angle_offset) * 0.6 + 12  # Bias forward

                # Position based on tree direction
                if self._layout_type == LayoutType.TREE:
                    if self._tree_direction == TreeDirection.TOP_DOWN:
                        x = fx + sideways
                        y = fy + forward
                    elif self._tree_direction == TreeDirection.BOTTOM_UP:
                        x = fx + sideways
                        y = fy - forward
                    elif self._tree_direction == TreeDirection.LEFT_RIGHT:
                        x = fx + forward
                        y = fy + sideways
                    else:  # RIGHT_LEFT
                        x = fx - forward
                        y = fy + sideways
                else:
                    # For radial/force, position outward from center
                    angle = math.atan2(fy, fx) if (fx != 0 or fy != 0) else 0
                    x = fx + forward * math.cos(angle) + sideways * math.sin(angle)
                    y = fy + forward * math.sin(angle) - sideways * math.cos(angle)

                file_positions[data['path']] = (x, y)

        return file_positions

    # -------------------------------------------------------------------------
    # Zoom and Pan
    # -------------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming."""
        # Get zoom direction
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # Calculate zoom factor
        if delta > 0:
            factor = self._zoom_factor
        else:
            factor = 1 / self._zoom_factor

        # Check limits
        new_scale = self.current_scale * factor
        if new_scale < self._min_zoom or new_scale > self._max_zoom:
            return

        # Apply zoom
        self.scale(factor, factor)

        # Update the style manager with current scale (for edge width adjustment)
        self._style.view_scale = self.current_scale

        # Update the style manager's LOD level based on new scale
        lod_changed = self._style.update_lod_from_scale(self.current_scale)

        # Update item visibility if LOD changed
        if lod_changed:
            self._update_lod()

        # Reposition files based on new zoom level (dynamic distance)
        self._reposition_files()

        # Force full scene repaint to update edges and items
        self._scene.update()

        # Emit signal
        self.scale_changed.emit(self.current_scale)

    def _reposition_files(self):
        """Reposition files based on current zoom level without recalculating folder layout."""
        # Get current folder positions
        folder_positions = {}
        for path, item in self._scene._path_to_folder.items():
            pos = item.pos()
            folder_positions[path] = (pos.x(), pos.y())

        # Calculate new file positions with current zoom scale
        file_positions = self._position_files(folder_positions)

        # Apply to file items
        for path, (x, y) in file_positions.items():
            if path in self._scene._path_to_file:
                self._scene._path_to_file[path].setPos(x, y)

        # Update file edges
        self._scene.update_file_edge_positions()

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for panning and selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked on item
            item = self.itemAt(event.pos())
            if item:
                # Handle item click
                from .items import FolderItem, FileItem
                if isinstance(item, (FolderItem, FileItem)):
                    self._scene.select_node(item.node_id if hasattr(item, 'node_id') else item.file_id)
                    self.node_clicked.emit(item.path)
            else:
                # Start panning
                self._panning = True
                self._pan_start = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for panning."""
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()

            # Move the view
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click for drill-down."""
        item = self.itemAt(event.pos())
        if item:
            from .items import FolderItem
            if isinstance(item, FolderItem):
                self.node_double_clicked.emit(item.path)
                self.drill_down(item.path)

        super().mouseDoubleClickEvent(event)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def drill_down(self, path: str):
        """Drill down into a folder."""
        if self._full_file_index is None:
            return

        # Save current path to history
        if self._current_root_path is not None:
            self._navigation_history.append(self._current_root_path)
        elif path:
            self._navigation_history.append("")

        self._current_root_path = path

        # Filter file index to only show children
        self._update_filtered_view()

        # Update back button state
        self._back_btn.setEnabled(len(self._navigation_history) > 0)

    def navigate_back(self) -> bool:
        """Navigate back to previous folder."""
        if not self._navigation_history:
            return False

        self._current_root_path = self._navigation_history.pop()
        self._update_filtered_view()

        # Update back button state
        self._back_btn.setEnabled(len(self._navigation_history) > 0)
        return True

    def navigate_to_root(self):
        """Navigate to the root."""
        self._current_root_path = None
        self._navigation_history.clear()

        if self._full_file_index:
            self.build_graph(self._full_file_index, preserve_full_index=True)
            self.navigation_changed.emit([])

        # Update back button state
        self._back_btn.setEnabled(False)

    def _update_filtered_view(self):
        """Update view to show only current folder contents."""
        if self._full_file_index is None:
            return

        if self._current_root_path is None or self._current_root_path == "":
            self.build_graph(self._full_file_index, preserve_full_index=True)
            self.navigation_changed.emit([])
        else:
            # Filter files to current path
            all_files = self._full_file_index.get('files', [])
            filtered = [
                f for f in all_files
                if f['path'].startswith(self._current_root_path + '/') or
                   f['path'] == self._current_root_path
            ]

            filtered_index = {
                'root': self._current_root_path,
                'total_files': len(filtered),
                'files': filtered,
            }

            self.build_graph(filtered_index, preserve_full_index=True)

            # Emit breadcrumb
            from pathlib import Path
            parts = list(Path(self._current_root_path).parts)
            self.navigation_changed.emit(parts)

    def _fit_in_view(self):
        """Fit the graph in the view."""
        # Get the scene bounds
        bounds = self._scene.itemsBoundingRect()
        if bounds.isEmpty():
            return

        # Fit in view with some padding
        self.fitInView(bounds.adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)

        # With semantic zoom, start at a reasonable scale
        # Clamp to a good starting scale for readability
        current = self.current_scale
        if current < 0.5:
            # Zoom in a bit so nodes are visible with labels
            target = 0.6
            factor = target / current
            self.scale(factor, factor)
        elif current > 2.0:
            # Don't start too zoomed in
            target = 1.5
            factor = target / current
            self.scale(factor, factor)

        # Update style manager with current scale
        self._style.view_scale = self.current_scale
        # Update LOD based on final scale
        self._style.update_lod_from_scale(self.current_scale)
        self._update_lod()

    # -------------------------------------------------------------------------
    # LOD and Visibility
    # -------------------------------------------------------------------------

    def _update_lod(self):
        """Update item visibility based on current LOD."""
        show_files = self._show_files and self._style.should_show_files()
        show_labels = self._show_labels and self._style.should_show_labels()
        self._scene.update_lod(show_files, show_labels)

    def set_show_files(self, show: bool):
        """Set whether to show file nodes."""
        self._show_files = show
        self._update_lod()

    def set_show_labels(self, show: bool):
        """Set whether to show labels."""
        self._show_labels = show
        self._update_lod()

    def set_show_links(self, show: bool):
        """Set whether to show relationship edges."""
        self._show_links = show

    def set_show_tree_edges(self, show: bool):
        """Set whether to show tree structure edges."""
        self._scene.set_show_tree_edges(show)

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    def set_layout(self, layout_type: str):
        """Set the layout type by string."""
        try:
            self._layout_type = LayoutType(layout_type)
            self._recalculate_layout()
        except ValueError:
            pass

    def set_tree_direction(self, direction: str):
        """Set the tree direction by string."""
        try:
            self._tree_direction = TreeDirection(direction)
            if self._layout_type == LayoutType.TREE:
                self._recalculate_layout()
        except ValueError:
            pass

    def set_color_mode(self, mode: str):
        """Set the color mode."""
        try:
            self._style.color_mode = ColorMode(mode)
            self.viewport().update()
        except ValueError:
            pass

    def set_node_spacing(self, spacing: int):
        """Set spacing between sibling nodes."""
        self._node_spacing = spacing
        self._recalculate_layout()

    def set_layer_spacing(self, spacing: int):
        """Set spacing between depth levels."""
        self._layer_spacing = spacing
        self._recalculate_layout()

    # -------------------------------------------------------------------------
    # Highlighting
    # -------------------------------------------------------------------------

    def set_highlighted_paths(self, paths: Set[str]):
        """Highlight paths (e.g., search results)."""
        self._scene.highlight_paths(paths)

    def clear_highlighted_paths(self):
        """Clear all highlights."""
        self._scene.clear_highlights()

    # -------------------------------------------------------------------------
    # Filtering
    # -------------------------------------------------------------------------

    def set_file_type_filter(self, categories: Set[str], fade_opacity: float = 0.2):
        """
        Filter to show only specified file categories.

        Args:
            categories: Set of category names ('presentations', 'data', 'code', etc.)
                       Empty set = show all
            fade_opacity: Opacity for non-matching items
        """
        self._active_filter_categories = categories
        self._scene.set_filter(
            categories=categories,
            fade_opacity=fade_opacity,
            hide_non_matching=False,
            branch_aware=True,
        )

        # If using Force layout and filter is active, recalculate to cluster filtered items
        if self._layout_type == LayoutType.FORCE and categories:
            self._recalculate_layout()

    def clear_file_type_filter(self):
        """Clear file type filter (show all)."""
        self._active_filter_categories = set()
        self._scene.clear_filter()

    def toggle_category_filter(self, category: str):
        """Toggle a single category in the filter."""
        if category in self._active_filter_categories:
            self._active_filter_categories.discard(category)
        else:
            self._active_filter_categories.add(category)

        self.set_file_type_filter(self._active_filter_categories)

    # -------------------------------------------------------------------------
    # Context Menu
    # -------------------------------------------------------------------------

    def _show_context_menu(self, pos):
        """Show the right-click context menu."""
        menu = QMenu(self)

        # Layout submenu
        layout_menu = menu.addMenu("Layout")
        for lt in LayoutType:
            action = layout_menu.addAction(lt.value)
            action.setCheckable(True)
            action.setChecked(self._layout_type == lt)
            action.triggered.connect(lambda checked, l=lt: self.set_layout(l.value))

        # Direction submenu (only for Tree)
        if self._layout_type == LayoutType.TREE:
            dir_menu = menu.addMenu("Direction")
            for td in TreeDirection:
                action = dir_menu.addAction(td.value)
                action.setCheckable(True)
                action.setChecked(self._tree_direction == td)
                action.triggered.connect(lambda checked, d=td: self.set_tree_direction(d.value))

        menu.addSeparator()

        # Filter by Type submenu
        filter_menu = menu.addMenu("Filter by Type")

        # Category options
        categories = [
            ("Presentations (PPTX)", "presentations"),
            ("Data Files (ABF, CSV...)", "data"),
            ("Documents (DOCX, PDF...)", "documents"),
            ("Spreadsheets (XLSX)", "spreadsheets"),
            ("Code (PY, IPYNB...)", "code"),
            ("Images", "images"),
        ]

        for label, cat in categories:
            action = filter_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(cat in self._active_filter_categories)
            action.triggered.connect(lambda checked, c=cat: self.toggle_category_filter(c))

        filter_menu.addSeparator()
        clear_action = filter_menu.addAction("Clear Filter")
        clear_action.triggered.connect(self.clear_file_type_filter)

        menu.addSeparator()

        # Visibility toggles
        tree_edges_action = menu.addAction("Show Tree Edges")
        tree_edges_action.setCheckable(True)
        tree_edges_action.setChecked(self._scene._show_tree_edges)
        tree_edges_action.triggered.connect(lambda checked: self.set_show_tree_edges(checked))

        menu.addSeparator()

        # View actions
        fit_action = menu.addAction("Zoom to Fit")
        fit_action.triggered.connect(self._fit_in_view)

        reset_action = menu.addAction("Reset View")
        reset_action.triggered.connect(self.navigate_to_root)

        menu.addSeparator()

        # Export submenu
        export_menu = menu.addMenu("Export")
        pdf_action = export_menu.addAction("Export as PDF...")
        pdf_action.triggered.connect(self._export_as_pdf)
        png_action = export_menu.addAction("Export as PNG...")
        png_action.triggered.connect(self._export_as_png)
        svg_action = export_menu.addAction("Export as SVG...")
        svg_action.triggered.connect(self._export_as_svg)

        menu.addSeparator()

        # Check if clicked on item
        item = self.itemAt(pos)
        if item:
            from .items import FolderItem, FileItem
            if isinstance(item, (FolderItem, FileItem)):
                # Item-specific actions
                if hasattr(item, 'path') and item.path:
                    open_action = menu.addAction("Open in Explorer")
                    open_action.triggered.connect(lambda: self._open_in_explorer(item.path))

                    copy_action = menu.addAction("Copy Path")
                    copy_action.triggered.connect(lambda: self._copy_path(item.path))

        menu.exec(self.mapToGlobal(pos))

    def _open_in_explorer(self, path: str):
        """Open path in system file explorer."""
        import os
        import subprocess
        from pathlib import Path

        if self._full_file_index:
            root = self._full_file_index.get('root', '')
            full_path = Path(root) / path

            if full_path.exists():
                if full_path.is_dir():
                    subprocess.Popen(f'explorer "{full_path}"')
                else:
                    subprocess.Popen(f'explorer /select,"{full_path}"')

    def _copy_path(self, path: str):
        """Copy path to clipboard."""
        if self._full_file_index:
            from pathlib import Path
            root = self._full_file_index.get('root', '')
            full_path = str(Path(root) / path)
            QApplication.clipboard().setText(full_path)

    # -------------------------------------------------------------------------
    # Export Methods
    # -------------------------------------------------------------------------

    def _export_as_pdf(self):
        """Export the graph as a PDF file."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QPainter, QPageSize, QPageLayout
        from PyQt6.QtCore import QMarginsF, QSizeF
        from PyQt6.QtPrintSupport import QPrinter

        # Get filename from user
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Graph as PDF",
            "graph_export.pdf",
            "PDF Files (*.pdf)"
        )
        if not filename:
            return

        # Get scene bounds
        scene_rect = self._scene.itemsBoundingRect()
        if scene_rect.isEmpty():
            return

        # Add padding
        padding = 50
        scene_rect = scene_rect.adjusted(-padding, -padding, padding, padding)

        # Create printer for PDF output
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(filename)

        # Set page size to match scene aspect ratio
        width_inches = max(8.5, scene_rect.width() / 72)  # Minimum letter width
        height_inches = max(11, scene_rect.height() / 72)  # Minimum letter height

        # Maintain aspect ratio
        scene_aspect = scene_rect.width() / scene_rect.height()
        if scene_aspect > width_inches / height_inches:
            height_inches = width_inches / scene_aspect
        else:
            width_inches = height_inches * scene_aspect

        page_size = QPageSize(QSizeF(width_inches * 25.4, height_inches * 25.4), QPageSize.Unit.Millimeter)
        printer.setPageSize(page_size)
        printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

        # Render scene to PDF
        painter = QPainter()
        if painter.begin(printer):
            self._scene.render(painter, source=scene_rect)
            painter.end()

    def _export_as_png(self):
        """Export the graph as a PNG image."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QPainter, QImage
        from PyQt6.QtCore import Qt

        # Get filename from user
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Graph as PNG",
            "graph_export.png",
            "PNG Files (*.png)"
        )
        if not filename:
            return

        # Get scene bounds
        scene_rect = self._scene.itemsBoundingRect()
        if scene_rect.isEmpty():
            return

        # Add padding
        padding = 50
        scene_rect = scene_rect.adjusted(-padding, -padding, padding, padding)

        # Create high-resolution image (2x scale for quality)
        scale = 2.0
        image = QImage(
            int(scene_rect.width() * scale),
            int(scene_rect.height() * scale),
            QImage.Format.Format_ARGB32_Premultiplied
        )
        image.fill(Qt.GlobalColor.white)

        # Render scene to image
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(scale, scale)
        self._scene.render(painter, source=scene_rect)
        painter.end()

        # Save image
        image.save(filename, "PNG")

    def _export_as_svg(self):
        """Export the graph as an SVG file."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtSvg import QSvgGenerator
        from PyQt6.QtGui import QPainter
        from PyQt6.QtCore import QSize

        # Get filename from user
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Graph as SVG",
            "graph_export.svg",
            "SVG Files (*.svg)"
        )
        if not filename:
            return

        # Get scene bounds
        scene_rect = self._scene.itemsBoundingRect()
        if scene_rect.isEmpty():
            return

        # Add padding
        padding = 50
        scene_rect = scene_rect.adjusted(-padding, -padding, padding, padding)

        # Create SVG generator
        generator = QSvgGenerator()
        generator.setFileName(filename)
        generator.setSize(QSize(int(scene_rect.width()), int(scene_rect.height())))
        generator.setViewBox(scene_rect)
        generator.setTitle("LabIndex Graph Export")
        generator.setDescription("File relationship graph exported from LabIndex")

        # Render scene to SVG
        painter = QPainter()
        if painter.begin(generator):
            self._scene.render(painter, source=scene_rect)
            painter.end()
