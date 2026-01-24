"""
Graph Canvas - Interactive file system visualization.

Ported from MetadataBrowser with modifications for LabIndex.
Supports Tree, Radial, Spring, and Circular layouts.
"""

import math
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QPainterPath,
    QWheelEvent, QMouseEvent, QPaintEvent, QFontMetrics
)


class GraphCanvas(QWidget):
    """Custom widget for drawing the file system graph using QPainter.

    Supports proper hierarchical tree layout where each subtree stays grouped,
    with files shown as leaves attached to their parent folders.
    """

    # Signal emitted when user drills into a folder
    node_clicked = pyqtSignal(str)  # folder path
    navigation_changed = pyqtSignal(list)  # breadcrumb path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node_positions = {}
        self.edges = []
        self.folder_hierarchy = {}  # folder_path -> parent_path
        self.folder_children = {}   # folder_path -> [child_folder_paths]
        self.folder_files = {}      # folder_path -> [file_info_dicts]
        self.folder_sizes = {}
        self.folder_counts = {}
        self.folder_categories = {}  # folder_path -> {category: count}
        self.file_positions = {}    # file_path -> (x, y)
        self.root_name = "Root"
        self.layout_type = "Tree"
        self.tree_direction = "Top-Down"  # Top-Down, Left-Right, Bottom-Up, Right-Left
        self.color_mode = "Uniform"  # Consistent golden yellow for clean look
        self.show_labels = True
        self.show_files = True       # Show file leaves
        self.show_file_labels = False
        self.max_depth = 5
        self.actual_max_depth = 0

        # Navigation for drill-down
        self.full_file_index = None  # Store original file index
        self.current_root_path = None  # Current drill-down path
        self.navigation_history = []  # Breadcrumb trail

        # Highlighted paths (for search results)
        self.highlighted_paths = set()  # Files/folders to highlight
        self.highlight_color = QColor(255, 215, 0)  # Gold for highlights

        # Hovered node for tooltips
        self.hovered_node = None
        self.setMouseTracking(True)

        # Zoom and pan
        self.zoom_scale = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self._panning = False
        self._pan_start = None
        self._pan_start_offset = None

        # Auto-scaling based on visible content
        self.detail_scale = 1.0  # Increases when fewer nodes are shown
        self.auto_scale_enabled = True  # Enable automatic detail scaling

        # Layout control parameters
        self.repulsion_strength = 50   # 0-100 (for Spring layout)
        self.min_node_distance = 30    # pixels
        self.node_spacing = 60         # pixels between siblings

        # Tree layout specific parameters
        self.layer_spacing = 80        # pixels between depth levels (vertical in Top-Down)
        self.horizontal_spacing = 40   # pixels minimum between sibling nodes
        self.subtree_gap = 20          # pixels gap between subtrees

        # File leaf fanning parameters (controllable)
        self.file_fan_angle = 0.4      # Max fan angle in radians (0.4 = ~23 degrees)
        self.file_fan_distance = 20    # Base distance from parent folder
        self.file_fan_variation = 12   # Distance variation (creates arc depth)
        self.file_fan_spread = 0.5     # Sideways spread multiplier (0-1)
        self.file_leaf_repulsion = 30  # 0-100: repulsion strength between file leaves (default lower)
        self.file_distance_variability = 50  # 0-100: random variation in distance from parent

        # Balloon layout specific parameters
        self.balloon_radius_scale = 50     # 0-100: how much radius increases per depth
        self.balloon_min_wedge = 15        # minimum wedge angle in degrees for small subtrees
        self.balloon_compactness = 50      # 0-100: how tightly packed the balloon is

        # Spring layout specific parameters
        self.spring_iterations = 50        # number of force-directed iterations
        self.spring_attraction = 50        # 0-100: edge attraction strength
        self.spring_repulsion = 50         # 0-100: node repulsion strength

        # Radial layout specific parameters
        self.radial_layer_spacing = 80     # pixels between concentric circles

        # Colors
        self.bg_color = QColor(20, 20, 20)
        self.node_color = QColor(79, 195, 247)
        self.edge_color = QColor(80, 80, 80)
        self.file_edge_color = QColor(60, 60, 60)
        self.text_color = QColor(200, 200, 200)
        self.root_color = QColor(255, 200, 100)
        self.file_color = QColor(120, 120, 120)  # Gray for files

        # Depth colors for color-by-depth mode
        self.depth_colors = [
            QColor(255, 200, 100),  # Root - gold
            QColor(79, 195, 247),   # Depth 1 - cyan
            QColor(144, 238, 144),  # Depth 2 - light green
            QColor(255, 182, 193),  # Depth 3 - pink
            QColor(255, 218, 185),  # Depth 4 - peach
            QColor(221, 160, 221),  # Depth 5 - plum
            QColor(176, 224, 230),  # Depth 6 - powder blue
            QColor(255, 255, 224),  # Depth 7 - light yellow
        ]

        # Category colors
        self.category_colors = {
            'data': QColor(231, 76, 60),      # Red
            'documents': QColor(52, 152, 219), # Blue
            'spreadsheets': QColor(46, 204, 113), # Green
            'images': QColor(243, 156, 18),   # Orange
            'code': QColor(155, 89, 182),     # Purple
            'slides': QColor(230, 126, 34),   # Dark orange
            'video': QColor(241, 196, 15),    # Yellow
            'archives': QColor(149, 165, 166), # Gray
            'other': QColor(127, 140, 141),   # Dark gray
        }

        # Uniform color for nodes and files (golden yellow)
        self.uniform_color = QColor(255, 215, 100)  # Golden yellow

        # File icon display mode
        self.show_file_icons = True  # Show icons instead of dots

        # Extension to icon type mapping
        self.extension_icons = {
            # Spreadsheets
            '.xlsx': 'spreadsheet', '.xls': 'spreadsheet', '.csv': 'spreadsheet',
            '.ods': 'spreadsheet',
            # Documents
            '.doc': 'word', '.docx': 'word', '.rtf': 'word',
            '.pdf': 'pdf',
            '.txt': 'text', '.md': 'text', '.log': 'text',
            # Code
            '.py': 'code', '.js': 'code', '.m': 'code', '.r': 'code',
            '.ipynb': 'code', '.json': 'code', '.xml': 'code', '.html': 'code',
            # Images
            '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.gif': 'image',
            '.tiff': 'image', '.tif': 'image', '.svg': 'image', '.bmp': 'image',
            # Data files
            '.abf': 'data', '.smrx': 'data', '.smr': 'data', '.edf': 'data',
            '.mat': 'data', '.npz': 'data', '.npy': 'data', '.h5': 'data',
            '.hdf5': 'data', '.nwb': 'data',
            # Video
            '.mp4': 'video', '.avi': 'video', '.mov': 'video', '.mkv': 'video',
            # Archives
            '.zip': 'archive', '.tar': 'archive', '.gz': 'archive', '.7z': 'archive',
            '.rar': 'archive',
        }

        self.setMinimumSize(600, 500)

    def set_show_file_icons(self, show: bool):
        """Toggle file icon display mode."""
        self.show_file_icons = show
        self.update()

    def set_file_leaf_repulsion(self, value: int):
        """Set repulsion strength between file leaves (0-100)."""
        self.file_leaf_repulsion = value
        self._calculate_layout()
        self.update()

    def set_file_distance_variability(self, value: int):
        """Set distance variability from parent (0-100)."""
        self.file_distance_variability = value
        self._calculate_layout()
        self.update()

    def set_layer_spacing(self, value: int):
        """Set vertical spacing between depth levels in Tree layout."""
        self.layer_spacing = value
        self._calculate_layout()
        self.update()

    def set_horizontal_spacing(self, value: int):
        """Set horizontal spacing between sibling nodes."""
        self.horizontal_spacing = value
        self._calculate_layout()
        self.update()

    def set_subtree_gap(self, value: int):
        """Set gap between subtrees."""
        self.subtree_gap = value
        self._calculate_layout()
        self.update()

    def set_file_fan_distance(self, value: int):
        """Set base distance of file leaves from parent folder."""
        self.file_fan_distance = value
        self._calculate_layout()
        self.update()

    # Balloon layout setters
    def set_balloon_radius_scale(self, value: int):
        """Set balloon radius scale (0-100)."""
        self.balloon_radius_scale = value
        self._calculate_layout()
        self.update()

    def set_balloon_min_wedge(self, value: int):
        """Set minimum wedge angle in degrees."""
        self.balloon_min_wedge = value
        self._calculate_layout()
        self.update()

    def set_balloon_compactness(self, value: int):
        """Set balloon compactness (0-100)."""
        self.balloon_compactness = value
        self._calculate_layout()
        self.update()

    # Spring layout setters
    def set_spring_iterations(self, value: int):
        """Set number of force-directed iterations."""
        self.spring_iterations = value
        self._calculate_layout()
        self.update()

    def set_spring_attraction(self, value: int):
        """Set spring attraction strength (0-100)."""
        self.spring_attraction = value
        self._calculate_layout()
        self.update()

    def set_spring_repulsion(self, value: int):
        """Set spring repulsion strength (0-100)."""
        self.spring_repulsion = value
        self._calculate_layout()
        self.update()

    # Radial layout setters
    def set_radial_layer_spacing(self, value: int):
        """Set spacing between concentric circles in radial layout."""
        self.radial_layer_spacing = value
        self._calculate_layout()
        self.update()

    def _get_file_icon_type(self, file_info: dict) -> str:
        """Get the icon type for a file based on its extension."""
        name = file_info.get('name', '').lower()
        for ext, icon_type in self.extension_icons.items():
            if name.endswith(ext):
                return icon_type
        return 'file'  # Default generic file icon

    def _draw_file_icon(self, painter, x: float, y: float, icon_type: str,
                        color: QColor, size: float = 10, highlighted: bool = False):
        """Draw a file type icon at the given position.

        Args:
            painter: QPainter instance
            x, y: Center position
            icon_type: One of 'spreadsheet', 'word', 'pdf', 'text', 'code',
                      'image', 'data', 'video', 'archive', 'folder', 'file'
            color: Fill color
            size: Icon size in pixels
            highlighted: Whether to draw highlight ring
        """
        from PyQt6.QtGui import QPen, QBrush, QPolygonF
        from PyQt6.QtCore import QPointF

        # Convert to int for Qt drawing functions
        size = int(size)
        half = size // 2
        x, y = int(x), int(y)

        # Draw highlight ring if highlighted
        if highlighted:
            highlight_pen = QPen(self.highlight_color)
            highlight_pen.setWidth(2)
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(x - half - 3, y - half - 3, size + 6, size + 6)

        painter.setPen(QPen(color.darker(120)))
        painter.setBrush(QBrush(color))

        if icon_type == 'folder':
            # Folder shape: rectangle with tab on top-left
            tab_w = int(size * 0.4)
            tab_h = int(size * 0.2)
            painter.drawRect(x - half, y - half + tab_h, size, size - tab_h)
            painter.drawRect(x - half, y - half, tab_w, tab_h)

        elif icon_type == 'spreadsheet':
            # Grid/table icon: rectangle with grid lines
            painter.drawRect(x - half, y - half, size, size)
            # Draw grid lines
            painter.setPen(QPen(color.darker(150)))
            third = size // 3
            painter.drawLine(x - half + third, y - half, x - half + third, y + half)
            painter.drawLine(x - half + 2*third, y - half, x - half + 2*third, y + half)
            painter.drawLine(x - half, y - half + third, x + half, y - half + third)
            painter.drawLine(x - half, y - half + 2*third, x + half, y - half + 2*third)

        elif icon_type == 'word':
            # Document with lines
            painter.drawRect(x - half, y - half, size, size)
            # Draw text lines
            painter.setPen(QPen(color.darker(150)))
            for i in range(3):
                ly = int(y - half + size * 0.25 + i * size * 0.22)
                painter.drawLine(x - half + 2, ly, x + half - 2, ly)

        elif icon_type == 'pdf':
            # Document with corner fold
            corner = int(size * 0.25)
            points = [
                QPointF(x - half, y - half),
                QPointF(x + half - corner, y - half),
                QPointF(x + half, y - half + corner),
                QPointF(x + half, y + half),
                QPointF(x - half, y + half),
            ]
            painter.drawPolygon(QPolygonF(points))
            # Draw corner fold line
            painter.setPen(QPen(color.darker(150)))
            painter.drawLine(x + half - corner, y - half, x + half, y - half + corner)

        elif icon_type == 'text':
            # Simple document rectangle
            painter.drawRect(x - half, y - half, size, size)
            # Single line
            painter.setPen(QPen(color.darker(150)))
            painter.drawLine(x - half + 2, y, x + half - 2, y)

        elif icon_type == 'code':
            # Brackets < >
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Left bracket <
            painter.drawLine(x - half + 2, y, x - half // 2, y - half + 2)
            painter.drawLine(x - half + 2, y, x - half // 2, y + half - 2)
            # Right bracket >
            painter.drawLine(x + half - 2, y, x + half // 2, y - half + 2)
            painter.drawLine(x + half - 2, y, x + half // 2, y + half - 2)

        elif icon_type == 'image':
            # Frame with mountain/sun
            painter.drawRect(x - half, y - half, size, size)
            painter.setPen(QPen(color.darker(150)))
            # Simple mountain triangle
            painter.drawLine(x - half + 2, y + half - 2, x, y - 1)
            painter.drawLine(x, y - 1, x + half - 2, y + half - 2)

        elif icon_type == 'data':
            # Cylinder/database shape
            ellipse_h = int(size * 0.4)
            rect_h = int(size * 0.6)
            painter.drawEllipse(x - half, y - half, size, ellipse_h)
            painter.drawRect(x - half, y - half + int(size * 0.2), size, rect_h)
            painter.drawEllipse(x - half, y + half - ellipse_h, size, ellipse_h)

        elif icon_type == 'video':
            # Play button triangle in rectangle
            painter.drawRect(x - half, y - half, size, size)
            painter.setBrush(QBrush(color.darker(150)))
            qh = half // 2  # quarter size
            points = [
                QPointF(x - qh, y - qh),
                QPointF(x - qh, y + qh),
                QPointF(x + qh, y),
            ]
            painter.drawPolygon(QPolygonF(points))

        elif icon_type == 'archive':
            # Box with zipper
            painter.drawRect(x - half, y - half, size, size)
            painter.setPen(QPen(color.darker(150)))
            # Zipper line down center
            painter.drawLine(x, y - half, x, y + half)
            # Zipper teeth
            for i in range(3):
                ty = int(y - half + size * 0.25 + i * size * 0.25)
                painter.drawLine(x - 2, ty, x + 2, ty)

        else:  # 'file' - generic file
            # Simple rectangle
            painter.drawRect(x - half, y - half, size, size)

    def build_graph(self, file_index: Dict, preserve_full_index: bool = False):
        """Build graph structure from file index.

        Creates a proper tree structure where:
        - folder_hierarchy maps each folder to its parent
        - folder_children maps each folder to its child folders
        - folder_files maps each folder to files directly in it

        Args:
            file_index: Dict with 'files' list and 'root' path
            preserve_full_index: If True, don't overwrite self.full_file_index
        """
        # Store full index for drill-down navigation
        if not preserve_full_index:
            self.full_file_index = file_index
            self.current_root_path = None
            self.navigation_history.clear()

        self.node_positions = {}
        self.edges = []
        self.file_positions = {}
        self.folder_hierarchy = {}
        self.folder_children = {}
        self.folder_files = {}
        self.folder_sizes = {}
        self.folder_counts = {}
        self.folder_categories = {}

        files = file_index.get('files', [])
        self.root_name = Path(file_index.get('root', 'Root')).name or 'Root'

        # Initialize root
        self.folder_sizes[self.root_name] = 0
        self.folder_counts[self.root_name] = 0
        self.folder_categories[self.root_name] = {}
        self.folder_children[self.root_name] = []
        self.folder_files[self.root_name] = []

        max_depth_found = 0

        for f in files:
            path = f.get('path', '')
            parts = Path(path).parts
            size = f.get('size_kb', 0)
            category = f.get('category', 'other')

            # Track depth (folder depth, not including file)
            folder_depth = len(parts) - 1
            if folder_depth > max_depth_found:
                max_depth_found = folder_depth

            # Add to root totals
            self.folder_sizes[self.root_name] += size
            self.folder_counts[self.root_name] += 1
            if category not in self.folder_categories[self.root_name]:
                self.folder_categories[self.root_name][category] = 0
            self.folder_categories[self.root_name][category] += 1

            # Build folder hierarchy
            current = self.root_name
            for i, part in enumerate(parts[:-1]):  # Exclude filename
                if i >= self.max_depth:
                    break
                folder_path = '/'.join(parts[:i+1])

                if folder_path not in self.folder_sizes:
                    # New folder - initialize
                    self.folder_sizes[folder_path] = 0
                    self.folder_counts[folder_path] = 0
                    self.folder_categories[folder_path] = {}
                    self.folder_children[folder_path] = []
                    self.folder_files[folder_path] = []
                    self.folder_hierarchy[folder_path] = current
                    self.edges.append((current, folder_path))

                    # Add to parent's children list
                    if folder_path not in self.folder_children[current]:
                        self.folder_children[current].append(folder_path)

                self.folder_sizes[folder_path] += size
                self.folder_counts[folder_path] += 1
                if category not in self.folder_categories[folder_path]:
                    self.folder_categories[folder_path][category] = 0
                self.folder_categories[folder_path][category] += 1
                current = folder_path

            # Add file to its parent folder (current is now the immediate parent)
            file_info = {
                'name': parts[-1] if parts else path,
                'path': path,
                'size': size,
                'category': category
            }
            # Only add if within max_depth
            parent_depth = len(parts) - 1
            if parent_depth <= self.max_depth:
                if current not in self.folder_files:
                    self.folder_files[current] = []
                self.folder_files[current].append(file_info)

        self.actual_max_depth = max_depth_found
        self._calculate_layout()
        self._update_detail_scale()
        self.update()

    def _update_detail_scale(self):
        """Calculate detail scale based on number of visible elements.

        Fewer nodes = larger detail scale = bigger nodes and more info shown.
        """
        if not self.auto_scale_enabled:
            self.detail_scale = 1.0
            return

        # Count visible elements
        num_nodes = len(self.node_positions)
        num_files = len(self.file_positions)
        total_elements = num_nodes + num_files

        # Scale formula: fewer elements = higher detail
        # 1-10 elements: scale 2.5
        # 10-30 elements: scale 2.0
        # 30-100 elements: scale 1.5
        # 100-300 elements: scale 1.2
        # 300+ elements: scale 1.0
        if total_elements <= 10:
            self.detail_scale = 2.5
        elif total_elements <= 30:
            self.detail_scale = 2.0
        elif total_elements <= 100:
            self.detail_scale = 1.5
        elif total_elements <= 300:
            self.detail_scale = 1.2
        else:
            self.detail_scale = 1.0

    def set_layout(self, layout_type: str):
        """Set the layout algorithm."""
        self.layout_type = layout_type
        self._calculate_layout()
        self.update()

    def set_color_mode(self, mode: str):
        """Set the color mode."""
        self.color_mode = mode
        self.update()

    def set_show_labels(self, show: bool):
        """Toggle label visibility."""
        self.show_labels = show
        self.update()

    def set_max_depth(self, depth: int):
        """Set maximum depth to display."""
        self.max_depth = depth
        self.update()

    def set_tree_direction(self, direction: str):
        """Set tree layout direction."""
        self.tree_direction = direction
        if self.layout_type == "Tree":
            self._calculate_layout()
            self.update()

    def set_show_files(self, show: bool):
        """Toggle file leaf visibility."""
        self.show_files = show
        self._calculate_layout()
        self.update()

    def set_show_file_labels(self, show: bool):
        """Toggle file label visibility."""
        self.show_file_labels = show
        self.update()

    def set_repulsion_strength(self, value: int):
        """Set repulsion strength (0-100)."""
        self.repulsion_strength = value
        self._calculate_layout()
        self.update()

    def set_min_node_distance(self, value: int):
        """Set minimum distance between nodes."""
        self.min_node_distance = value
        self._calculate_layout()
        self.update()

    def set_node_spacing(self, value: int):
        """Set spacing between sibling nodes."""
        self.node_spacing = value
        self._calculate_layout()
        self.update()

    def _calculate_layout(self):
        """Calculate node positions based on layout type."""
        if not self.folder_sizes:
            return

        import math
        import random

        nodes = list(self.folder_sizes.keys())
        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        margin = 60

        # Calculate depths
        depths = {self.root_name: 0}
        for folder, parent in self.folder_hierarchy.items():
            if parent in depths:
                depths[folder] = depths[parent] + 1
            else:
                depths[folder] = 1

        if self.layout_type == "Radial":
            self._layout_radial(nodes, depths, center_x, center_y, margin)
        elif self.layout_type == "Spring":
            self._layout_spring(nodes, center_x, center_y, margin)
        elif self.layout_type == "Tree":
            self._layout_tree(nodes, depths, width, height, margin)
        elif self.layout_type == "Balloon":
            self._layout_balloon(nodes, depths, center_x, center_y, margin)
        else:  # Circular
            self._layout_circular(nodes, center_x, center_y, margin)

        # Apply force-directed overlap minimization (but NOT for Tree or Balloon layout)
        # Tree/Balloon layouts position file leaves relative to parent folders, so moving
        # folders afterward would orphan the files under wrong parents
        if self.layout_type not in ("Tree", "Balloon"):
            self._minimize_overlap(nodes, margin)

    def _layout_radial(self, nodes, depths, center_x, center_y, margin):
        """Radial layout with root at center."""
        import math

        nodes_by_depth = {}
        for node in nodes:
            d = depths.get(node, 0)
            if d not in nodes_by_depth:
                nodes_by_depth[d] = []
            nodes_by_depth[d].append(node)

        max_depth = max(nodes_by_depth.keys()) if nodes_by_depth else 0
        max_radius = min(center_x, center_y) - margin

        for depth, depth_nodes in nodes_by_depth.items():
            if depth == 0:
                self.node_positions[self.root_name] = (center_x, center_y)
            else:
                radius = (depth / max(1, max_depth)) * max_radius
                for i, node in enumerate(depth_nodes):
                    angle = (2 * math.pi * i / len(depth_nodes)) - math.pi / 2
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    self.node_positions[node] = (x, y)

    def _layout_spring(self, nodes, center_x, center_y, margin):
        """Force-directed spring layout."""
        import math
        import random

        # Initialize with random positions
        for node in nodes:
            if node == self.root_name:
                self.node_positions[node] = (center_x, center_y)
            else:
                self.node_positions[node] = (
                    center_x + random.uniform(-200, 200),
                    center_y + random.uniform(-200, 200)
                )

        # Scale repulsion by slider value (0-100)
        repulsion_multiplier = 1000 + (self.repulsion_strength * 30)  # 1000-4000 range

        # Force-directed iterations
        for iteration in range(100):
            forces = {node: [0.0, 0.0] for node in nodes}

            # Repulsion between all nodes
            for i, n1 in enumerate(nodes):
                for n2 in nodes[i+1:]:
                    x1, y1 = self.node_positions[n1]
                    x2, y2 = self.node_positions[n2]
                    dx, dy = x2 - x1, y2 - y1
                    dist = max(1, math.sqrt(dx*dx + dy*dy))
                    # Stronger repulsion for closer nodes (scaled by slider)
                    force = repulsion_multiplier / (dist * dist)
                    forces[n1][0] -= force * dx / dist
                    forces[n1][1] -= force * dy / dist
                    forces[n2][0] += force * dx / dist
                    forces[n2][1] += force * dy / dist

            # Attraction along edges
            for parent, child in self.edges:
                if parent in self.node_positions and child in self.node_positions:
                    x1, y1 = self.node_positions[parent]
                    x2, y2 = self.node_positions[child]
                    dx, dy = x2 - x1, y2 - y1
                    dist = max(1, math.sqrt(dx*dx + dy*dy))
                    # Pull connected nodes together
                    force = dist / 30
                    forces[parent][0] += force * dx / dist
                    forces[parent][1] += force * dy / dist
                    forces[child][0] -= force * dx / dist
                    forces[child][1] -= force * dy / dist

            # Apply forces with decreasing step size
            step = 0.1 * (1 - iteration / 100)
            for node in nodes:
                if node != self.root_name:
                    x, y = self.node_positions[node]
                    x += forces[node][0] * step
                    y += forces[node][1] * step
                    # Keep in bounds
                    x = max(margin, min(self.width() - margin, x))
                    y = max(margin, min(self.height() - margin, y))
                    self.node_positions[node] = (x, y)

    def _layout_tree(self, nodes, depths, width, height, margin):
        """Proper hierarchical tree layout where children stay grouped under parent."""
        import math

        direction = self.tree_direction
        # Use min_node_distance to affect tree spacing (so slider has effect)
        spacing = max(self.node_spacing, self.min_node_distance * 2)

        # Calculate subtree widths recursively
        def get_subtree_width(node, depth):
            """Get the width needed for a node and all its descendants."""
            if depth > self.max_depth:
                return 0
            children = self.folder_children.get(node, [])
            if not children:
                # Leaf folder - just needs space for itself (and its files)
                file_count = len(self.folder_files.get(node, []))
                if self.show_files and file_count > 0:
                    return max(spacing, file_count * 8 + spacing)
                return spacing
            # Sum of all children's widths
            total = sum(get_subtree_width(child, depth + 1) for child in children)
            return max(spacing, total)

        # Calculate depths for all folders
        folder_depths = {self.root_name: 0}
        def calc_depths(node, depth):
            for child in self.folder_children.get(node, []):
                folder_depths[child] = depth + 1
                calc_depths(child, depth + 1)
        calc_depths(self.root_name, 0)

        max_depth_found = max(folder_depths.values()) if folder_depths else 0

        # Position nodes recursively
        def position_subtree(node, depth, start_pos, end_pos):
            """Position a node and its subtree within the given range."""
            if depth > self.max_depth:
                return

            # Calculate position for this node (center of its range)
            mid_pos = (start_pos + end_pos) / 2

            # Use layer_spacing parameter for depth positioning
            layer_step = self.layer_spacing

            # Set position based on direction
            if direction == "Top-Down":
                level_y = margin + depth * layer_step
                self.node_positions[node] = (mid_pos, level_y)
            elif direction == "Bottom-Up":
                level_y = height - margin - depth * layer_step
                self.node_positions[node] = (mid_pos, level_y)
            elif direction == "Left-Right":
                level_x = margin + depth * layer_step
                self.node_positions[node] = (level_x, mid_pos)
            else:  # Right-Left
                level_x = width - margin - depth * layer_step
                self.node_positions[node] = (level_x, mid_pos)

            # Position file leaves around this folder
            if self.show_files:
                files = self.folder_files.get(node, [])
                if files:
                    self._position_file_leaves(node, files, depth)

            # Position children
            children = self.folder_children.get(node, [])
            if children and depth < self.max_depth:
                # Calculate total width of children
                child_widths = [get_subtree_width(child, depth + 1) for child in children]
                total_width = sum(child_widths)

                # Scale to fit in our range
                available = end_pos - start_pos
                scale = available / total_width if total_width > 0 else 1

                # Position each child in its portion of the range
                current_pos = start_pos
                for child, child_width in zip(children, child_widths):
                    scaled_width = child_width * scale
                    position_subtree(child, depth + 1, current_pos, current_pos + scaled_width)
                    current_pos += scaled_width

        # Start positioning from root
        if direction in ["Top-Down", "Bottom-Up"]:
            position_subtree(self.root_name, 0, margin, width - margin)
        else:
            position_subtree(self.root_name, 0, margin, height - margin)

        # Apply repulsion between file leaves after initial positioning
        if self.show_files and self.file_leaf_repulsion > 0:
            self._apply_file_leaf_repulsion()

    def _position_file_leaves(self, folder_node, files, depth):
        """Position file leaves in an arc/fan below their parent folder.

        Files fan out in the tree growth direction with variability in distance
        and angle, but constrained to stay under their parent folder.
        Uses class-level parameters for controllable fanning behavior.
        """
        import math
        import random

        if folder_node not in self.node_positions:
            return

        fx, fy = self.node_positions[folder_node]
        num_files = len(files)
        max_files_shown = 20  # Limit files shown per folder for performance
        files_to_show = min(num_files, max_files_shown)

        direction = self.tree_direction

        # Scale distance variability by the parameter (0-100)
        # At 0: no variation, at 100: maximum variation
        variability_scale = self.file_distance_variability / 100  # 0.0 to 1.0

        # Use class-level fanning parameters
        base_distance = self.file_fan_distance
        distance_variation = self.file_fan_variation * variability_scale

        # Calculate fan angle - deeper levels get narrower fans
        depth_factor = max(0.3, 1.0 - depth * 0.12)  # Reduces with depth
        max_fan_angle = self.file_fan_angle * depth_factor
        # Scale fan angle based on file count (more files = wider fan, up to max)
        fan_angle = min(max_fan_angle, files_to_show * 0.05 + 0.15)

        # Sideways spread multiplier from parameter
        sideways_mult = self.file_fan_spread * depth_factor

        # Use a seeded random for consistent positioning per folder
        folder_seed = hash(folder_node) % 10000
        rng = random.Random(folder_seed)

        for i, file_info in enumerate(files[:files_to_show]):
            # Calculate angle offset within the fan
            if files_to_show == 1:
                angle_offset = 0
            else:
                # Spread evenly across the fan, with slight randomness
                base_offset = -fan_angle/2 + (i / (files_to_show - 1)) * fan_angle
                angle_offset = base_offset + rng.uniform(-0.08, 0.08)

            # Vary the distance from parent (creates arc depth)
            # Center files closer, edge files further - creates the arc shape
            center_factor = 1.0 - abs(i - files_to_show/2) / (files_to_show/2 + 0.1)
            distance = base_distance + distance_variation * (1 - center_factor * 0.4)
            # Add random variation scaled by variability parameter
            distance += rng.uniform(-3, 8) * variability_scale

            # Calculate positions - forward push in tree direction, controlled sideways spread
            sideways = distance * math.sin(angle_offset) * sideways_mult
            forward = distance * 0.9 + 8  # Forward push in tree direction

            if direction == "Top-Down":
                file_x = fx + sideways
                file_y = fy + forward
            elif direction == "Bottom-Up":
                file_x = fx + sideways
                file_y = fy - forward
            elif direction == "Left-Right":
                file_x = fx + forward
                file_y = fy + sideways
            else:  # Right-Left
                file_x = fx - forward
                file_y = fy + sideways

            self.file_positions[file_info['path']] = (file_x, file_y, file_info)

    def _apply_file_leaf_repulsion(self):
        """Apply repulsion forces between file leaves to spread them apart.

        This is called after initial file positioning to push overlapping
        files away from each other based on the file_leaf_repulsion parameter.
        The parameter range is 0-100 but effects are scaled for sensitivity.
        """
        import math

        if not self.file_positions or self.file_leaf_repulsion == 0:
            return

        # Convert to list for easier manipulation
        file_paths = list(self.file_positions.keys())
        if len(file_paths) < 2:
            return

        # Scale for gentler effect (slider 0-100 maps to gentle spreading)
        # At 10: modest spread, at 50: moderate spread, at 100: maximum spread
        scale = self.file_leaf_repulsion / 100.0

        # Number of iterations (3-10)
        iterations = 3 + int(7 * scale)
        # Minimum distance between files (8-20 pixels)
        min_dist = 8 + scale * 12
        # Force strength (0.1-0.4)
        force_strength = 0.1 + scale * 0.3

        for _ in range(iterations):
            moves = {}  # file_path -> (dx, dy)

            for i, path1 in enumerate(file_paths):
                x1, y1, info1 = self.file_positions[path1]
                dx_total, dy_total = 0, 0

                for path2 in file_paths[i+1:]:
                    x2, y2, info2 = self.file_positions[path2]

                    dx = x2 - x1
                    dy = y2 - y1
                    dist = math.sqrt(dx*dx + dy*dy)

                    if dist < min_dist and dist > 0.1:
                        # Push apart
                        push = (min_dist - dist) * force_strength
                        nx, ny = dx / dist, dy / dist

                        dx_total -= nx * push
                        dy_total -= ny * push

                        # Also move the other file
                        if path2 not in moves:
                            moves[path2] = [0, 0]
                        moves[path2][0] += nx * push
                        moves[path2][1] += ny * push

                if dx_total != 0 or dy_total != 0:
                    if path1 not in moves:
                        moves[path1] = [0, 0]
                    moves[path1][0] += dx_total
                    moves[path1][1] += dy_total

            # Apply moves
            for path, (dx, dy) in moves.items():
                x, y, info = self.file_positions[path]
                self.file_positions[path] = (x + dx, y + dy, info)

    def _layout_circular(self, nodes, center_x, center_y, margin):
        """Circular layout with all nodes on a circle."""
        import math
        radius = min(center_x, center_y) - margin
        for i, node in enumerate(nodes):
            angle = (2 * math.pi * i / max(1, len(nodes))) - math.pi / 2
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            self.node_positions[node] = (x, y)

    def _layout_balloon(self, nodes, depths, center_x, center_y, margin):
        """Balloon tree layout - radial with circular subtree arrangement.

        Each subtree is arranged in a circular "balloon" around its parent,
        with wedge angles proportional to subtree size. This is ideal for
        leaf-heavy hierarchies as it uses 360 degrees of space.
        """
        import math

        if not nodes:
            return

        # Calculate subtree sizes (total descendants including self)
        subtree_sizes = {}

        def calc_subtree_size(node):
            """Recursively calculate size of subtree rooted at node."""
            if node in subtree_sizes:
                return subtree_sizes[node]

            children = self.folder_children.get(node, [])
            # Filter to nodes that exist and are within max_depth
            children = [c for c in children if c in self.folder_sizes]

            # Count files as well
            file_count = len(self.folder_files.get(node, []))

            size = 1 + file_count  # Self + files
            for child in children:
                size += calc_subtree_size(child)

            subtree_sizes[node] = size
            return size

        # Calculate all subtree sizes
        for node in nodes:
            calc_subtree_size(node)

        # Layout parameters based on settings
        base_radius = 40 + (self.balloon_radius_scale / 100) * 60  # 40-100 base
        radius_increment = 50 + (self.balloon_radius_scale / 100) * 50  # 50-100 per depth
        min_wedge_rad = math.radians(self.balloon_min_wedge)  # Convert to radians
        compactness = 0.3 + (self.balloon_compactness / 100) * 0.7  # 0.3-1.0

        # Place root at center
        self.node_positions[self.root_name] = (center_x, center_y)

        def layout_children(parent_node, parent_x, parent_y, start_angle, total_angle, depth):
            """Recursively layout children in a balloon pattern."""
            children = self.folder_children.get(parent_node, [])
            # Filter to nodes that exist and are within display depth
            children = [c for c in children if c in self.folder_sizes]

            if not children:
                return

            # Calculate radius for this depth level
            radius = base_radius + depth * radius_increment * compactness

            # Calculate total weight of all children
            total_weight = sum(subtree_sizes.get(c, 1) for c in children)

            if total_weight == 0:
                total_weight = len(children)

            # Distribute children around the parent
            current_angle = start_angle

            for child in children:
                child_weight = subtree_sizes.get(child, 1)
                # Wedge angle proportional to subtree size
                wedge_angle = max(min_wedge_rad, (child_weight / total_weight) * total_angle)

                # Place child at middle of its wedge
                child_angle = current_angle + wedge_angle / 2

                # Position child
                child_x = parent_x + radius * math.cos(child_angle)
                child_y = parent_y + radius * math.sin(child_angle)
                self.node_positions[child] = (child_x, child_y)

                # Recursively layout grandchildren
                # Children get a portion of the parent's wedge, slightly reduced
                child_start = child_angle - wedge_angle * 0.4
                child_total = wedge_angle * 0.8
                layout_children(child, child_x, child_y, child_start, child_total, depth + 1)

                current_angle += wedge_angle

        # Start layout from root, using full circle (2*pi)
        # Start at top (-pi/2) and go clockwise
        layout_children(self.root_name, center_x, center_y, -math.pi/2, 2 * math.pi, 1)

        # Position file leaves around their parent folders
        if self.show_files:
            # Calculate depths for file positioning
            node_depths = {self.root_name: 0}
            for node in nodes:
                if node in self.folder_hierarchy:
                    parent = self.folder_hierarchy[node]
                    if parent in node_depths:
                        node_depths[node] = node_depths[parent] + 1

            # Position files for each folder
            for node in nodes:
                if node in self.node_positions:
                    files = self.folder_files.get(node, [])
                    if files:
                        depth = node_depths.get(node, 0)
                        self._position_file_leaves(node, files, depth)

            # Apply repulsion between file leaves
            if self.file_leaf_repulsion > 0:
                self._apply_file_leaf_repulsion()

    def _minimize_overlap(self, nodes, margin):
        """Apply force-directed repulsion to minimize node overlap."""
        import math

        # Scale iterations by repulsion strength (0-100)
        iterations = 10 + int(20 * self.repulsion_strength / 100)

        for _ in range(iterations):
            moved = False
            for i, n1 in enumerate(nodes):
                for n2 in nodes[i+1:]:
                    x1, y1 = self.node_positions[n1]
                    x2, y2 = self.node_positions[n2]
                    dx, dy = x2 - x1, y2 - y1
                    dist = math.sqrt(dx*dx + dy*dy)

                    # Use configurable min distance
                    min_dist = self.min_node_distance
                    if dist < min_dist and dist > 0:
                        # Push nodes apart
                        push = (min_dist - dist) / 2
                        nx, ny = dx / dist, dy / dist
                        if n1 != self.root_name:
                            new_x1 = x1 - nx * push
                            new_y1 = y1 - ny * push
                            new_x1 = max(margin, min(self.width() - margin, new_x1))
                            new_y1 = max(margin, min(self.height() - margin, new_y1))
                            self.node_positions[n1] = (new_x1, new_y1)
                        if n2 != self.root_name:
                            new_x2 = x2 + nx * push
                            new_y2 = y2 + ny * push
                            new_x2 = max(margin, min(self.width() - margin, new_x2))
                            new_y2 = max(margin, min(self.height() - margin, new_y2))
                            self.node_positions[n2] = (new_x2, new_y2)
                        moved = True
            if not moved:
                break

    def paintEvent(self, event):
        """Paint the graph."""
        from PyQt6.QtGui import QPainter, QPen, QBrush, QFont
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background (drawn without transform)
        painter.fillRect(self.rect(), self.bg_color)

        # Early return if no data yet
        if not self.folder_sizes:
            painter.setPen(QPen(self.text_color))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data - run a crawl first")
            return

        # Apply zoom and pan transform
        painter.translate(self.pan_offset_x, self.pan_offset_y)
        painter.scale(self.zoom_scale, self.zoom_scale)

        # Draw zoom indicator in corner (save/restore to avoid transform)
        if self.zoom_scale != 1.0:
            painter.save()
            painter.resetTransform()
            painter.setPen(QPen(QColor(100, 100, 100)))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(10, self.height() - 10, f"Zoom: {self.zoom_scale:.0%}")
            painter.restore()
            # Reapply transform
            painter.translate(self.pan_offset_x, self.pan_offset_y)
            painter.scale(self.zoom_scale, self.zoom_scale)

        # Calculate depths for coloring
        depths = {self.root_name: 0}
        for folder, parent in self.folder_hierarchy.items():
            if parent in depths:
                depths[folder] = depths[parent] + 1
            else:
                depths[folder] = 1

        # Draw edges
        edge_pen = QPen(self.edge_color)
        edge_pen.setWidth(1)
        painter.setPen(edge_pen)

        for parent, child in self.edges:
            if parent in self.node_positions and child in self.node_positions:
                # Only draw if within max depth
                if depths.get(child, 0) <= self.max_depth:
                    x1, y1 = self.node_positions[parent]
                    x2, y2 = self.node_positions[child]
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw nodes
        for node, (x, y) in self.node_positions.items():
            depth = depths.get(node, 0)
            if depth > self.max_depth:
                continue

            # Determine color based on mode
            if self.color_mode == "Uniform":
                # Consistent golden yellow for all nodes
                color = self.uniform_color
            elif self.color_mode == "Depth":
                color = self.depth_colors[min(depth, len(self.depth_colors) - 1)]
            elif self.color_mode == "Category":
                # Use dominant category
                cats = self.folder_categories.get(node, {})
                if cats:
                    dominant = max(cats, key=cats.get)
                    color = self.category_colors.get(dominant, self.node_color)
                else:
                    color = self.node_color
            elif self.color_mode == "Size":
                # Color by size (red = large, blue = small)
                size = self.folder_sizes.get(node, 0)
                max_size = max(self.folder_sizes.values()) if self.folder_sizes else 1
                ratio = min(1, size / max(1, max_size))
                r = int(255 * ratio)
                b = int(255 * (1 - ratio))
                color = QColor(r, 100, b)
            else:
                color = self.node_color

            # Node size based on file count, scaled by detail_scale
            count = self.folder_counts.get(node, 1)
            max_count = max(self.folder_counts.values()) if self.folder_counts else 1
            base_size = 6 + 12 * (count / max(1, max_count))
            if node == self.root_name:
                base_size = max(base_size, 14)
            size = base_size * self.detail_scale

            # Corner radius for rounded rectangles (folders are squares with rounded corners)
            corner_radius = max(2, size * 0.2)

            # Draw highlight ring for highlighted nodes (search results)
            if node in self.highlighted_paths:
                highlight_pen = QPen(self.highlight_color)
                highlight_pen.setWidth(int(3 * self.detail_scale))
                painter.setPen(highlight_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(int(x - size/2 - 4), int(y - size/2 - 4),
                                       int(size + 8), int(size + 8),
                                       corner_radius + 2, corner_radius + 2)

            # Draw hover ring for hovered node
            if node == self.hovered_node:
                hover_pen = QPen(QColor(255, 255, 255, 150))
                hover_pen.setWidth(int(2 * self.detail_scale))
                painter.setPen(hover_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(int(x - size/2 - 2), int(y - size/2 - 2),
                                       int(size + 4), int(size + 4),
                                       corner_radius + 1, corner_radius + 1)

            # Draw the folder node as a rounded square
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(int(x - size/2), int(y - size/2),
                                   int(size), int(size),
                                   corner_radius, corner_radius)

            # Draw label - larger font and more text when detail_scale is high
            font_size = int(8 * self.detail_scale)
            max_label_len = int(15 + 10 * (self.detail_scale - 1))  # More chars at higher detail
            if self.show_labels and size > 8:
                painter.setPen(QPen(self.text_color))
                font = QFont("Segoe UI", font_size)
                painter.setFont(font)
                # Get folder name (last part of path)
                label = node.split('/')[-1] if '/' in node else node
                if len(label) > max_label_len:
                    label = label[:max_label_len - 3] + "..."
                painter.drawText(int(x + size/2 + 3), int(y + font_size/2), label)

        # Draw file leaves (if enabled)
        if self.show_files and self.file_positions:
            # Draw edges from folders to files (thin lines)
            file_edge_pen = QPen(self.file_edge_color)
            file_edge_pen.setWidth(1)
            painter.setPen(file_edge_pen)

            for file_path, (fx, fy, file_info) in self.file_positions.items():
                # Find parent folder and draw connecting line
                for folder_node, (folder_x, folder_y) in self.node_positions.items():
                    files_in_folder = self.folder_files.get(folder_node, [])
                    if any(f['path'] == file_path for f in files_in_folder):
                        painter.drawLine(int(folder_x), int(folder_y), int(fx), int(fy))
                        break

            # Draw file nodes (icons or dots)
            for file_path, (fx, fy, file_info) in self.file_positions.items():
                # Files ALWAYS use category colors for meaningful visual info
                # (Uniform mode only affects folder nodes, not file leaves)
                category = file_info.get('category', 'other')
                color = self.category_colors.get(category, self.file_color)

                # Check if this file is highlighted (search results)
                is_highlighted = file_path in self.highlighted_paths

                # Scale file size by detail_scale for better visibility when drilling down
                base_file_size = 12 if is_highlighted else 10
                file_size = base_file_size * self.detail_scale

                if self.show_file_icons:
                    # Draw file type icon
                    icon_type = self._get_file_icon_type(file_info)
                    self._draw_file_icon(painter, fx, fy, icon_type, color,
                                        size=file_size, highlighted=is_highlighted)
                else:
                    # Draw simple dots (original behavior) - scaled by detail_scale
                    base_dot_size = 6 if is_highlighted else 4
                    dot_size = base_dot_size * self.detail_scale

                    # Draw highlight ring for highlighted files
                    if is_highlighted:
                        highlight_pen = QPen(self.highlight_color)
                        highlight_pen.setWidth(max(2, int(2 * self.detail_scale)))
                        painter.setPen(highlight_pen)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        ring_padding = 3 * self.detail_scale
                        painter.drawEllipse(int(fx - dot_size/2 - ring_padding),
                                           int(fy - dot_size/2 - ring_padding),
                                           int(dot_size + ring_padding * 2),
                                           int(dot_size + ring_padding * 2))

                    # Draw the file dot
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(int(fx - dot_size/2), int(fy - dot_size/2),
                                       int(dot_size), int(dot_size))

                # Draw file label if enabled or highlighted
                if self.show_file_labels or is_highlighted:
                    painter.setPen(QPen(QColor(200, 200, 150) if is_highlighted else QColor(150, 150, 150)))
                    # Scale font size by detail_scale
                    font_size = max(7, int(7 * self.detail_scale))
                    font = QFont("Segoe UI", font_size)
                    if is_highlighted:
                        font.setBold(True)
                    painter.setFont(font)
                    label = file_info.get('name', '')
                    # Show more of the label when detail_scale is high
                    max_label_len = int(15 + 10 * (self.detail_scale - 1))
                    if len(label) > max_label_len:
                        label = label[:max_label_len - 3] + "..."
                    painter.drawText(int(fx + file_size/2 + 2), int(fy + font_size/2), label)

    def resizeEvent(self, event):
        """Recalculate layout on resize."""
        super().resizeEvent(event)
        if self.folder_sizes:
            self._calculate_layout()

    def mousePressEvent(self, event):
        """Handle mouse clicks for drill-down navigation and panning."""
        # Middle mouse button or Ctrl+Left for panning
        if (event.button() == Qt.MouseButton.MiddleButton or
            (event.button() == Qt.MouseButton.LeftButton and
             event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
            self._panning = True
            self._pan_start = event.position()
            self._pan_start_offset = (self.pan_offset_x, self.pan_offset_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            clicked_node = self._get_node_at_position(event.position())
            if clicked_node and clicked_node != self.root_name:
                # Double-click to drill down (single click just selects)
                pass  # Could add selection highlight here
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop panning."""
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to drill into a folder."""
        if event.button() == Qt.MouseButton.LeftButton:
            clicked_node = self._get_node_at_position(event.position())
            if clicked_node and clicked_node in self.folder_children:
                # It's a folder - drill down into it
                self.drill_down(clicked_node)
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        """Handle scroll wheel for zooming."""
        # Get zoom center (mouse position)
        mouse_pos = event.position()

        # Calculate zoom factor
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9

        # Calculate new zoom level
        new_zoom = self.zoom_scale * zoom_factor
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))

        if new_zoom != self.zoom_scale:
            # Zoom towards mouse position
            # Convert mouse position to graph coordinates before zoom
            graph_x = (mouse_pos.x() - self.pan_offset_x) / self.zoom_scale
            graph_y = (mouse_pos.y() - self.pan_offset_y) / self.zoom_scale

            # Update zoom
            self.zoom_scale = new_zoom

            # Adjust pan to keep mouse position fixed
            self.pan_offset_x = mouse_pos.x() - graph_x * self.zoom_scale
            self.pan_offset_y = mouse_pos.y() - graph_y * self.zoom_scale

            self.update()

        event.accept()

    def reset_view(self):
        """Reset zoom and pan to default."""
        self.zoom_scale = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.update()

    def fit_to_view(self):
        """Fit the entire graph to the visible area."""
        if not self.node_positions:
            return

        # Find bounding box of all nodes
        xs = [pos[0] for pos in self.node_positions.values()]
        ys = [pos[1] for pos in self.node_positions.values()]

        # Include file positions
        for pos in self.file_positions.values():
            xs.append(pos[0])
            ys.append(pos[1])

        if not xs or not ys:
            return

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Add margin
        margin = 50
        graph_width = max_x - min_x + 2 * margin
        graph_height = max_y - min_y + 2 * margin

        # Calculate zoom to fit
        zoom_x = self.width() / graph_width if graph_width > 0 else 1
        zoom_y = self.height() / graph_height if graph_height > 0 else 1
        self.zoom_scale = min(zoom_x, zoom_y, 1.0)  # Don't zoom in beyond 100%

        # Center the graph
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        self.pan_offset_x = self.width() / 2 - center_x * self.zoom_scale
        self.pan_offset_y = self.height() / 2 - center_y * self.zoom_scale

        self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse movement for hover effects and panning."""
        # Handle panning
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self.pan_offset_x = self._pan_start_offset[0] + delta.x()
            self.pan_offset_y = self._pan_start_offset[1] + delta.y()
            self.update()
            event.accept()
            return

        pos = event.position()

        # Check for file hover first
        file_info = self._get_file_at_position(pos)
        if file_info:
            # Show file tooltip
            name = file_info.get('name', 'Unknown')
            category = file_info.get('category', 'other')
            size_kb = file_info.get('size', 0)
            size_str = f"{size_kb/1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.0f} KB"
            full_path = file_info.get('path', '')
            self.setToolTip(f"📄 {name}\nType: {category}\nSize: {size_str}\nPath: {full_path}\n\nRight-click to open")
            self.hovered_node = None
            self.update()
            super().mouseMoveEvent(event)
            return

        # Check for folder hover
        node = self._get_node_at_position(pos)
        if node != self.hovered_node:
            self.hovered_node = node
            self.update()
            # Show tooltip with folder info
            if node and node in self.folder_counts:
                count = self.folder_counts.get(node, 0)
                size_kb = self.folder_sizes.get(node, 0)
                size_str = f"{size_kb/1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.0f} KB"
                self.setToolTip(f"📁 {node}\n{count} files, {size_str}\nDouble-click to explore\n\n🔍 Scroll to zoom, Ctrl+drag to pan")
            else:
                self.setToolTip("")
        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        """Handle right-click context menu for files."""
        pos = event.pos()

        # Check if clicking on a file
        file_info = self._get_file_at_position(pos)
        if file_info:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2d2d30;
                    color: #d4d4d4;
                    border: 1px solid #3e3e42;
                }
                QMenu::item:selected {
                    background-color: #094771;
                }
            """)

            file_path = file_info.get('path', '')
            file_name = file_info.get('name', 'file')
            category = file_info.get('category', 'other')

            # Open file action
            open_action = menu.addAction(f"📂 Open {file_name}")
            open_action.triggered.connect(lambda: self._open_file(file_path))

            # Open containing folder
            folder_action = menu.addAction("📁 Open containing folder")
            folder_action.triggered.connect(lambda: self._open_folder(file_path))

            menu.addSeparator()

            # Copy path
            copy_action = menu.addAction("📋 Copy path")
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(file_path))

            # File info
            menu.addSeparator()
            info_action = menu.addAction(f"ℹ️ {category.title()} file")
            info_action.setEnabled(False)

            menu.exec(event.globalPos())
            return

        # Check if clicking on a folder
        folder = self._get_node_at_position(pos)
        if folder and folder in self.folder_children:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2d2d30;
                    color: #d4d4d4;
                    border: 1px solid #3e3e42;
                }
                QMenu::item:selected {
                    background-color: #094771;
                }
            """)

            # Drill down
            drill_action = menu.addAction("🔍 Explore this folder")
            drill_action.triggered.connect(lambda: self.drill_down(folder))

            # Open in file explorer
            open_action = menu.addAction("📂 Open in Explorer")
            open_action.triggered.connect(lambda: self._open_folder_in_explorer(folder))

            menu.exec(event.globalPos())
            return

        super().contextMenuEvent(event)

    def _screen_to_graph(self, pos):
        """Convert screen coordinates to graph coordinates (accounting for zoom/pan)."""
        x = (pos.x() - self.pan_offset_x) / self.zoom_scale
        y = (pos.y() - self.pan_offset_y) / self.zoom_scale
        return x, y

    def _get_file_at_position(self, pos):
        """Find which file leaf is at the given position."""
        if not self.show_files:
            return None

        # Convert to graph coordinates
        x, y = self._screen_to_graph(pos)

        for file_path, (fx, fy, file_info) in self.file_positions.items():
            is_highlighted = file_path in self.highlighted_paths
            # Match the scaled size used in drawing
            base_file_size = 12 if is_highlighted else 10
            file_size = base_file_size * self.detail_scale
            # Hit radius = file size + buffer (buffer scales inversely with zoom for easier clicking)
            buffer = 5 / self.zoom_scale
            hit_radius = file_size / 2 + buffer
            if (x - fx) ** 2 + (y - fy) ** 2 <= hit_radius ** 2:
                return file_info
        return None

    def _open_file(self, file_path: str):
        """Open a file with the default system application."""
        import subprocess
        import os as _os
        full_path = self._resolve_full_path(file_path)
        if full_path and Path(full_path).exists():
            if sys.platform == 'win32':
                _os.startfile(full_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', full_path])
            else:
                subprocess.run(['xdg-open', full_path])

    def _open_folder(self, file_path: str):
        """Open the folder containing a file."""
        import subprocess
        import os as _os
        full_path = self._resolve_full_path(file_path)
        if full_path:
            folder = str(Path(full_path).parent)
            if Path(folder).exists():
                if sys.platform == 'win32':
                    subprocess.run(['explorer', '/select,', full_path])
                elif sys.platform == 'darwin':
                    subprocess.run(['open', '-R', full_path])
                else:
                    subprocess.run(['xdg-open', folder])

    def _open_folder_in_explorer(self, folder_path: str):
        """Open a folder in the system file explorer."""
        import subprocess
        import os as _os
        full_path = self._resolve_full_path(folder_path)
        if full_path and Path(full_path).exists():
            if sys.platform == 'win32':
                _os.startfile(full_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', full_path])
            else:
                subprocess.run(['xdg-open', full_path])

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        full_path = self._resolve_full_path(text)
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(full_path or text)

    def _resolve_full_path(self, relative_path: str) -> str:
        """Resolve a relative path to full path using the file index root."""
        if not self.full_file_index:
            return relative_path
        root = self.full_file_index.get('root', '')
        if not root:
            return relative_path
        return str(Path(root) / relative_path)

    def _get_node_at_position(self, pos):
        """Find which node is at the given position."""
        # Convert to graph coordinates
        x, y = self._screen_to_graph(pos)

        # Check folder nodes first
        for node, (nx, ny) in self.node_positions.items():
            count = self.folder_counts.get(node, 1)
            max_count = max(self.folder_counts.values()) if self.folder_counts else 1
            size = 6 + 12 * (count / max(1, max_count))
            if node == self.root_name:
                size = max(size, 14)

            # Hit radius = node size + buffer
            # Buffer is larger when zoomed out for easier clicking on small targets
            buffer = 8 / self.zoom_scale
            hit_radius = size + buffer
            if (x - nx) ** 2 + (y - ny) ** 2 <= hit_radius ** 2:
                return node

        return None

    def drill_down(self, folder_path: str):
        """Drill down into a specific folder, making it the new root."""
        if not self.full_file_index:
            return

        # Add current root to history for back navigation
        if self.current_root_path:
            self.navigation_history.append(self.current_root_path)
        else:
            self.navigation_history.append(None)  # Original root

        self.current_root_path = folder_path

        # Filter files to only those under this folder
        filtered_index = self._filter_files_for_folder(folder_path)
        self.build_graph(filtered_index, preserve_full_index=True)

        # Reset zoom/pan and fit to view after a short delay (let layout settle)
        self.reset_view()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.fit_to_view)

        # Emit navigation changed signal
        self.navigation_changed.emit(self._get_breadcrumb_path())
        self.node_clicked.emit(folder_path)

    def navigate_back(self):
        """Go back to parent folder in navigation history."""
        if not self.navigation_history:
            return

        previous = self.navigation_history.pop()
        self.current_root_path = previous

        if previous is None:
            # Back to original root
            self.build_graph(self.full_file_index, preserve_full_index=True)
        else:
            filtered_index = self._filter_files_for_folder(previous)
            self.build_graph(filtered_index, preserve_full_index=True)

        # Reset zoom/pan and fit to view
        self.reset_view()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.fit_to_view)

        self.navigation_changed.emit(self._get_breadcrumb_path())

    def navigate_to_root(self):
        """Navigate back to the original root."""
        self.navigation_history.clear()
        self.current_root_path = None
        if self.full_file_index:
            self.build_graph(self.full_file_index, preserve_full_index=True)

        # Reset zoom/pan and fit to view
        self.reset_view()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.fit_to_view)

        self.navigation_changed.emit(self._get_breadcrumb_path())

    def _filter_files_for_folder(self, folder_path: str) -> Dict:
        """Filter the full file index to only include files under a specific folder."""
        if not self.full_file_index:
            debug_print(f"[DrillDown] No full_file_index available")
            return {'files': [], 'root': folder_path}

        # Normalize folder path (use forward slashes consistently)
        folder_path_normalized = folder_path.replace('\\', '/')
        if folder_path_normalized.endswith('/'):
            folder_path_normalized = folder_path_normalized[:-1]

        debug_print(f"[DrillDown] Looking for files under: '{folder_path_normalized}'")

        filtered_files = []
        total_files = len(self.full_file_index.get('files', []))

        for f in self.full_file_index.get('files', []):
            file_path = f.get('path', '').replace('\\', '/')

            # Check if file is under this folder (direct match or subfolder)
            # Need to check for exact prefix with separator to avoid partial matches
            if file_path.startswith(folder_path_normalized + '/'):
                # Make path relative to new root
                relative_path = file_path[len(folder_path_normalized)+1:]
                filtered_file = f.copy()
                filtered_file['path'] = relative_path
                filtered_files.append(filtered_file)
            elif file_path == folder_path_normalized:
                # File is at exactly this path (shouldn't happen for folders, but handle it)
                filtered_file = f.copy()
                filtered_file['path'] = f.get('name', '')
                filtered_files.append(filtered_file)

        debug_print(f"[DrillDown] Filtering for '{folder_path}': found {len(filtered_files)} of {total_files} files")

        return {
            'files': filtered_files,
            'root': folder_path
        }

    def _get_breadcrumb_path(self) -> List[str]:
        """Get the current breadcrumb navigation path."""
        if not self.current_root_path:
            return [self.full_file_index.get('root', 'Root')] if self.full_file_index else ['Root']

        original_root = self.full_file_index.get('root', '') if self.full_file_index else ''
        parts = [Path(original_root).name or 'Root']

        # Add navigation history
        for hist in self.navigation_history:
            if hist:
                parts.append(Path(hist).name)

        # Add current
        if self.current_root_path:
            parts.append(Path(self.current_root_path).name)

        return parts

    def set_highlighted_paths(self, paths: Set[str]):
        """Set paths to highlight (for search results)."""
        self.highlighted_paths = paths
        self.update()

    def clear_highlights(self):
        """Clear all highlighted paths."""
        self.highlighted_paths.clear()
        self.update()

