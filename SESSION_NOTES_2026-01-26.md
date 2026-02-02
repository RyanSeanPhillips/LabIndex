# LabIndex Session Notes - 2026-01-26

## What Was Accomplished

### 1. MVVM Extraction (Complete)
- Created 6 ViewModels: IndexStatusVM, SearchVM, GraphVM, AgentVM, InspectorVM, CandidateReviewVM
- Fixed N+1 query problems with batch methods
- Created workers for background operations
- Created AppCoordinator for cross-VM communication
- Reduced main_window.py from ~1,912 lines to ~1,000 lines

### 2. Test Run on Examples Folder
- Indexed examples folder: 1,138 files, 551 with content extracted, 4,026 links
- Found 19 FP_data photometry CSV files, 16 txt notes files
- Discovered that current linker creates wrong links (to .abf files instead of nearby .txt notes)

### 3. Photometry Analysis
- Analyzed folder structure: session_folder/FP_data_X/FP_data_X.csv with notes at session_folder/YYMMDD.txt
- Notes files contain: mouse IDs (R-266018), channel mappings (ROI->signal type), wavelengths, timelines
- Created analyze_photometry.py script to understand the data structure

### 4. Adaptive Linking Plan (Designed)
Full plan saved in: `.claude/plans/curried-strolling-starlight.md`

Key design decisions:
- Context window: 20 lines around references
- ML models: Both RandomForest and XGBoost available
- LLM budget: 50 calls per session (configurable)
- Generic handler system: Works with any file type, LLM can discover new patterns

## Files Created (To Be Reviewed)

**Premature implementations (may need rework):**
- `src/labindex_core/services/llm_file_reader.py` - Context reading, may be superseded
- `src/labindex_core/services/strategy_generator.py` - Strategy generation, may be superseded

**Test files:**
- `test_mvvm.py` - Tests the MVVM implementation
- `analyze_photometry.py` - Analyzes photometry file structure

## Key Insight: Keyword Extraction for File Classification

**User's idea:** Extract keywords from confirmed notes files to help classify new files.

**How it would work:**
1. User shows LLM some example notes files
2. LLM extracts characteristic keywords/patterns (e.g., "415nm", "470nm", "ROI", "GCaMP", "recording")
3. These become "content signatures" for the file type handler
4. During indexing, files are scored against these signatures
5. Signatures can be stored in the handler config and refined over time

**Implementation location:** `handlers/base.py` - add `content_signatures` field
```python
class FileTypeHandler:
    content_signatures: List[str]  # Keywords that identify this type
    signature_weights: Dict[str, float]  # Optional weights for each keyword

    def score_by_signatures(self, content: str) -> float:
        """Return 0-1 score based on keyword presence."""
```

## Environment Notes

**Python environment:** plethapp conda
**Path:** `C:\Users\rphil2\AppData\Local\miniforge3\envs\plethapp\python.exe`

## Next Steps

1. Delete premature implementations if they don't fit the plan
2. Implement Phase 1: Context-aware file reading with handler registry
3. Add content signature extraction to handlers
4. Test on photometry data

## Files Modified in MVVM Extraction

- `src/labindex_app/viewmodels/*` - All new
- `src/labindex_app/workers/*` - All new
- `src/labindex_core/services/search.py` - Added `search_with_metadata()`
- `src/labindex_core/services/linker.py` - Added `get_candidates_with_files()`
