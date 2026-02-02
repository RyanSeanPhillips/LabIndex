"""
File node QGraphicsItem.

Renders file nodes with category-specific icons.
"""

from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QBrush, QPen, QPolygonF, QFontMetrics

if TYPE_CHECKING:
    from ..style_manager import StyleManager


# Extension to icon type mapping
EXTENSION_ICONS = {
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
    # Presentations
    '.pptx': 'presentation', '.ppt': 'presentation', '.odp': 'presentation',
    # Archives
    '.zip': 'archive', '.tar': 'archive', '.gz': 'archive', '.7z': 'archive',
    '.rar': 'archive',
}


class FileItem(QGraphicsItem):
    """
    QGraphicsItem for rendering a file node.

    Features:
    - Category-specific icons (spreadsheet, code, data, etc.)
    - Size based on file size
    - Color based on category
    - Optional label (shown at high LOD)
    - Selection highlight ring
    """

    def __init__(
        self,
        file_id: int,
        name: str,
        path: str,
        category: str = "other",
        size_kb: int = 0,
        style_manager: Optional["StyleManager"] = None,
    ):
        super().__init__()

        self.file_id = file_id
        self.name = name
        self.path = path
        self.category = category
        self.size_kb = size_kb
        self._style = style_manager

        # Determine icon type from extension
        ext = '.' + name.split('.')[-1].lower() if '.' in name else ''
        self.icon_type = EXTENSION_ICONS.get(ext, 'file')

        # State
        self._selected = False
        self._highlighted = False
        self._hovered = False
        self._opacity = 1.0
        self._show_label = False
        self._show_icon = True

        # Cached size
        self._size = 8.0
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
            self._size = self._style.get_node_size(0, is_folder=False)
        else:
            self._size = 8.0

    def _update_tooltip(self):
        """Update tooltip text."""
        lines = [
            f"📄 {self.name}",
            f"Type: {self.category}",
        ]
        if self.size_kb > 0:
            if self.size_kb > 1024:
                lines.append(f"Size: {self.size_kb / 1024:.1f} MB")
            else:
                lines.append(f"Size: {self.size_kb} KB")
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

    @property
    def show_icon(self) -> bool:
        return self._show_icon

    @show_icon.setter
    def show_icon(self, value: bool):
        if self._show_icon != value:
            self._show_icon = value
            self.update()

    # -------------------------------------------------------------------------
    # QGraphicsItem Interface
    # -------------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle for the item."""
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
        """Return the shape for hit testing."""
        path = QPainterPath()
        half = self._size / 2
        path.addEllipse(-half, -half, self._size, self._size)
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ):
        """Paint the file node as a colored circle (distinct from folder rectangles)."""
        if not self._style:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get color from style manager - always use category color for files
        color = self._style.get_file_color(self.category)

        # Apply opacity
        if self._opacity < 1.0:
            color = QColor(color)
            color.setAlphaF(self._opacity)

        half = self._size / 2

        # Draw selection/highlight ring first
        if self._selected or self._highlighted:
            pen = self._style.get_node_pen(self._selected, self._highlighted)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), half + 3, half + 3)

        # Draw the file as a colored CIRCLE (distinct from folder rectangles)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(0, 0), half, half)

        # Draw a small inner highlight to give depth
        if self._size >= 6:
            highlight = QColor(255, 255, 255, 60)
            painter.setBrush(QBrush(highlight))
            painter.drawEllipse(QPointF(-half/4, -half/4), half/3, half/3)

        # Draw hover highlight
        if self._hovered:
            hover_color = QColor(255, 255, 255, 80)
            painter.setBrush(hover_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(0, 0), half, half)

        # Draw label below node (uses new should_show_file_labels)
        if self._show_label and self._style.should_show_file_labels():
            self._draw_label(painter)

    def _draw_icon(self, painter: QPainter, color: QColor):
        """Draw the file type icon."""
        size = int(self._size)
        half = size // 2
        x, y = 0, 0  # Center position

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))

        if self.icon_type == 'spreadsheet':
            # Grid pattern
            painter.drawRect(x - half, y - half, size, size)
            painter.setPen(QPen(color.darker(150)))
            third = size // 3
            painter.drawLine(x - half + third, y - half, x - half + third, y + half)
            painter.drawLine(x - half + 2*third, y - half, x - half + 2*third, y + half)
            painter.drawLine(x - half, y - half + third, x + half, y - half + third)
            painter.drawLine(x - half, y - half + 2*third, x + half, y - half + 2*third)

        elif self.icon_type == 'word':
            # Document with lines
            painter.drawRect(x - half, y - half, size, size)
            painter.setPen(QPen(color.darker(150)))
            for i in range(3):
                ly = y - half + int(size * 0.3) + i * int(size * 0.2)
                painter.drawLine(x - half + 2, ly, x + half - 2, ly)

        elif self.icon_type == 'pdf':
            # Red-tinted rectangle
            pdf_color = QColor(200, 50, 50) if color.lightness() > 128 else color
            painter.setBrush(QBrush(pdf_color))
            painter.drawRect(x - half, y - half, size, size)

        elif self.icon_type == 'text':
            # Simple rectangle with corner fold
            painter.drawRect(x - half, y - half, size, size)
            fold = size // 4
            painter.setBrush(QBrush(color.darker(120)))
            points = [
                QPointF(x + half - fold, y - half),
                QPointF(x + half, y - half + fold),
                QPointF(x + half - fold, y - half + fold),
            ]
            painter.drawPolygon(QPolygonF(points))

        elif self.icon_type == 'code':
            # Brackets < >
            painter.drawRect(x - half, y - half, size, size)
            painter.setPen(QPen(color.darker(150), 1))
            qh = half // 2
            # Left bracket <
            painter.drawLine(x - qh, y - qh, x - half + 2, y)
            painter.drawLine(x - half + 2, y, x - qh, y + qh)
            # Right bracket >
            painter.drawLine(x + qh, y - qh, x + half - 2, y)
            painter.drawLine(x + half - 2, y, x + qh, y + qh)

        elif self.icon_type == 'image':
            # Rectangle with mountain/sun
            painter.drawRect(x - half, y - half, size, size)
            painter.setBrush(QBrush(color.darker(130)))
            # Simple mountain shape
            mountain = [
                QPointF(x - half + 2, y + half - 2),
                QPointF(x, y),
                QPointF(x + half - 2, y + half - 2),
            ]
            painter.drawPolygon(QPolygonF(mountain))

        elif self.icon_type == 'data':
            # Cylinder/database shape
            ellipse_h = int(size * 0.4)
            rect_h = int(size * 0.6)
            painter.drawEllipse(x - half, y - half, size, ellipse_h)
            painter.drawRect(x - half, y - half + int(size * 0.2), size, rect_h)
            painter.drawEllipse(x - half, y + half - ellipse_h, size, ellipse_h)

        elif self.icon_type == 'video':
            # Play button triangle in rectangle
            painter.drawRect(x - half, y - half, size, size)
            painter.setBrush(QBrush(color.darker(150)))
            qh = half // 2
            points = [
                QPointF(x - qh, y - qh),
                QPointF(x - qh, y + qh),
                QPointF(x + qh, y),
            ]
            painter.drawPolygon(QPolygonF(points))

        elif self.icon_type == 'presentation':
            # Slide with title bar
            painter.drawRect(x - half, y - half, size, size)
            painter.setBrush(QBrush(color.darker(120)))
            painter.drawRect(x - half, y - half, size, int(size * 0.25))

        elif self.icon_type == 'archive':
            # Box with zipper
            painter.drawRect(x - half, y - half, size, size)
            painter.setPen(QPen(color.darker(150)))
            painter.drawLine(x, y - half, x, y + half)
            for i in range(3):
                ty = int(y - half + size * 0.25 + i * size * 0.25)
                painter.drawLine(x - 2, ty, x + 2, ty)

        else:  # 'file' - generic file
            painter.drawRect(x - half, y - half, size, size)

    def _draw_label(self, painter: QPainter):
        """Draw the file name label below the node."""
        font = self._style.get_font()
        font.setPointSize(max(6, font.pointSize() - 1))  # Slightly smaller for files
        painter.setFont(font)
        painter.setPen(self._style.get_text_pen())

        # Truncate long names
        fm = QFontMetrics(font)
        max_width = 50
        text = fm.elidedText(self.name, Qt.TextElideMode.ElideMiddle, max_width)

        # Position below node
        half = self._size / 2
        text_rect = QRectF(
            -max_width / 2,
            half + 2,
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
