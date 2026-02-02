# LabIndex Graph Visualization - Session Notes
**Date:** 2026-01-29

## Summary

We implemented Phase 1 of the modern graph visualization system for LabIndex, replacing the custom QPainter-based `graph_canvas.py` with a new QGraphicsView-based implementation in `views/graph/`.

## Key Decisions Made

### 1. Architecture
- **QGraphicsView/QGraphicsScene** instead of QPainter for better performance and interaction handling
- **Parallel development** - Both old ("Classic") and new ("Modern") renderers available via toggle dropdown
- **MVVM pattern** - Scene manages items, Canvas manages view, existing GraphVM manages state

### 2. Two Types of Edges
- **Tree edges**: Parent-child folder connections (visible by default, toggleable via right-click)
- **Relationship edges**: Cross-reference links from linker (controlled by "Links" checkbox)

### 3. Layout Modes
- **Tree**: Hierarchical layout scaled to fit viewport
- **Force**: Tree-constrained force-directed (to be improved)
- **Radial**: Concentric rings from root

### 4. File Positioning
- Files are "leaves" attached to parent folders
- Fan out in an arc shape with seeded randomness for consistency
- Matches the classic canvas behavior

### 5. Controls
- **Right-click context menu** for layout, direction, tree edges toggle
- **Toolbar** dropdowns for layout, direction, color mode
- **Checkboxes** for Files, Labels, Links

## Files Created

```
src/labindex_app/views/graph/
├── __init__.py              # Exports ModernGraphCanvas, GraphScene
├── canvas.py                # QGraphicsView with pan/zoom/layout (~750 lines)
├── scene.py                 # QGraphicsScene managing items (~500 lines)
├── style_manager.py         # Colors, sizes, LOD logic (~300 lines)
└── items/
    ├── __init__.py
    ├── folder_item.py       # Folder nodes with labels, badges
    ├── file_item.py         # File nodes with type icons
    └── edge_item.py         # Bezier curve edges
```

## Files Modified

- **main_window.py**: Added toggle dropdown, QStackedWidget for both canvases, wired signals

## Current State of Implementation

### Working ✅
- Toggle between Classic/Modern
- Tree layout scaled to viewport
- Radial layout
- Tree edges (parent-child connections)
- File type icons
- Pan and zoom (smooth)
- Right-click context menu
- LOD (files hide when zoomed out)
- File fan positioning

### Needs Work 🔶
- Relationship edges (may need debugging)
- Animations

## COMPLETED (Session 3) ✅

### Improved LOD System
- **6 granular LOD levels** instead of 4:
  - CLUSTERS (scale < 0.1): Supernodes only
  - FOLDERS (0.1-0.3): Folders only, no labels
  - FOLDERS_LABELS (0.3-0.5): Folders with labels, no files
  - FILES (0.5-0.8): Files visible as dots, no file labels
  - FILES_LABELS (0.8-1.2): Files with labels
  - DETAIL (> 1.2): Full detail
- **Folder labels appear BEFORE files** (priority to structure)
- **File labels appear LAST** (least important)

### Visual Distinction: Files vs Folders
- **Files are now CIRCLES** (colored dots), folders are RECTANGLES
- **Files always use category colors**:
  - Red (231, 76, 60) - data files (.abf, .csv, .mat...)
  - Blue (52, 152, 219) - documents (.docx, .pdf...)
  - Purple (155, 89, 182) - code (.py, .ipynb...)
  - Orange (230, 126, 34) - presentations (.pptx)
  - Green (46, 204, 113) - spreadsheets (.xlsx)
- **Folders use uniform golden color** by default
- **Default color mode changed to CATEGORY**

## COMPLETED (Session 2) ✅

### Phase 5: Filtering + Fade Mode
- **FilterState dataclass** added to `scene.py` - tracks enabled categories, fade opacity, hide mode
- **GraphScene.set_filter()** - applies category-based filtering with branch-aware parent highlighting
- **GraphScene.clear_filter()** - restores all items to full visibility
- **ModernGraphCanvas.set_file_type_filter()** - public API for setting filter
- **ModernGraphCanvas.toggle_category_filter()** - toggle individual categories
- **Context menu "Filter by Type"** submenu - UI for selecting presentations, data, documents, code, etc.

