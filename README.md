# LabIndex

**NLP-Assisted Lab Directory Indexing and File Relationship Discovery**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18458509.svg)](https://doi.org/10.5281/zenodo.18458509)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LabIndex builds a local SQLite index of your lab/network drives, enabling fast search, intelligent file discovery, and automatic relationship detection between data files and notes—all without ever modifying your source files.

## Key Features

- **Read-Only Safety**: Never writes to indexed drives - all operations through read-only facade
- **Tiered Metadata Extraction**: Pattern matching → NLP → LLM pipeline for progressively complex files
- **Automatic Link Detection**: Connects notes ↔ data files using filename patterns, content analysis, and ML
- **48+ ML Features**: Comprehensive feature extraction for link confidence scoring
- **Human-in-the-Loop Review**: Confidence-based routing to human review for uncertain cases
- **LLM Integration**: Claude and Ollama adapters for intelligent pattern learning
- **Graph Visualization**: Interactive exploration of file relationships
- **Fast Search**: SQLite FTS5 full-text search on local index

## Architecture

```
labindex/
├── labindex_core/          # Headless library (importable API)
│   ├── domain/             # Data models (DTOs)
│   ├── ports/              # Abstract interfaces
│   ├── adapters/           # SQLite, LLM, filesystem implementations
│   ├── services/           # Business logic layer
│   │   ├── crawler.py      # Tier 0: File inventory
│   │   ├── extractor.py    # Tier 1-2: Content extraction
│   │   ├── linker.py       # Rule-based link detection
│   │   ├── feature_extractor.py  # 48+ ML features
│   │   ├── ml_trainer.py   # Classifier training
│   │   └── link_auditor.py # Tier 3: LLM validation
│   └── extractors/         # File-type-specific extractors
│
└── labindex_app/           # PyQt6 desktop application
    ├── viewmodels/         # MVVM ViewModels
    └── views/              # UI components
```

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/labindex.git
cd labindex

# Install in development mode
pip install -e ".[dev,extraction]"

# Or minimal install (core only)
pip install -e .
```

### Dependencies

Core:
- Python 3.9+
- PyQt6
- SQLite (FTS5)

Extraction (optional):
- pyabf (ABF files)
- sonpy (Spike2 SMRX/SMR)
- openpyxl (Excel)
- pdfplumber (PDF)
- python-docx (Word)

LLM (optional):
- anthropic (Claude API)
- ollama (local models)

## Quick Start

### As a Desktop Application

```bash
python run.py
```

### As a Python API

```python
from labindex_core.adapters.sqlite_db import SqliteDB
from labindex_core.adapters.readonly_fs import ReadOnlyFS
from labindex_core.services.crawler import CrawlerService
from labindex_core.services.search import SearchService

# Initialize
db = SqliteDB("my_index.db")
fs = ReadOnlyFS()
crawler = CrawlerService(fs, db)
search = SearchService(db)

# Index a folder
root = crawler.add_root("/path/to/lab/data", "My Project")
crawler.crawl_root(root.root_id)

# Search
results = search.search("mouse 266")
for r in results:
    print(f"{r.name}: {r.path}")
```

## Tiered Extraction Pipeline

LabIndex uses a progressive extraction strategy to balance speed and accuracy:

| Tier | Method | Speed | Accuracy | Use Case |
|------|--------|-------|----------|----------|
| **0** | File scan | Very fast | Basic | Path, size, timestamps, extension |
| **1** | Pattern matching | Fast | High | Standardized formats (ABF, SMRX headers) |
| **2** | NLP extraction | Medium | High | Semi-structured text (notes, spreadsheets) |
| **3** | LLM reading | Slow | Highest | Complex/ambiguous notes (budget-controlled) |

## Supported File Types

| Category | Extensions | Extraction Level |
|----------|------------|------------------|
| **Physiology Data** | .abf, .smrx, .smr, .edf, .tdms | Headers, channels, sampling rates |
| **Analysis Files** | .npz, .npy, .mat, .h5 | Array names, shapes, metadata |
| **Documents** | .pdf, .docx, .doc, .txt, .md | Full text, structure |
| **Spreadsheets** | .xlsx, .xls, .csv | Headers, cell values, formulas |
| **Presentations** | .pptx, .ppt | Slide titles, notes, text |
| **Code** | .py, .m, .r, .ipynb | Structure, comments |

## Link Detection

LabIndex automatically discovers relationships between files:

- **Animal ID matching**: Extracts IDs from paths/filenames
- **Filename similarity**: Fuzzy matching with numeric suffix handling
- **Content references**: Finds mentions of files in notes
- **Folder proximity**: Sibling/parent relationships
- **ML classification**: Trained models with confidence scoring

### Confidence Routing

```
Score > 0.95  →  Auto-accept (confirmed link)
Score 0.4-0.95  →  Human review queue
Score < 0.4  →  Auto-reject or LLM audit
```

## Safety Design

LabIndex is designed with multiple safety layers:

1. **Read-Only Facade**: All file access through `ReadOnlyFS` - no write operations
2. **File ID Handles**: Agent tools use IDs, never raw paths
3. **Database Isolation**: Index stored separately from source files
4. **UI Indicators**: Clear read-only mode indication

## Related Projects

- **[PhysioMetrics](https://github.com/RyanSeanPhillips/PhysioMetrics)**: Multi-modal physiological data analysis platform that can use LabIndex for project organization

## Citation

If you use LabIndex in your research, please cite:

```bibtex
@software{phillips_labindex_2026,
  author       = {Phillips, Ryan S.},
  title        = {LabIndex: NLP-Assisted Lab Directory Indexing},
  year         = 2026,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.18458509},
  url          = {https://github.com/RyanSeanPhillips/LabIndex}
}
```

## License

MIT License - See [LICENSE](LICENSE) file

## Contributing

Contributions welcome! Please open an issue or pull request.
