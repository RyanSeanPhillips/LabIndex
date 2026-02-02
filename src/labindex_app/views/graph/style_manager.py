"""
Style manager for graph visualization.

Centralizes all colors, sizes, fonts, and styling logic.
Ported from graph_canvas.py with enhancements for LOD support.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPen, QBrush


class ColorMode(Enum):
    """Color modes for node rendering."""
    UNIFORM = "Uniform"
    CATEGORY = "Category"
    DEPTH = "Depth"
    SIZE = "Size"


class LODLevel(Enum):
    """Level of detail bands."""
    CLUSTERS = 0       # Supernodes only (scale < 0.2)
    FOLDERS = 1        # Folders only, no files (scale 0.2 - 0.4)
    FOLDERS_LABELS = 2 # Folders with labels, no files (scale 0.4 - 0.6)
    FILES = 3          # Files visible, no file labels (scale 0.6 - 0.9)
    FILES_LABELS = 4   # Files with labels (scale 0.9 - 1.5)
    DETAIL = 5         # Full detail with all labels (scale > 1.5)


@dataclass
class GraphStyle:
    """All styling parameters for the graph."""

    # Background
    bg_color: QColor = field(default_factory=lambda: QColor(20, 20, 20))

    # Node colors
    uniform_color: QColor = field(default_factory=lambda: QColor(255, 215, 100))  # Golden yellow
    root_color: QColor = field(default_factory=lambda: QColor(255, 200, 100))
    file_color: QColor = field(default_factory=lambda: QColor(120, 120, 120))  # Gray for files

    # Edge colors (brighter for visibility on dark background)
    edge_color: QColor = field(default_factory=lambda: QColor(150, 150, 150))
    file_edge_color: QColor = field(default_factory=lambda: QColor(100, 100, 100))

    # Text
    text_color: QColor = field(default_factory=lambda: QColor(200, 200, 200))

    # Selection/highlight
    selection_color: QColor = field(default_factory=lambda: QColor(100, 200, 255))
    highlight_color: QColor = field(default_factory=lambda: QColor(255, 215, 0))  # Gold

    # Sizes
    node_size: int = 12        # Base folder node radius
    file_size: int = 8         # Base file node size
    font_size: int = 9         # Label font size

    # Spacing
    node_spacing: int = 60
    layer_spacing: int = 80


class StyleManager:
    """Manages all styling for the graph visualization."""

    # Category colors
    CATEGORY_COLORS: Dict[str, QColor] = {
        'data': QColor(231, 76, 60),       # Red
        'documents': QColor(52, 152, 219),  # Blue
        'spreadsheets': QColor(46, 204, 113),  # Green
        'images': QColor(243, 156, 18),    # Orange
        'code': QColor(155, 89, 182),      # Purple
        'slides': QColor(230, 126, 34),    # Dark orange
        'presentations': QColor(230, 126, 34),  # Dark orange (alias)
        'video': QColor(241, 196, 15),     # Yellow
        'archives': QColor(149, 165, 166),  # Gray
        'other': QColor(127, 140, 141),    # Dark gray
    }

    # Depth colors (rainbow progression)
    DEPTH_COLORS = [
        QColor(255, 200, 100),  # Depth 0 - gold
        QColor(79, 195, 247),   # Depth 1 - cyan
        QColor(144, 238, 144),  # Depth 2 - light green
        QColor(255, 182, 193),  # Depth 3 - pink
        QColor(255, 218, 185),  # Depth 4 - peach
        QColor(221, 160, 221),  # Depth 5 - plum
        QColor(176, 224, 230),  # Depth 6 - powder blue
        QColor(255, 255, 224),  # Depth 7 - light yellow
    ]

    # Relationship edge colors
    RELATION_COLORS: Dict[str, QColor] = {
        'notes_for': QColor(100, 200, 100),     # Green
        'analysis_of': QColor(100, 150, 255),   # Blue
        'same_animal': QColor(255, 180, 100),   # Orange
        'mentions': QColor(200, 150, 255),      # Purple
        'same_session': QColor(255, 255, 100),  # Yellow
        'tree': QColor(80, 80, 80),             # Dark gray for tree structure
        'file': QColor(60, 60, 60),             # Darker gray for folder-to-file edges
    }

    # LOD thresholds (scale values) - tuned for semantic zoom
    # With semantic zoom, scale affects spacing, not item size
    # - Below 0.2: Clusters only (very zoomed out, nodes overlap)
    # - 0.2-0.4: Folders only, no labels (still crowded)
    # - 0.4-0.6: Folders with labels, no files
    # - 0.6-0.9: Files visible as dots, no file labels
    # - 0.9-1.5: Files with labels
    # - Above 1.5: Full detail
    LOD_THRESHOLDS = [0.2, 0.4, 0.6, 0.9, 1.5]

    def __init__(self, style: Optional[GraphStyle] = None):
        self.style = style or GraphStyle()
        self._color_mode = ColorMode.CATEGORY  # Default to Category for visual distinction
        self._current_lod = LODLevel.FOLDERS
        self._font = QFont("Segoe UI", self.style.font_size)
        self._view_scale = 1.0  # Current view scale for edge width adjustment

    @property
    def view_scale(self) -> float:
        """Current view scale (used for constant-width edges)."""
        return self._view_scale

    @view_scale.setter
    def view_scale(self, value: float):
        self._view_scale = max(0.01, value)

    @property
    def color_mode(self) -> ColorMode:
        return self._color_mode

    @color_mode.setter
    def color_mode(self, mode: ColorMode):
        self._color_mode = mode

    @property
    def current_lod(self) -> LODLevel:
        return self._current_lod

    def update_lod_from_scale(self, scale: float) -> bool:
        """
        Update LOD based on current scale.

        Returns:
            True if LOD changed (items need update)
        """
        if scale < self.LOD_THRESHOLDS[0]:
            new_lod = LODLevel.CLUSTERS
        elif scale < self.LOD_THRESHOLDS[1]:
            new_lod = LODLevel.FOLDERS
        elif scale < self.LOD_THRESHOLDS[2]:
            new_lod = LODLevel.FOLDERS_LABELS
        elif scale < self.LOD_THRESHOLDS[3]:
            new_lod = LODLevel.FILES
        elif scale < self.LOD_THRESHOLDS[4]:
            new_lod = LODLevel.FILES_LABELS
        else:
            new_lod = LODLevel.DETAIL

        if new_lod != self._current_lod:
            self._current_lod = new_lod
            return True
        return False

    # -------------------------------------------------------------------------
    # Color Methods
    # -------------------------------------------------------------------------

    def get_node_color(
        self,
        category: str = "other",
        depth: int = 0,
        size_kb: int = 0,
        is_root: bool = False,
    ) -> QColor:
        """Get the color for a node based on current color mode."""
        if is_root:
            return self.style.root_color

        if self._color_mode == ColorMode.UNIFORM:
            return self.style.uniform_color

        elif self._color_mode == ColorMode.CATEGORY:
            return self.CATEGORY_COLORS.get(category, self.CATEGORY_COLORS['other'])

        elif self._color_mode == ColorMode.DEPTH:
            idx = min(depth, len(self.DEPTH_COLORS) - 1)
            return self.DEPTH_COLORS[idx]

        elif self._color_mode == ColorMode.SIZE:
            # Size gradient: small=blue, large=red
            # Normalize size (assume 0-10MB range for most files)
            normalized = min(1.0, size_kb / 10240)
            r = int(50 + normalized * 200)
            g = int(100 - normalized * 50)
            b = int(200 - normalized * 150)
            return QColor(r, g, b)

        return self.style.uniform_color

    def get_file_color(self, category: str = "other") -> QColor:
        """Get color for a file node - always uses category colors for visual distinction."""
        # Files always use category colors to distinguish them from folders
        return self.CATEGORY_COLORS.get(category, self.style.file_color)

    def get_edge_color(self, relation_type: Optional[str] = None) -> QColor:
        """Get color for an edge."""
        if relation_type and relation_type in self.RELATION_COLORS:
            return self.RELATION_COLORS[relation_type]
        return self.style.edge_color

    # -------------------------------------------------------------------------
    # Size Methods
    # -------------------------------------------------------------------------

    def get_node_size(self, file_count: int = 0, is_folder: bool = True) -> float:
        """Get node size, optionally scaled by file count."""
        base = self.style.node_size if is_folder else self.style.file_size

        if is_folder and file_count > 0:
            # Scale folder size by file count (logarithmic)
            import math
            scale = 1.0 + 0.3 * math.log10(max(1, file_count))
            return base * min(scale, 2.5)  # Cap at 2.5x

        return base

    def get_font_size(self) -> int:
        """Get font size for current LOD."""
        if self._current_lod == LODLevel.DETAIL:
            return self.style.font_size
        elif self._current_lod == LODLevel.FILES:
            return max(6, self.style.font_size - 2)
        return self.style.font_size

    def get_font(self) -> QFont:
        """Get font for labels."""
        font = QFont("Segoe UI", self.get_font_size())
        return font

    # -------------------------------------------------------------------------
    # LOD Visibility
    # -------------------------------------------------------------------------

    def should_show_files(self) -> bool:
        """Whether files should be visible at current LOD."""
        return self._current_lod.value >= LODLevel.FILES.value

    def should_show_file_labels(self) -> bool:
        """Whether file labels should be visible at current LOD."""
        return self._current_lod.value >= LODLevel.FILES_LABELS.value

    def should_show_labels(self) -> bool:
        """Whether all labels should be visible at current LOD (legacy)."""
        return self._current_lod == LODLevel.DETAIL

    def should_show_folder_labels(self) -> bool:
        """Whether folder labels should be visible at current LOD."""
        # Folder labels appear earlier than file labels
        return self._current_lod.value >= LODLevel.FOLDERS_LABELS.value

    # -------------------------------------------------------------------------
    # Pen/Brush Helpers
    # -------------------------------------------------------------------------

    def get_node_pen(self, selected: bool = False, highlighted: bool = False) -> QPen:
        """Get pen for drawing node outline."""
        if selected:
            return QPen(self.style.selection_color, 2)
        elif highlighted:
            return QPen(self.style.highlight_color, 2)
        return QPen(Qt.PenStyle.NoPen)

    def get_node_brush(self, color: QColor, opacity: float = 1.0) -> QBrush:
        """Get brush for filling node."""
        if opacity < 1.0:
            color = QColor(color)
            color.setAlphaF(opacity)
        return QBrush(color)

    def get_edge_pen(
        self,
        relation_type: Optional[str] = None,
        confidence: float = 1.0,
        is_file_edge: bool = False,
    ) -> QPen:
        """Get pen for drawing edges."""
        # Tree edges are subtle structural lines
        is_tree_edge = relation_type == "tree"

        if is_file_edge:
            color = self.style.file_edge_color
        elif is_tree_edge:
            color = self.RELATION_COLORS.get('tree', QColor(80, 80, 80))
        else:
            color = self.get_edge_color(relation_type)

        # Confidence affects alpha (not for tree edges)
        if confidence < 1.0 and not is_tree_edge:
            color = QColor(color)
            alpha = int(80 + confidence * 175)  # 80-255 range
            color.setAlpha(alpha)

        # Tree edges are thinner, relationship edges are bolder
        if is_tree_edge:
            width = 1.0
        elif is_file_edge:
            width = 1.5
        else:
            width = 2.0
        pen = QPen(color, width)

        # Dashed line for low confidence
        if confidence < 0.5:
            pen.setStyle(Qt.PenStyle.DashLine)

        return pen

    def get_text_pen(self) -> QPen:
        """Get pen for drawing text."""
        return QPen(self.style.text_color)
