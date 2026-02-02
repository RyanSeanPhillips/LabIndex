# LabIndex Implementation Plan

## Overview

This plan builds on the existing foundation to complete the Adaptive Linking System with a minimal chat-first UI that allows iterative testing and refinement.

**Approach**: Build in small, testable increments. Each phase produces a working system that can be tested before moving on.

**MVVM Compliance**: All changes follow the existing pattern - ViewModels hold state and emit signals, Services do business logic, Views display and handle input.

---

## Current State (Already Built)

```
✅ Handler system (base + registry)
✅ GenericTextHandler, GenericDataHandler, SpreadsheetHandler
✅ ContextReader (20-line context windows)
✅ MLTrainer (RandomForest/XGBoost)
✅ AdaptiveLinkingService (orchestration)
✅ FeatureExtractor (30+ features including timestamps)
✅ LinkAuditor (LLM validation)
✅ StrategyExplorerVM
✅ Persistent SQLite database
✅ ReadOnlyFS (safety layer)
✅ Timestamp features (just added)
```

---

## Phase 1: Minimal Chat UI (Foundation)
**Goal**: Get a working chat interface that can talk to Ollama

### 1.1 Create ChatWidget (PyQt6)
**File**: `src/labindex_app/views/chat_widget.py`

```python
class ChatWidget(QWidget):
    """Simple chat interface with message history."""
    message_sent = pyqtSignal(str)  # Emitted when user sends message

    Components:
    - QScrollArea with message bubbles
    - QLineEdit for input
    - Send button
    - Folder drop zone
```

### 1.2 Create ChatViewModel
**File**: `src/labindex_app/viewmodels/chat_vm.py`

```python
class ChatViewModel(BaseViewModel):
    """Manages chat state and LLM interaction."""

    Signals:
    - message_received(str, str)  # (role, content)
    - thinking_started()
    - thinking_finished()

    Methods:
    - send_message(text: str)
    - clear_history()

    Uses: OllamaLLM for responses
```

### 1.3 Create Main Window Shell
**File**: `src/labindex_app/views/main_window.py`

```python
class LabIndexMainWindow(QMainWindow):
    """Main window with chat panel."""

    Layout:
    ┌─────────────────────────────────────────┐
    │  LabIndex                    [Settings] │
    ├─────────────────────────────────────────┤
    │                                         │
    │           Chat Widget                   │
    │                                         │
    ├─────────────────────────────────────────┤
    │  [Folder drop zone]        [Send]       │
    └─────────────────────────────────────────┘
```

### 1.4 Test Checkpoint
```bash
python -m labindex_app.main
# Should open window, type message, get Ollama response
```

**Estimated effort**: Small (foundation exists)

---

## Phase 2: Folder Indexing via Chat
**Goal**: Drag a folder, see indexing progress, get summary

### 2.1 Add IndexingViewModel
**File**: `src/labindex_app/viewmodels/indexing_vm.py`

```python
class IndexingViewModel(BaseViewModel):
    """Manages folder indexing state."""

    Signals:
    - indexing_started(str)       # folder path
    - indexing_progress(int, int) # current, total
    - indexing_finished(dict)     # stats summary

    Methods:
    - start_indexing(folder_path: str)
    - cancel_indexing()

    Uses: CrawlerService, ExtractorService
```

### 2.2 Integrate with Chat
When user drops folder or types path:
1. ChatVM detects folder path
2. Triggers IndexingVM
3. Shows progress in chat
4. When done, summarizes findings

### 2.3 Add Progress Display
- Inline progress bar in chat
- "Indexed 245 files in 32 folders"
- "Found: 156 data files, 34 notes files"

### 2.4 Test Checkpoint
```bash
# Drag folder → see progress → get summary
```

**Estimated effort**: Small

---

## Phase 3: LLM Example Learning
**Goal**: User shows examples, LLM discovers patterns

### 3.1 Add ContentSignature Learning
**File**: `src/labindex_core/services/signature_learner.py`

