# LabIndex - Development Guide

> **Version**: 0.1.0-dev
> **Parent Project**: PhysioMetrics
> **Purpose**: Read-only lab drive indexer with LLM-assisted search

## Quick Start

```bash
# Development
python run.py

# Run tests
pytest tests/
```

## Project Overview

LabIndex is a **read-only** file indexer for lab/network drives that:
- Builds a local SQLite index (never modifies source files)
- Provides fast search via FTS5 full-text search
- Links related files (notes ↔ data ↔ histology)
- Offers an LLM assistant for natural language queries

**Safety is paramount**: The app NEVER writes to the indexed drive.

## Architecture

```
LabIndex/
├── labindex_core/           # Headless library (no UI dependencies)
│   ├── domain/              # DTOs, enums, data models
│   ├── ports/               # Interfaces (FSPort, DBPort, LLMPort)
│   ├── adapters/            # Implementations (sqlite, readonly_fs)
│   ├── services/            # Business logic (crawler, extractor, linker)
│   └── schema/              # SQL migrations
├── labindex_app/            # PyQt6 UI
│   ├── viewmodels/          # MVVM view models
│   ├── views/               # Qt widgets
│   └── resources/           # Icons, styles
└── tests/                   # pytest test suite
```

## Tiered Indexing

| Tier | What | Cost |
|------|------|------|
| 0 | Inventory (scandir/stat only) | Very low |
| 1 | Lightweight extraction (headers, samples) | Low |
| 2 | Format parsing (PPTX, PDF, ABF headers) | Medium |
| 3 | LLM enrichment (summaries, entities) | High (budgeted) |

## Safety Model

**Read-only at ALL levels:**
- OS: Mount shares read-only when possible
- App: All file access through `ReadOnlyFS` facade
- UI: No destructive actions, "READ-ONLY" indicator visible
- Agent: Tools use `file_id` handles, not raw paths

## Key Files

| File | Purpose |
|------|---------|
| `labindex_core/adapters/readonly_fs.py` | Safe filesystem access |
| `labindex_core/adapters/sqlite_db.py` | Database operations |
| `labindex_core/services/crawler.py` | Directory scanning |
| `labindex_core/services/search.py` | FTS5 search |
| `labindex_app/views/main_window.py` | Main UI |

## Testing

```bash
# Run all tests
pytest tests/

# Run safety tests only
pytest tests/unit/test_readonly_fs.py

# Run with coverage
pytest --cov=labindex_core tests/
```

## Integration with PhysioMetrics

LabIndex is designed to be embeddable:
```python
from labindex_core.services import SearchService, CrawlerService

# Use in PhysioMetrics to find related files
search = SearchService(db_path)
notes = search.find_notes_for_file(abf_path)
```

## Plan Documents

See `docs/plan/` for detailed design documents:
- `00_master_plan.md` - Overview and phases
- `03_sqlite_schema_and_fts.md` - Database design
- `08_llm_agent_and_tools.md` - Agent architecture

## Current Phase

**Phase 1: Inventory MVP**
- [ ] SQLite schema + migrations
- [ ] ReadOnlyFS facade + safety tests
- [ ] Crawler service (Tier 0)
- [ ] Minimal UI (Index tab)
- [ ] Basic filename search