### Phase 3: Real Force-Directed Layout
- **Improved physics simulation** with:
  1. Strong parent-child springs (maintain hierarchy)
  2. Sibling repulsion (spread out nodes at same depth)
  3. **Filtered file attraction** - files matching filter attract each other, creating visual clusters!
- 100 iterations with temperature cooling for stable layout

### Phase 2: ClusterItem (Optional)
- Created `cluster_item.py` for LOD0 supernodes
- Shows file count and folder name
- Ready for integration when LOD0 is needed

### Phase 4: Filter Dialog (Optional)
- Created `graph_filter_dialog.py` with:
  - Checkbox for each file category
  - Select All / Clear All buttons
  - Fade opacity slider (5-50%)
  - Hide completely option
  - Apply button emits `filter_changed` signal

## Remaining Phases (Per Plan)

### Phase 2: LOD System (Partial)
- ClusterItem for LOD0 supernodes not implemented
- Basic file show/hide based on zoom works

### Phase 3: Force-Directed Layout
- Needs proper physics simulation
- Should cluster related files when filtered

### Phase 4: Context Menu + Dialogs
- Basic menu done
- Need appearance dialog and filter dialog

### Phase 5: Filtering + Fade Mode ← USER PRIORITY
- Filter by file type (PowerPoint, data, code, etc.)
- Fade mode (non-matching at 20% opacity)
- Branch-aware (keep parent folders visible)
- Force layout should cluster filtered files

### Phase 6-8: Data Provider, Polish, Cutover

## User's Vision for Filtering

> "This could be very cool if this works in the force layout so that the tree dynamically moves/adjusts to highlight where these specific files are."

The idea: When filtering to (e.g.) PowerPoint files:
1. Non-matching files/folders fade to 20% opacity
2. In Force layout, filtered files attract each other
3. Creates visual clusters showing where those files are in the tree

## Technical Details for Future Reference

### File Categories (from domain/models.py)
```python
class FileCategory(Enum):
    DOCUMENTS = "documents"
    SPREADSHEETS = "spreadsheets"
    PRESENTATIONS = "presentations"
    DATA = "data"
    CODE = "code"
    IMAGES = "images"
    VIDEO = "video"
    ARCHIVES = "archives"
    OTHER = "other"
```

### LOD Thresholds (style_manager.py)
```python
LOD_THRESHOLDS = [0.15, 0.4, 1.0]
# < 0.15: Clusters only
# 0.15-0.4: Folders only
# 0.4-1.0: Files visible (no labels)
# > 1.0: Full detail with labels
```

### Key Scene Data Structures
```python
self._folder_items: Dict[int, FolderItem]  # node_id -> item
self._file_items: Dict[int, FileItem]       # file_id -> item
self._tree_edge_items: List[EdgeItem]       # Parent-child edges
self._edge_items: Dict[int, EdgeItem]       # Relationship edges
self._path_to_folder: Dict[str, FolderItem] # For lookups
self._path_to_file: Dict[str, FileItem]
self._nodes: Dict[int, GraphNode]           # Node data
self._children: Dict[int, List[int]]        # parent_id -> child_ids
self._parent: Dict[int, int]                # child_id -> parent_id
self._file_data: Dict[int, Dict]            # file_id -> file info dict
```

### GraphVM Signals
```python
file_index_changed = pyqtSignal()
settings_changed = pyqtSignal()
navigation_changed = pyqtSignal()
highlights_changed = pyqtSignal()
links_changed = pyqtSignal()
```

## Environment

- **Python env**: `plethapp` conda
- **Path**: `C:\Users\rphil2\AppData\Local\miniforge3\envs\plethapp\python.exe`
- **Working dir**: `C:\Users\rphil2\Dropbox\python scripts\breath_analysis\LabIndex`
- **Test command**: `python -c "import sys; sys.path.insert(0, 'src'); from labindex_app.views.graph import ModernGraphCanvas"`
