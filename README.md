# LabIndex

**Read-only lab drive indexer with LLM-assisted search**

LabIndex builds a local SQLite index of your lab/network drives, enabling fast search and intelligent file discovery without ever modifying your source files.

## Features

- **Read-Only Safety**: Never writes to indexed drives
- **Fast Search**: SQLite FTS5 full-text search on local SSD
- **Smart Linking**: Automatically connects notes ↔ data ↔ histology
- **LLM Assistant**: Natural language queries with evidence-based answers
- **Graph Visualization**: Interactive file relationship explorer

## Quick Start

```bash
# Install
pip install -e ".[dev,extraction]"

# Run
python run.py
```

## Architecture

- `labindex_core/` - Headless library (reusable from other apps)
- `labindex_app/` - PyQt6 desktop application
- `tests/` - Test suite

## Safety

LabIndex is designed with multiple safety layers:
- All file access through a read-only facade
- No write operations in the codebase
- Agent tools use file IDs, not raw paths
- UI clearly indicates read-only mode

## License

MIT License - See LICENSE file