```python
class SignatureLearner:
    """Learns content signatures from example files."""

    def learn_from_examples(
        self,
        example_file_ids: List[int],
        file_type_name: str
    ) -> ContentSignature:
        """
        LLM reads examples and discovers keywords.

        1. Read content from all example files
        2. Ask LLM: "What keywords are common?"
        3. Return structured ContentSignature
        """

    def propose_file_type(
        self,
        file_id: int
    ) -> Tuple[str, float]:
        """
        Score file against known signatures.
        Returns (best_type, confidence).
        """
```

### 3.2 Chat Integration for Examples
User flow:
```
User: "These are photometry notes"
       [selects 3 files in browse panel]

Bot:  Analyzing examples...

      I found these patterns:
      • Keywords: 415nm, 470nm, ROI, GCaMP, GRABNE
      • Mouse ID format: R-XXXXXX
      • Usually in same folder as FP_data*

      [✓ Looks right] [✗ Wrong] [Adjust...]
```

### 3.3 Store Learned Signatures
- Save to database as ContentSignature records
- Associate with file type name
- Track who created (user confirmed vs LLM proposed)

### 3.4 Test Checkpoint
```bash
# Show examples → LLM proposes patterns → user confirms
```

**Estimated effort**: Medium

---

## Phase 4: Re-extraction Pipeline
**Goal**: After learning patterns, re-extract metadata from matching files

### 4.1 Add Re-extraction Service
**File**: `src/labindex_core/services/reextractor.py`

```python
class ReextractionService:
    """Re-extracts metadata using learned patterns."""

    def identify_candidates(
        self,
        signature: ContentSignature
    ) -> List[FileRecord]:
        """Find files that might match this signature."""

    def reextract_batch(
        self,
        file_ids: List[int],
        signature: ContentSignature
    ) -> ReextractionStats:
        """
        Re-read files and extract enriched metadata.

        Stores results in ContentRecord.entities
        """
```

### 4.2 Enriched Metadata Storage
Add to ContentRecord.entities:
```python
{
    "wavelengths": [415, 470],
    "mouse_ids": ["R-266018", "R-266019"],
    "chambers": [1, 2],
    "data_refs": ["FP_data_0", "FP_data_1"],
    "experimenters": ["ANB", "JRS"],
    "file_type_hint": "photometry_notes",
    "signature_confidence": 0.87
}
```

### 4.3 Chat Integration
```
Bot:  I'll now scan 45 candidate notes files for these patterns.

      Progress: [████████░░] 80%

      Done! Enriched metadata for 38 files:
      • 28 matched photometry_notes pattern
      • 10 matched pleth_notes pattern
```

### 4.4 Test Checkpoint
```bash
# After learning → re-extraction runs → metadata enriched
```

**Estimated effort**: Medium

---

## Phase 5: Browse Panel
**Goal**: Add folder tree and search alongside chat

### 5.1 Create BrowsePanel
**File**: `src/labindex_app/views/browse_panel.py`

```python
class BrowsePanel(QWidget):
    """Folder tree and search results."""

    Components:
    - QLineEdit for search
    - QTreeView for folder structure
    - QListWidget for search results
    - File type filter chips

    Signals:
    - file_selected(int)          # file_id
    - files_selected(List[int])   # for bulk operations
```

### 5.2 Create BrowseViewModel
**File**: `src/labindex_app/viewmodels/browse_vm.py`

```python
class BrowseViewModel(BaseViewModel):
    """Manages browse/search state."""

    Properties:
    - folder_tree: TreeModel
    - search_results: List[FileRecord]
    - selected_file: Optional[FileRecord]

    Methods:
    - search(query: str)
    - filter_by_type(file_type: str)
    - select_file(file_id: int)
```

