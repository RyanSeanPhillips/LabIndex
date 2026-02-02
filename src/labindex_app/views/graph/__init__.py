"""
Graph visualization package - Modern QGraphicsView-based implementation.

This package provides a scalable, interactive graph visualization with:
- Level of Detail (LOD) for huge datasets
- Tree and Force-directed layouts
- Filtering with fade mode
- Right-click context menu for all controls
"""

from .canvas import ModernGraphCanvas
from .scene import GraphScene

__all__ = ["ModernGraphCanvas", "GraphScene"]
