"""
Edge QGraphicsItem for relationship visualization.

Renders curved Bezier edges between nodes with confidence-based styling.
"""

from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen

if TYPE_CHECKING:
    from ..style_manager import StyleManager


class EdgeItem(QGraphicsItem):
    """
    QGraphicsItem for rendering relationship edges between files.

    Features:
    - Curved Bezier lines
    - Color by relationship type
    - Opacity by confidence
    - Dashed lines for low confidence
    - Optional arrow heads
    """

    def __init__(
        self,
        edge_id: int,
        src_pos: QPointF,
        dst_pos: QPointF,
        relation_type: str = "notes_for",
        confidence: float = 1.0,
        evidence: Optional[str] = None,
        style_manager: Optional["StyleManager"] = None,
    ):
        super().__init__()

        self.edge_id = edge_id
        self._src_pos = src_pos
        self._dst_pos = dst_pos
        self.relation_type = relation_type
        self.confidence = confidence
        self.evidence = evidence
        self._style = style_manager

        # State
        self._selected = False
        self._highlighted = False
        self._opacity = 1.0

        # Compute bounding rect
        self._path: Optional[QPainterPath] = None
        self._update_path()

        # Tooltip
        self._update_tooltip()

        # Edges should be behind nodes
        self.setZValue(-1)

        # Don't intercept mouse events - allows panning through edges
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)

    def set_style_manager(self, style: "StyleManager"):
        """Set the style manager."""
        self._style = style
        self.update()

    def set_positions(self, src: QPointF, dst: QPointF):
        """Update edge positions."""
        if self._src_pos != src or self._dst_pos != dst:
            self.prepareGeometryChange()
            self._src_pos = src
            self._dst_pos = dst
            self._update_path()
            self.update()

    def _update_path(self):
        """Update the cached Bezier path."""
        self._path = QPainterPath()

        src = self._src_pos
        dst = self._dst_pos

        # Calculate control points for smooth curve
        dx = dst.x() - src.x()
        dy = dst.y() - src.y()

        # Control point offset (perpendicular to line, creates curve)
        # Longer edges get more curve
        import math
        dist = math.sqrt(dx*dx + dy*dy)
        curve_strength = min(50, dist * 0.3)

        # Perpendicular direction
        if dist > 0:
            px = -dy / dist * curve_strength
            py = dx / dist * curve_strength
        else:
            px, py = 0, 0

        # Control points
        mid_x = (src.x() + dst.x()) / 2
        mid_y = (src.y() + dst.y()) / 2
        ctrl = QPointF(mid_x + px, mid_y + py)

        self._path.moveTo(src)
        self._path.quadTo(ctrl, dst)

    def _update_tooltip(self):
        """Update tooltip text."""
        lines = [
            f"🔗 {self.relation_type.replace('_', ' ').title()}",
            f"Confidence: {self.confidence:.0%}",
        ]
        if self.evidence:
            # Truncate long evidence
            ev = self.evidence[:100] + "..." if len(self.evidence) > 100 else self.evidence
            lines.append(f"Evidence: {ev}")
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

    # -------------------------------------------------------------------------
    # QGraphicsItem Interface
    # -------------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle for the edge."""
        if self._path is None:
            return QRectF()

        # Add padding for line width
        rect = self._path.boundingRect()
        padding = 5
        return rect.adjusted(-padding, -padding, padding, padding)

    def shape(self) -> QPainterPath:
        """Return the shape for hit testing."""
        if self._path is None:
            return QPainterPath()

        # Create a wider path for easier selection
        from PyQt6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(self._path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ):
        """Paint the edge."""
        if self._path is None or not self._style:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get view scale directly from painter's world transform for accurate scaling
        # This ensures we always use the current transform, avoiding timing issues
        transform = painter.worldTransform()
        view_scale = transform.m11()  # Horizontal scale factor
        if view_scale <= 0:
            view_scale = 1.0

        # Get pen from style manager
        pen = self._style.get_edge_pen(
            relation_type=self.relation_type,
            confidence=self.confidence,
        )

        # Adjust pen width to maintain constant visual thickness
        # When zoomed in (scale > 1), make pen thinner in scene coords
        # When zoomed out (scale < 1), make pen thicker in scene coords
        base_width = pen.widthF()
        adjusted_width = max(0.5, base_width / view_scale)
        pen.setWidthF(adjusted_width)

        # Apply additional opacity
        if self._opacity < 1.0:
            color = pen.color()
            color.setAlphaF(color.alphaF() * self._opacity)
            pen.setColor(color)

        # Highlight/selection effect
        if self._selected:
            pen.setWidthF(max(0.5, 3.0 / view_scale))
            pen.setColor(self._style.style.selection_color)
        elif self._highlighted:
            pen.setWidthF(max(0.5, 2.0 / view_scale))
            color = pen.color()
            color.setAlpha(255)  # Full opacity when highlighted
            pen.setColor(color)

        # Use cosmetic pen for truly constant pixel width regardless of transform
        pen.setCosmetic(True)
        # Cosmetic pens use pixel widths, so use the base width directly
        pen.setWidthF(base_width)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)

        # Draw arrow head at destination (for relationship edges with higher confidence)
        # Tree edges don't get arrow heads - they're structural, not directional
        if self.confidence >= 0.5 and self.relation_type != "tree":
            self._draw_arrow_head(painter, pen.color(), view_scale)

    def _draw_arrow_head(self, painter: QPainter, color: QColor, view_scale: float = 1.0):
        """Draw an arrow head at the destination end."""
        if self._path is None:
            return

        import math

        # Get direction at end of path
        dst = self._dst_pos
        # Approximate direction from second-to-last point
        t = 0.9
        pt = self._path.pointAtPercent(t)
        dx = dst.x() - pt.x()
        dy = dst.y() - pt.y()
        angle = math.atan2(dy, dx)

        # Arrow parameters - scale inversely with view scale for constant visual size
        arrow_size = 8.0 / view_scale
        arrow_angle = math.pi / 6  # 30 degrees

        # Arrow points
        p1 = QPointF(
            dst.x() - arrow_size * math.cos(angle - arrow_angle),
            dst.y() - arrow_size * math.sin(angle - arrow_angle)
        )
        p2 = QPointF(
            dst.x() - arrow_size * math.cos(angle + arrow_angle),
            dst.y() - arrow_size * math.sin(angle + arrow_angle)
        )

        # Draw filled arrow
        from PyQt6.QtGui import QBrush, QPolygonF
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        arrow = QPolygonF([dst, p1, p2])
        painter.drawPolygon(arrow)