### 5.3 Update Main Window Layout
```
┌─────────────────────────────────────────────────────────────────┐
│  LabIndex                              [🔍 Search]    [Settings]│
├────────────────────┬────────────────────────────────────────────┤
│                    │                                            │
│  📁 Browse         │  💬 Chat                                   │
│  ─────────────     │                                            │
│                    │  [messages...]                             │
│  ▼ 📂 Experiments  │                                            │
│    ▼ 📂 GRABNE...  │                                            │
│      📊 data.abf   │                                            │
│      📝 notes.txt  │                                            │
│                    │                                            │
│  ─────────────     │                                            │
│  🏷️ Types         │                                            │
│  📊 Data (245)     │                                            │
│  📝 Notes (34)     │                                            │
│                    │                                            │
├────────────────────┴────────────────────────────────────────────┤
│  Type a message or drag a folder...                    [Send]   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Connect Browse to Chat
- Click file in tree → show details in chat
- Right-click → "Show this as example"
- Drag files to chat → "These are photometry notes"

### 5.5 Test Checkpoint
```bash
# Browse tree works, search works, connects to chat
```

**Estimated effort**: Medium

---

## Phase 6: Bulk Labeling
**Goal**: Label multiple files at once via tree selection

### 6.1 Add Bulk Label Dialog
**File**: `src/labindex_app/dialogs/bulk_label_dialog.py`

```python
class BulkLabelDialog(QDialog):
    """Assign labels to multiple files."""

    Features:
    - Shows selected files in tree
    - Dropdown for label type
    - Quick actions: "All .txt → notes"
    - Confirm button
```

### 6.2 Connect to Training Data
Each label action:
1. Updates file category in database
2. Creates training example for ML
3. Increments "pending labels" counter

### 6.3 Test Checkpoint
```bash
# Select files → bulk label → training data created
```

**Estimated effort**: Small

---

## Phase 7: ML Training Integration
**Goal**: Train button, auto-training, view performance

### 7.1 Add TrainingPanel
**File**: `src/labindex_app/views/training_panel.py`

```python
class TrainingPanel(QWidget):
    """ML model training controls."""

    Shows:
    - Current model accuracy
    - Training examples count
    - "Train Now" button
    - Auto-train threshold setting
```

### 7.2 Background Training
- Runs in QThread
- Progress bar in UI
- Notification when complete
- Auto-triggers at 50+ new labels

### 7.3 Test Checkpoint
```bash
# Label files → train model → see accuracy improvement
```

**Estimated effort**: Small

---

## Phase 8: Multi-Root Support
**Goal**: Index multiple folders, cross-link between them

### 8.1 Add Roots Manager
**File**: `src/labindex_app/views/roots_panel.py`

```python
class RootsPanel(QWidget):
    """Manage indexed folders."""

    Shows:
    - List of indexed roots
    - File counts per root
    - "Add Folder" button
    - "Refresh" per root
```

### 8.2 Cross-Root Linking
Update LinkerService to:
- Find links across roots (e.g., surgery notes → experiments)
- Use animal ID as linking key
- Track cross-root relationships

### 8.3 Test Checkpoint
```bash
# Add surgery folder → links to experiment data → animal-centric view
```

**Estimated effort**: Medium

---

## Phase 9: Rules Manager
**Goal**: View, edit, merge, disable extraction rules

### 9.1 Add RulesPanel
**File**: `src/labindex_app/views/rules_panel.py`

```python
class RulesPanel(QWidget):
    """Manage extraction rules and signatures."""

    Shows:
    - Active rules with match counts
    - Edit dialog for each rule
    - Merge suggestions
    - Disable/enable toggle
    - Health warnings (unused rules, conflicts)
```

### 9.2 Rule Optimization Suggestions
Periodic check for:
- Rules with 0 matches → suggest delete
- Overlapping rules → suggest merge
- Slow rules → suggest optimization

### 9.3 Test Checkpoint
```bash
# View rules → see health warnings → take suggested actions
```

**Estimated effort**: Small

---

## Phase 10: Graph Visualization
**Goal**: Visual exploration of file relationships

### 10.1 Add GraphWidget
**File**: `src/labindex_app/views/graph_widget.py`

```python
class GraphWidget(QWidget):
    """Interactive relationship graph."""

    Uses: pyqtgraph or matplotlib for rendering

    Features:
    - Nodes = files (colored by type)
    - Edges = links (thickness = confidence)
    - Click node → show details
    - Filter by type/folder
    - Layout options (tree, radial, force-directed)
