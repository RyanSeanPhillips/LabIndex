# LabIndex Development Session Notes

## Session: 2026-01-26

### Completed: v2 Goal-Driven Linking (10 phases)
All phases complete and tested:
- Schema: candidate_edges, artifacts, audits, linker_strategies tables
- Models: CandidateEdge, Artifact, Audit, LinkerStrategy dataclasses
- Services: FeatureExtractor, LinkerTrainer, LinkAuditor, ArtifactExtractor
- UI: Tab 3 "Link Review" + StrategyBuilderDialog
- Agent tools: get_candidate_edges, review_candidate, get_linking_strategies, get_candidate_stats

### In Progress: MVVM Extraction
Plan file: `C:\Users\rphil2\.claude\plans\curried-strolling-starlight.md`

**Key findings:**
- `main_window.py` is 1,912 lines with 60+ handlers, 4 thread classes
- `viewmodels/` folder exists but empty (placeholder)
- N+1 query problems in `_populate_results()` (700+ queries for 100 results)
- Reference pattern: `pyqt6/viewmodels/event_marker_viewmodel.py`

**4 Phases planned:**
1. Foundation + IndexStatusVM (~300 lines)
2. SearchVM + GraphVM (~400 lines)
3. AgentVM + InspectorVM (~300 lines)
4. CandidateReviewVM + Coordinator (~400 lines)

### UI/UX Note
Tab 1 "Find Links" uses OLD automatic approach.
Tab 3 "Link Review" uses NEW goal-driven approach.
User wants UI/UX planning session after MVVM is done.

### Reference Files
| File | Purpose |
|------|---------|
| `pyqt6/viewmodels/event_marker_viewmodel.py` | ViewModel pattern reference |
| `LabIndex/src/labindex_app/views/main_window.py` | Target (1,912 lines → ~400) |
| `LabIndex/src/labindex_app/views/graph_canvas.py` | Decouple from DB (1,985 lines) |
