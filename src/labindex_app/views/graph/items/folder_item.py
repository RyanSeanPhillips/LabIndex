"""
Folder node QGraphicsItem.

Renders folder nodes as rounded rectangles with optional labels and rollup badges.
"""

from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QFontMetrics

if TYPE_CHECKING:
    from ..style_manager import StyleManager


class FolderItem(QGraphicsItem):
    """
    QGraphicsItem for rendering a folder node.

    Features:
    - Rounded rectangle shape
    - Size scales with file count
    - Color based on category/depth/size mode
    - Optional label (shown at high LOD)
    - Selection highlight ring
    - Rollup badge showing file count
    """

    def __init__(
        self,
        node_id: int,
        name: str,
        path: str,
        category: str = "other",
        depth: int = 0,
        file_count: int = 0,
        total_size_kb: int = 0,
        is_root: bool = False,
        style_manager: Optional["StyleManager"] = None,
    ):
        super().__init__()

        self.node_id = node_id
        self.name = name
        self.path = path
        self.category = category
        self.depth = depth
        self.file_count = file_count
        self.total_size_kb = total_size_kb
        self.is_root = is_root
        self._style = style_manager

        # State
        self._selected = False
        self._highlighted = False
        self._hovered = False
        self._opacity = 1.0
        self._show_label = True

        # Cached size (will be set by style manager)
        self._size = 12.0
        self._update_size()

        # Enable hover events and selection
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # Semantic zoom: item stays same screen size regardless of view scale
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

        # Tooltip
        self._update_tooltip()

    def set_style_manager(self, style: "StyleManager"):
        """Set the style manager and update appearance."""
        self._style = style
        self._update_size()
        self.update()

    def _update_size(self):
        """Update cached size from style manager."""
        if self._style:
            self._size = self._style.get_node_size(self.file_count, is_folder=True)
        else:
            self._size = 12.0

    def _update_tooltip(self):
        """Update tooltip text."""
        lines = [
            f"📁 {self.name}",
            f"Path: {self.path}",
            f"Files: {self.file_count}",
        ]
        if self.total_size_kb > 0:
            if self.total_size_kb > 1024:
                lines.append(f"Size: {self.total_size_kb / 1024:.1f} MB")
            else:
                lines.append(f"Size: {self.total_size_kb} KB")
        self.setToolTip("\n".join(lines))

    # -------------------------------------------------------------------------
    # State Properties
    # -------------------------------------------------------------------------

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        if self._selected != value:
            self._selected = value
            self.update()

    @property
    def highlighted(self) -> bool:
        return self._highlighted

    @highlighted.setter
    def highlighted(self, value: bool):
        if self._highlighted != value:
            self._highlighted = value
            self.update()

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float):
        if self._opacity != value:
            self._opacity = max(0.0, min(1.0, value))
            self.update()

    @property
    def show_label(self) -> bool:
        return self._show_label

    @show_label.setter
    def show_label(self, value: bool):
        if self._show_label != value:
            self._show_label = value
            self.update()

    # -------------------------------------------------------------------------
    # QGraphicsItem Interface
    # -------------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle for the item."""
        # Include some padding for selection ring and label
        padding = 4
        size = self._size + padding * 2

        # If showing label, extend downward
        if self._show_label and self._style:
            font = self._style.get_font()
            fm = QFontMetrics(font)
            label_height = fm.height() + 4
            return QRectF(-size/2, -size/2, size, size + label_height)

        return QRectF(-size/2, -size/2, size, size)

    def shape(self) -> QPainterPath:
        """Return the shape for hit testing (rounded rect)."""
        path = QPainterPath()
        half = self._size / 2
        path.addRoundedRect(-half, -half, self._size, self._size, 3, 3)
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ):
        """Paint the folder node."""
        if not self._style:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        half = self._size / 2
        rect = QRectF(-half, -half, self._size, self._size)

        # Get color from style manager
        color = self._style.get_node_color(
            category=self.category,
            depth=self.depth,
            size_kb=self.total_size_kb,
            is_root=self.is_root,
        )

        # Apply opacity
        brush = self._style.get_node_brush(color, self._opacity)
        pen = self._style.get_node_pen(self._selected, self._highlighted)

        # Draw selection/highlight ring first (behind node)
        if self._selected or self._highlighted:
            ring_rect = rect.adjusted(-3, -3, 3, 3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(ring_rect, 5, 5)

        # Draw the folder node (rounded rectangle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        painter.drawRoundedRect(rect, 3, 3)

        # Draw hover highlight
        if self._hovered:
            hover_color = QColor(255, 255, 255, 50)
            painter.setBrush(hover_color)
            painter.drawRoundedRect(rect, 3, 3)

        # Draw file count badge (top-right corner) if there are files
        if self.file_count > 0 and self._style.current_lod.value >= 2:
            self._draw_count_badge(painter, rect)

        # Draw label below node
        if self._show_label and self._style.should_show_folder_labels():
            self._draw_label(painter, rect)

    def _draw_count_badge(self, painter: QPainter, rect: QRectF):
        """Draw a small badge showing file count."""
        badge_size = 8
        badge_x = rect.right() - badge_size / 2
        badge_y = rect.top() - badge_size / 2

        # Badge background
        badge_color = QColor(80, 80, 80, 200)
        painter.setBrush(badge_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(badge_x, badge_y), badge_size, badge_size)

        # Badge text (only show if small enough to fit)
        if self.file_count < 1000:
            font = self._style.get_font()
            font.setPointSize(6)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            text = str(self.file_count) if self.file_count < 100 else "99+"
            painter.drawText(
                QRectF(badge_x - badge_size, badge_y - badge_size/2, badge_size * 2, badge_size),
                Qt.AlignmentFlag.AlignCenter,
                text
            )

    def _draw_label(self, painter: QPainter, rect: QRectF):
        """Draw the folder name label below the node."""
        font = self._style.get_font()
        painter.setFont(font)
        painter.setPen(self._style.get_text_pen())

        # Truncate long names
        fm = QFontMetrics(font)
        max_width = max(60, self._size * 4)
        text = fm.elidedText(self.name, Qt.TextElideMode.ElideMiddle, int(max_width))

        # Position below node
        text_rect = QRectF(
            -max_width / 2,
            rect.bottom() + 2,
            max_width,
            fm.height()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter, text)

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)