```

### 10.2 Graph ViewModel
**File**: `src/labindex_app/viewmodels/graph_vm.py`

```python
class GraphViewModel(BaseViewModel):
    """Manages graph state."""

    Properties:
    - nodes: List[GraphNode]
    - edges: List[GraphEdge]
    - selected_node: Optional[int]
    - layout: str

    Methods:
    - load_subgraph(center_file_id: int, depth: int)
    - filter_by_type(types: List[str])
    - change_layout(layout: str)
```

### 10.3 Test Checkpoint
```bash
# View graph → click nodes → see relationships
```

**Estimated effort**: Medium

---

## Implementation Order Summary

```
Phase 1: Minimal Chat UI          ← START HERE (foundation)
    ↓
Phase 2: Folder Indexing          ← Core functionality
    ↓
Phase 3: LLM Example Learning     ← Makes it "smart"
    ↓
Phase 4: Re-extraction Pipeline   ← Applies learning
    ↓
Phase 5: Browse Panel             ← Better UX
    ↓
Phase 6: Bulk Labeling           ← Training data
    ↓
Phase 7: ML Training             ← Improves over time
    ↓
Phase 8: Multi-Root Support      ← Full capability
    ↓
Phase 9: Rules Manager           ← Maintainability
    ↓
Phase 10: Graph Visualization    ← Nice to have
```

---

## Quick Wins Already Done

✅ **Timestamp features** - Added to FeatureVector:
- `time_created_delta_hours`
- `time_modified_delta_hours`
- `created_within_1h`, `created_within_24h`, `created_within_7d`
- `modified_within_1h`, `modified_within_24h`
- `src_size_bytes`, `dst_size_bytes`

These are automatically extracted and contribute to link scoring.

---

## File Structure After Implementation

```
src/labindex_app/
├── main.py                         # Application entry point
├── viewmodels/
│   ├── __init__.py
│   ├── base.py                     # Existing
│   ├── chat_vm.py                  # Phase 1
│   ├── indexing_vm.py              # Phase 2
│   ├── browse_vm.py                # Phase 5
│   ├── training_vm.py              # Phase 7
│   ├── graph_vm.py                 # Phase 10
│   ├── strategy_explorer_vm.py     # Existing
│   └── candidate_review_vm.py      # Existing
├── views/
│   ├── __init__.py
│   ├── main_window.py              # Phase 1
│   ├── chat_widget.py              # Phase 1
│   ├── browse_panel.py             # Phase 5
│   ├── training_panel.py           # Phase 7
│   ├── roots_panel.py              # Phase 8
│   ├── rules_panel.py              # Phase 9
│   └── graph_widget.py             # Phase 10
└── dialogs/
    ├── __init__.py
    └── bulk_label_dialog.py        # Phase 6

src/labindex_core/
├── services/
│   ├── signature_learner.py        # Phase 3 (NEW)
│   ├── reextractor.py              # Phase 4 (NEW)
│   └── ... (existing services)
└── ... (existing structure)
```

---

## Testing Strategy

Each phase has a checkpoint. After completing a phase:

1. **Manual test** - Use the UI, verify behavior
2. **Integration test** - Run test script against examples folder
3. **Regression check** - Ensure previous features still work

---

## Notes on MVVM Compliance

All changes follow the pattern:

- **ViewModels**: Hold state, emit signals, call services
- **Views**: Display state, handle user input, connect to VM signals
- **Services**: Business logic, database access, LLM calls
- **No direct View → Service calls**
- **No business logic in Views**

The existing `BaseViewModel` class is used for all new ViewModels.

---

## Getting Started

To begin implementation:

```bash
cd LabIndex

# Create the app package structure
mkdir -p src/labindex_app/views
mkdir -p src/labindex_app/dialogs

# Start with Phase 1
# Create chat_widget.py, chat_vm.py, main_window.py
```

Then follow each phase in order, testing at each checkpoint.
