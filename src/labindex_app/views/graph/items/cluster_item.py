"""
Cluster node for LOD0 - represents a collapsed subtree.
"""

from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QBrush, QPen, QFontMetrics

if TYPE_CHECKING:
    from ..style_manager import StyleManager


class ClusterItem(QGraphicsItem):
    """
    QGraphicsItem for rendering a collapsed cluster of nodes.

    Shown at LOD0 (very zoomed out) to represent large subtrees.
    """

    def __init__(
        self,
        cluster_id: int,
        name: str,
        path: str,
        total_files: int,
        total_folders: int,
        dominant_category: str = "other",
        style_manager: Optional["StyleManager"] = None,
    ):
        super().__init__()

        self.cluster_id = cluster_id
        self.name = name
        self.path = path
        self.total_files = total_files
        self.total_folders = total_folders
        self.dominant_category = dominant_category
        self._style = style_manager

        # Size based on content
        self._size = 30 + min(20, total_files // 50)

        # State
        self._hovered = False

        self.setAcceptHoverEvents(True)
        self.setToolTip(f"{name}\n{total_folders} folders, {total_files} files")

    def set_style_manager(self, style: "StyleManager"):
        """Set the style manager."""
        self._style = style
        self.update()

    def boundingRect(self) -> QRectF:
        size = self._size
        return QRectF(-size/2, -size/2, size, size + 20)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        if not self._style:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get color based on dominant category
        color = self._style.get_node_color(category=self.dominant_category, depth=0)

        # Draw as larger circle
        half = self._size / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(0, 0), half, half)

        # Draw count in center
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = self._style.get_font()
        font.setBold(True)
        painter.setFont(font)

        text = str(self.total_files) if self.total_files < 1000 else f"{self.total_files//1000}k"
        painter.drawText(QRectF(-half, -half, self._size, self._size),
                        Qt.AlignmentFlag.AlignCenter, text)

        # Draw label below
        painter.setPen(self._style.get_text_pen())
        font.setBold(False)
        painter.setFont(font)
        fm = QFontMetrics(font)
        label = fm.elidedText(self.name, Qt.TextElideMode.ElideMiddle, 60)
        painter.drawText(QRectF(-30, half + 2, 60, 16),
                        Qt.AlignmentFlag.AlignHCenter, label)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
