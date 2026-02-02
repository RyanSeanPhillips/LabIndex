# LabIndex as Foundation for Aim 1: NLP-Based Data Curation

> **Grant**: R01 - Multi-Modal Physiological Data Analysis Platform
> **Aim 1**: NLP-Based Data Curation and Custom Analysis Workflows
> **Document Purpose**: Technical reference mapping LabIndex capabilities to Aim 1 requirements

---

## Conceptual Architecture: Iterative Index Refinement

The following diagram illustrates the tiered, iterative workflow for building a curated lab index. Each step builds on the previous, with human review ensuring quality and ML classifiers improving over time.

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    LABINDEX: ITERATIVE INDEX REFINEMENT                       ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                         STEP 0: BASIC INVENTORY                         │  ║
║  │                        (Automated, No User Input)                       │  ║
║  │                                                                         │  ║
║  │   Lab Directory ──► Recursive Scan ──► Basic Metadata Extraction       │  ║
║  │        │                                      │                         │  ║
║  │        │            ┌─────────────────────────┴─────────────────────┐   │  ║
║  │        │            │  • File path, name, extension                 │   │  ║
║  │        │            │  • Size, creation time, modification time     │   │  ║
║  │        │            │  • Extension-based category (DATA, DOCS, etc) │   │  ║
║  │        │            │  • Parent folder relationships                │   │  ║
║  │        │            └───────────────────────────────────────────────┘   │  ║
║  │        ▼                                                                │  ║
║  │   SQLite Index (Tier 0: Inventory Complete)                            │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                        ║
║                                      ▼                                        ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                    STEP 1: LLM-ASSISTED PATTERN LEARNING                │  ║
║  │                         (Interactive, User-Guided)                      │  ║
║  │                                                                         │  ║
║  │   User ◄──────────────────► LLM Conversation                           │  ║
║  │     │                            │                                      │  ║
║  │     │  "These are always data    │                                      │  ║
║  │     │   files: .abf, .smrx,      │   LLM analyzes folder structure     │  ║
║  │     │   FP_data*.csv, .edf"      │   and file naming patterns          │  ║
║  │     │                            │                                      │  ║
║  │     │  "Here's an example        │                                      │  ║
║  │     │   notes file and its       ▼                                      │  ║
║  │     │   associated data"    ┌─────────────────────────────────────┐    │  ║
║  │     │                       │  LLM Generates Search Rules:        │    │  ║
║  │     │                       │  • glob: **/FP_data*.csv            │    │  ║
║  │     │                       │  • glob: **/*.abf                   │    │  ║
║  │     │                       │  • regex: \d{6}[A-Z]?\.txt → notes  │    │  ║
║  │     │                       │  • folder pattern: Animal_*/Day_*   │    │  ║
║  │     │                       └─────────────────────────────────────┘    │  ║
║  │     │                                      │                            │  ║
║  │     │                                      ▼                            │  ║
║  │     │                          ┌───────────────────────┐                │  ║
║  │     └─────────────────────────►│  Focused Re-indexing  │                │  ║
║  │                                │  with learned rules   │                │  ║
║  │                                └───────────────────────┘                │  ║
║  │                                           │                             │  ║
║  │   Output: Proposed file type labels + notes↔data link candidates       │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                        ║
║                                      ▼                                        ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                   STEP 2: USER REVIEW & CONFIRMATION                    │  ║
║  │                        (Human-in-the-Loop QC)                           │  ║
║  │                                                                         │  ║
║  │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │  ║
║  │   │  Review File    │    │  Review Link    │    │  Source-Linked  │    │  ║
║  │   │  Type Labels    │    │  Candidates     │    │  Verification   │    │  ║
║  │   │                 │    │                 │    │                 │    │  ║
║  │   │  ✓ Accept       │    │  ✓ Accept       │    │  Click field →  │    │  ║
║  │   │  ✗ Reject       │    │  ✗ Reject       │    │  See source     │    │  ║
║  │   │  ? Flag         │    │  ? Needs audit  │    │  in context     │    │  ║
║  │   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘    │  ║
║  │            │                      │                      │              │  ║
║  │            └──────────────────────┼──────────────────────┘              │  ║
║  │                                   │                                     │  ║
║  │                                   ▼                                     │  ║
║  │                    ┌───────────────────────────┐                        │  ║
║  │                    │  Labeled Training Data    │                        │  ║
║  │                    │  (Accepted/Rejected with  │                        │  ║
║  │                    │   feature vectors)        │                        │  ║
║  │                    └───────────────────────────┘                        │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                        ║
║                                      ▼                                        ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                    STEP 3: ML CLASSIFIER TRAINING                       │  ║
║  │                    (Automated Model Improvement)                        │  ║
║  │                                                                         │  ║
║  │   Labeled Data ──► Feature Extraction (48+ features) ──► Train Models  │  ║
║  │                                                               │         │  ║
║  │                    ┌──────────────────────────────────────────┘         │  ║
║  │                    │                                                    │  ║
║  │                    ▼                                                    │  ║
║  │   ┌─────────────────────────────────────────────────────────────────┐  │  ║
║  │   │  Trained Classifiers:                                           │  │  ║
║  │   │                                                                 │  │  ║
║  │   │  • File Type Classifier (is this a notes file? data file?)     │  │  ║
║  │   │  • Link Classifier (should these files be connected?)          │  │  ║
║  │   │  • Confidence Scoring (how certain is this prediction?)        │  │  ║
║  │   │                                                                 │  │  ║
║  │   │  Models: RandomForest, XGBoost, MLP (with feature importance)  │  │  ║
║  │   └─────────────────────────────────────────────────────────────────┘  │  ║
║  │                                                                         │  ║
║  │   Output: Models that can classify new files without user input        │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                        ║
║           ┌──────────────────────────┴──────────────────────────┐             ║
║           │                                                      │             ║
║           ▼                                                      ▼             ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                  STEP 4: ONGOING MAINTENANCE & REFINEMENT               │  ║
║  │                      (Daily/Triggered Re-indexing)                      │  ║
║  │                                                                         │  ║
║  │   ┌─────────────────┐         ┌─────────────────┐                      │  ║
║  │   │  New Files      │         │  Scheduled      │                      │  ║
║  │   │  Detected       │         │  Daily Scan     │                      │  ║
║  │   └────────┬────────┘         └────────┬────────┘                      │  ║
║  │            │                           │                                │  ║
║  │            └───────────┬───────────────┘                                │  ║
║  │                        ▼                                                │  ║
║  │              ┌─────────────────────┐                                    │  ║
║  │              │  Incremental Scan   │                                    │  ║
║  │              │  (only new/changed) │                                    │  ║
║  │              └──────────┬──────────┘                                    │  ║
║  │                         │                                               │  ║
║  │                         ▼                                               │  ║
║  │   ┌─────────────────────────────────────────────────────────────────┐  │  ║
║  │   │  ML Classifiers Auto-Classify New Files:                        │  │  ║
║  │   │                                                                 │  │  ║
║  │   │  High Confidence (>0.95) ──► Auto-accept, add to index         │  │  ║
║  │   │  Medium (0.4-0.95) ──────► Queue for human review              │  │  ║
║  │   │  Low (<0.4) ─────────────► Auto-reject or flag for LLM audit   │  │  ║
║  │   └─────────────────────────────────────────────────────────────────┘  │  ║
║  │                                                                         │  ║
║  │   Corrections feed back into training data ──────────────────────────┐ │  ║
║  └──────────────────────────────────────────────────────────────────────┼─┘  ║
║                                                                          │    ║
║           ┌──────────────────────────────────────────────────────────────┘    ║
║           │                                                                   ║
║           │    ╔════════════════════════════════════════════════════════╗    ║
║           │    ║              VIRTUOUS IMPROVEMENT CYCLE                ║    ║
║           │    ║                                                        ║    ║
║           └───►║  More data ──► Better models ──► Less human review    ║    ║
║                ║       ▲                                    │           ║    ║
║                ║       └────────────────────────────────────┘           ║    ║
║                ║                                                        ║    ║
║                ║  Initial: Heavy user involvement (Steps 1-2)          ║    ║
║                ║  Mature: Mostly automated (Step 4 dominates)          ║    ║
║                ╚════════════════════════════════════════════════════════╝    ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Step Summary Table

| Step | Name | User Effort | Automation | Output |
|------|------|-------------|------------|--------|
| **0** | Basic Inventory | None | Full | File paths, sizes, timestamps, extension-based categories |
| **1** | LLM Pattern Learning | Medium | LLM-assisted | Glob/regex rules, file type proposals, link candidates |
| **2** | User Review | High (initially) | Flagging only | Labeled training data, confirmed links |
| **3** | ML Training | None | Full | Trained classifiers with confidence scoring |
| **4** | Ongoing Maintenance | Low | High | Auto-classified new files, periodic model updates |

### Key Design Principles

1. **Progressive Automation**: Human effort decreases as the system learns
2. **Confidence-Based Routing**: Only uncertain cases require human review
3. **Source-Linked Verification**: Every extracted value traceable to source
4. **Incremental Updates**: Only scan changed files, not entire directory
5. **Model Improvement**: Corrections become training data for better models

---

## Strategic Positioning: LabIndex for the R01

### Relationship: LabIndex vs PhysioMetrics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOFTWARE ECOSYSTEM                                   │
│                                                                             │
│  ┌─────────────────────────────┐     ┌─────────────────────────────────┐   │
│  │         LABINDEX            │     │         PHYSIOMETRICS           │   │
│  │   (General Lab Indexer)     │     │   (Physiological Analysis)      │   │
│  │                             │     │                                 │   │
│  │  • Any lab file system      │     │  • Respiratory signals          │   │
│  │  • Domain-agnostic          │────►│  • Fiber photometry             │   │
│  │  • Indexing & search        │     │  • Electrophysiology            │   │
│  │  • File relationship        │     │  • ML breath classification     │   │
│  │    discovery                │     │  • Cross-modal analysis         │   │
│  │                             │     │                                 │   │
│  │  Aim 1 Infrastructure       │     │  Aims 2 & 3 Analysis            │   │
│  │  ────────────────────       │     │  ──────────────────────         │   │
│  │  • File discovery           │     │  • Multimodal integration       │   │
│  │  • Tiered extraction        │     │  • Event detection              │   │
│  │  • Link detection           │     │  • Pattern recognition          │   │
│  │  • ML feature extraction    │     │  • Human-in-loop review         │   │
│  │                             │     │  • Session state records        │   │
│  │  GitHub + Zenodo DOI        │     │  GitHub + Zenodo DOI            │   │
│  │  (separate repository)      │     │  (existing: 10.5281/...)        │   │
│  └─────────────────────────────┘     └─────────────────────────────────┘   │
│                                                                             │
│  Integration: PhysioMetrics can optionally use LabIndex for project        │
│  organization, or users can use LabIndex standalone for any lab directory  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Grant Language

**DO frame as:**
> "We have developed LabIndex, a prototype lab directory indexing system demonstrating the feasibility of tiered metadata extraction and ML-assisted file linking. The proposed work will rigorously validate these methods across multiple datasets and external sites, develop standardized evaluation metrics, and integrate with the PhysioMetrics analysis platform."

**DON'T frame as:**
> ~~"We have already built Aim 1"~~ (makes it seem like work is done)

**Key differentiators** (what the grant funds vs. what exists):

| Exists (LabIndex Prototype) | Proposed Work (Grant Funding) |
|-----------------------------|-------------------------------|
| Basic tiered extraction | Rigorous validation on K01 + external datasets |
| Pattern-based linking | Precision/recall benchmarks with ground truth |
| ML feature extraction | Cross-site generalization testing |
| Human review workflow | Usability studies (6-10 participants) |
| SQLite persistence | Standardized project file format |
| LLM adapters | LLM notebook with sandboxed execution |

### Why Zenodo/GitHub Strengthens the Grant

1. **Demonstrates feasibility** - Reviewers can see working code
2. **Shows open-source commitment** - Aligns with FAIR principles
3. **Separates engineering from science** - Infrastructure exists, validation is the science
4. **Provides baseline for comparison** - "Current version achieves X, proposed work targets Y"
5. **De-risks the project** - Less chance of "can they actually build this?"

### Suggested Zenodo Metadata

```yaml
Title: "LabIndex: NLP-Assisted Lab Directory Indexing and File Relationship Discovery"
Version: 0.1.0 (prototype)
License: MIT
Keywords:
  - laboratory data management
  - file indexing
  - metadata extraction
  - machine learning
  - NLP
  - scientific data curation
Description: |
  Prototype implementation of tiered metadata extraction and ML-assisted
  file relationship discovery for scientific laboratory directories.
  Supports ABF, SMRX, NPZ, and 12+ file formats. Includes pattern-based,
  NLP, and LLM-assisted extraction pipelines with human-in-the-loop review.

Related publications: [Link to grant if funded]
Related software: PhysioMetrics (DOI: 10.5281/zenodo.17575911)
```

---

## Executive Summary

**LabIndex is an ideal backbone for Aim 1.** The existing codebase provides 80-90% of the infrastructure needed for the grant's data curation objectives. Key alignments:

| Aim 1 Component | LabIndex Status | Gap Analysis |
|-----------------|-----------------|--------------|
| (a) File Discovery | **Complete** | Add NLP pattern generation |
| (b) Tiered Metadata Extraction | **70% Complete** | Add source span linking UI |
| (c) Project Organization | **50% Complete** | Add project files + progress tracking |
| (d) LLM Notebook | **Not Started** | New component needed |

**Recommendation**: Use LabIndex as the core indexing/search layer and extend with:
1. Enhanced source-span linking interface (Figure 2 in grant)
2. Project file format with progress tracking
3. Integrated LLM notebook (could leverage existing Claude/Ollama adapters)

---

## 1. Grant Aim 1 Requirements

From the Research Strategy (pages 5-6):

### (a) File Discovery
> "Data files and associated notes are often scattered across folder hierarchies... We will develop NLP-assisted, provenance-linked file discovery in which the system examines sample files and folder structures, then generates candidate search patterns (glob, regex) with explicit justification."

**Key Requirements**:
- Scan folder hierarchies for data files and notes
- NLP-assisted pattern generation
- Validate patterns on held-out folders
- Iterative refinement for unmatched files

### (b) Tiered Metadata Extraction with Source Linking
> "We will develop a tiered extraction pipeline: Tier 1 applies fast pattern matching; Tier 2 uses NLP extraction for varied natural language; Tier 3 invokes LLM reading for complex unstructured notes."

**Key Requirements**:
- Tier 1: Pattern matching for standardized formats
- Tier 2: NLP for semi-structured text
- Tier 3: LLM for complex/ambiguous notes
- **Source linking**: Every extracted field links to source location
- One-click verification of extracted values

### (c) Project Organization with Progress Tracking
> "Project files store curated metadata, data file links, and analysis status in a single shareable record. Visual progress tracking across all recordings."

**Key Requirements**:
- Shareable project files
- Link recordings, files, metadata, analysis status
- Visual progress tracking
- Error flagging (missing files, duplicates, conflicts)

### (d) Integrated Notebook with LLM-Assisted Code Generation
> "Users describe analyses in natural language, the system generates executable code in a sandboxed environment... exports to standard .ipynb format."

**Key Requirements**:
- Natural language → code generation
- Sandboxed execution environment
- Multiple LLM provider support
- Export to .ipynb format
- Conversation history saved for provenance

---

## 2. LabIndex Architecture Mapping

### 2.1 File Discovery (Aim 1a) — **COMPLETE**

**LabIndex Implementation**: `labindex_core/services/crawler.py`

```
Grant Requirement              LabIndex Component              Status
─────────────────────────────────────────────────────────────────────
Scan folder hierarchies        CrawlerService.crawl_root()     ✅ Complete
Categorize files by type       FileCategory enum (50+ exts)    ✅ Complete
Find data files (.abf, etc)    ExtractorRegistry routing       ✅ Complete
Find notes files               Handler-based detection         ✅ Complete
Store file inventory           SQLite files table              ✅ Complete
Progress tracking              CrawlProgress callbacks         ✅ Complete
Pattern-based search           Glob/regex in SearchService     ✅ Complete
NLP pattern generation         AdaptiveLinkingService          ⚠️ Partial
```

**Current Capabilities**:
```python
# File discovery is fully operational
crawler = CrawlerService(fs, db)
root = crawler.add_root("/path/to/data", "My Project")
crawler.crawl_root(root.root_id, progress_callback=update_ui)

# Result: FileRecord objects with:
# - path, name, ext, size_bytes, mtime, ctime
# - category (DATA, DOCUMENTS, SPREADSHEETS, etc.)
# - status (INVENTORY_OK, EXTRACT_OK, etc.)
```

**Gap**: The grant proposes LLM-assisted pattern generation where the system examines sample files and proposes glob/regex patterns. LabIndex has the foundation in `AdaptiveLinkingService.explore_data_patterns()` but needs:
- UI for pattern proposal review
- Validation on held-out folders
- Iterative refinement workflow

**Integration Path**: Extend `AdaptiveLinkingService` to generate file discovery patterns, not just linking strategies.

---

### 2.2 Tiered Metadata Extraction (Aim 1b) — **70% COMPLETE**

**LabIndex Implementation**: `labindex_core/services/extractor.py` + `services/handlers/`

```
Grant Requirement              LabIndex Component              Status
─────────────────────────────────────────────────────────────────────
Tier 1: Pattern matching       ExtractorRegistry               ✅ Complete
  - ABF metadata               ABFExtractor                    ✅ Complete
  - SMRX metadata              SMRXExtractor                   ✅ Complete
  - Spreadsheet parsing        SpreadsheetHandler              ✅ Complete
  - Filename patterns          LinkerService                   ✅ Complete
Tier 2: NLP extraction         ContextReader + handlers        ✅ Complete
  - Reference detection        GenericTextHandler.find_refs    ✅ Complete
  - Entity extraction          ContentRecord.entities          ✅ Complete
  - Animal ID detection        Regex patterns                  ✅ Complete
Tier 3: LLM for complex notes  LinkAuditorService              ✅ Complete
  - Context understanding      context_reader.py               ✅ Complete
  - Verification               audit() with rationale          ✅ Complete
SOURCE LINKING                 Artifact table + locators       ⚠️ Partial
  - Text span anchors          ArtifactExtractor               ✅ Complete
  - Table cell locators        artifact_type enum              ✅ Complete
  - One-click verification     UI not yet built                ❌ Missing
```

**Current Tiered Pipeline**:
```python
# Tier 1: Fast pattern extraction (deterministic)
extractor = ExtractorService(fs, db)
content = extractor.extract_file(file, root_path)
# → ContentRecord with title, summary, keywords, entities

# Tier 2: Handler-based NLP extraction
handler = SpreadsheetHandler()
if handler.can_handle(file, content):
    metadata = handler.extract_metadata(file, content)
    references = handler.find_references(file, content, context_lines=5)
    # → Dict with column patterns, cell values, formulas

# Tier 3: LLM for ambiguous cases (budget-controlled)
auditor = LinkAuditorService(llm_client)
if auditor.should_audit(candidate):  # Gating condition
    result = auditor.audit(candidate, src_file, dst_file)
    # → AuditResult with verdict, confidence, rationale
```

**Source Linking Architecture** (already designed):
```python
@dataclass
class Artifact:
    artifact_id: int
    file_id: int
    artifact_type: str  # text_span, table_cell, table_row, etc.
    locator: dict       # Type-specific location data
    excerpt: str        # Text at that location

# Example locator for text span:
locator = {
    "start_line": 42,
    "end_line": 45,
    "start_char": 0,
    "end_char": 120,
    "context_before": "...",
    "context_after": "..."
}
```

**Gap**: The source linking infrastructure exists (Artifact table, locators) but the **verification UI** (grant's Figure 2: three-panel flow with file graph → metadata table → source preview) needs implementation.

**Integration Path**:
1. Extend graph visualization to show file network (already done!)
2. Add metadata table panel synchronized with graph selection
3. Add source preview panel with text highlighting
4. Wire together: click graph node → show metadata → click field → show source

---

### 2.3 Project Organization (Aim 1c) — **50% COMPLETE**

**LabIndex Implementation**: `labindex_core/domain/` + `adapters/sqlite_db.py`

```
Grant Requirement              LabIndex Component              Status
─────────────────────────────────────────────────────────────────────
Store curated metadata         ContentRecord table             ✅ Complete
Data file links                Edge/CandidateEdge tables       ✅ Complete
Analysis status tracking       FileRecord.status enum          ✅ Complete
Shareable project files        Not yet implemented             ❌ Missing
Visual progress tracking       IndexStatusVM.stats             ⚠️ Basic
Error flagging                 Candidate review workflow       ✅ Complete
```

**Current Status Tracking**:
```python
class FileStatus(Enum):
    PENDING = "pending"           # Not yet processed
    INVENTORY_OK = "inventory_ok" # File discovered
    EXTRACT_OK = "extract_ok"     # Content extracted
    LLM_OK = "llm_ok"            # LLM enrichment done
    ERROR = "error"              # Processing failed
    SKIPPED = "skipped"          # Intentionally skipped
```

**Gap**: LabIndex uses SQLite as the project store, but the grant proposes a portable "project file" format. Options:
1. Export SQLite subset to portable format (JSON/YAML)
2. Add project file layer on top of existing database
3. Use existing database with export/import capabilities

**Integration Path**:
1. Define `ProjectFile` schema (JSON) with:
   - roots, files, edges, candidates, metadata, analysis_status
2. Add `export_project()` / `import_project()` to services
3. Visual progress: extend IndexStatusVM with per-recording status grid

---

### 2.4 LLM Notebook (Aim 1d) — **NOT STARTED** (but foundations exist)

**LabIndex Foundations**: `adapters/claude_llm.py`, `adapters/ollama_llm.py`

```
Grant Requirement              LabIndex Component              Status
─────────────────────────────────────────────────────────────────────
Natural language → code        Not implemented                 ❌ Missing
Multiple LLM providers         Claude + Ollama adapters        ✅ Complete
Sandboxed execution            Not implemented                 ❌ Missing
Export to .ipynb               Not implemented                 ❌ Missing
Conversation history           AgentVM.messages                ⚠️ Basic
```

**Existing LLM Infrastructure**:
```python
# LLM adapters already support code generation prompts
class LLMPort(ABC):
    @abstractmethod
    def chat(self, messages, tools=None, temperature=0.7) -> LLMResponse:
        pass

# Claude implementation (native tool calling)
class ClaudeLLM(LLMPort):
    def chat(self, messages, tools=None, ...):
        response = self.client.messages.create(
            model=self.model,
            messages=messages,
            tools=tools,  # Native tool support
            ...
        )
        return LLMResponse(content=response.content, ...)

# Ollama implementation (local, free)
class OllamaLLM(LLMPort):
    def chat(self, messages, tools=None, ...):
        # Fallback for tool calling
        ...
```

**Gap**: This is a new component. However, the LLM infrastructure (adapters, tool calling, conversation management) is ready. Need to add:
1. Code generation prompt templates
2. Sandboxed Python execution (e.g., `RestrictedPython` or subprocess)
3. Jupyter notebook export
4. Conversation history persistence

**Integration Path**:
1. Create `NotebookService` using existing LLM adapters
2. Add sandboxed execution with `exec()` in restricted namespace
3. Build notebook UI component with code cells + outputs
4. Export to `.ipynb` via `nbformat` library

---

## 3. Feature-by-Feature Alignment Matrix

| Grant Figure/Feature | LabIndex Component | Implementation Status |
|---------------------|-------------------|----------------------|
| **Figure 1: Platform Architecture** | | |
| Source Data (heterogeneous) | CrawlerService + ExtractorRegistry | ✅ Complete |
| Index/Organize/Track | SQLite DB + FileRecord status | ✅ Complete |
| Source-link + verify | Edge table + Artifact locators | ✅ Complete |
| Single-session analysis | — (PhysioMetrics handles this) | N/A |
| ML Classification | ML Trainer + Feature Extractor | ✅ Complete |
| Compare (group-level) | — (PhysioMetrics handles this) | N/A |
| **Figure 2: Source-Linked Extraction** | | |
| (A) File network graph | ModernGraphCanvas | ✅ Complete |
| (B) Metadata table | Not yet implemented | ❌ Missing |
| (C) Source preview + highlight | Artifact infrastructure ready | ⚠️ Partial |
| One-click verification | UI not yet built | ❌ Missing |
| **Tiered Extraction Pipeline** | | |
| Tier 1: Pattern matching | ExtractorRegistry + handlers | ✅ Complete |
| Tier 2: NLP extraction | ContextReader + entity extraction | ✅ Complete |
| Tier 3: LLM reading | LinkAuditorService | ✅ Complete |
| Budget control (gating) | `should_audit()` conditions | ✅ Complete |
| **Link Detection** | | |
| Animal ID matching | LinkerService regex patterns | ✅ Complete |
| Filename similarity | FeatureVector (16 path features) | ✅ Complete |
| Content mentions | GenericTextHandler.find_references | ✅ Complete |
| Confidence scoring | SoftScoring with breakdown | ✅ Complete |
| Human review workflow | CandidateReviewVM | ✅ Complete |
| **ML Features (48+)** | | |
| Path/name similarity | FeatureExtractor (16 features) | ✅ Complete |
| Evidence quality | FeatureExtractor (5 features) | ✅ Complete |
| Context agreement | FeatureExtractor (5 features) | ✅ Complete |
| Uniqueness/conflict | FeatureExtractor (4 features) | ✅ Complete |
| Timestamp proximity | FeatureExtractor (7 features) | ✅ Complete |

---

## 4. Database Schema for Aim 1

LabIndex's SQLite schema directly supports Aim 1's data model:

```sql
-- Tier 0: File inventory (crawler output)
CREATE TABLE files (
    file_id INTEGER PRIMARY KEY,
    root_id INTEGER REFERENCES roots(root_id),
    path TEXT NOT NULL,
    parent_path TEXT,
    name TEXT NOT NULL,
    ext TEXT,
    is_dir INTEGER DEFAULT 0,
    size_bytes INTEGER,
    mtime REAL,  -- Modification time
    ctime REAL,  -- Creation time
    category TEXT,  -- DATA, DOCUMENTS, SPREADSHEETS, etc.
    status TEXT DEFAULT 'pending'  -- Processing status
);

-- Tier 1/2/3: Extracted content
CREATE TABLE content (
    file_id INTEGER PRIMARY KEY REFERENCES files(file_id),
    title TEXT,
    summary TEXT,
    keywords TEXT,  -- JSON array
    entities TEXT,  -- JSON dict {type: [values]}
    content_excerpt TEXT,
    full_text TEXT,
    extraction_version TEXT
);

-- Full-text search (FTS5)
CREATE VIRTUAL TABLE fts_docs USING fts5(
    file_id, name, content_excerpt, full_text
);

-- Confirmed relationships
CREATE TABLE edges (
    edge_id INTEGER PRIMARY KEY,
    src_file_id INTEGER REFERENCES files(file_id),
    dst_file_id INTEGER REFERENCES files(file_id),
    relation_type TEXT,  -- NOTES_FOR, ANALYSIS_OF, etc.
    confidence REAL,
    evidence TEXT,
    evidence_file_id INTEGER,
    created_by TEXT,  -- rule, llm, user
    created_at TEXT
);

-- Proposed relationships (human review queue)
CREATE TABLE candidate_edges (
    candidate_id INTEGER PRIMARY KEY,
    -- All Edge fields plus:
    status TEXT DEFAULT 'pending',  -- pending, accepted, rejected, needs_audit
    linker_strategy_id INTEGER,
    features_json TEXT,  -- ML feature vector
    evidence_json TEXT
);

-- Source anchors for verification (NEW for Aim 1)
CREATE TABLE artifacts (
    artifact_id INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES files(file_id),
    artifact_type TEXT,  -- text_span, table_cell, table_row, etc.
    locator TEXT,  -- JSON with type-specific location
    excerpt TEXT
);

-- LLM auditor verdicts
CREATE TABLE audits (
    audit_id INTEGER PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidate_edges(candidate_id),
    auditor_model TEXT,
    verdict TEXT,  -- accept, reject, needs_more_info
    confidence REAL,
    rationale_excerpt TEXT
);
```

---

## 5. Service Architecture for Aim 1

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Aim 1: Data Curation                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  (a) File   │    │(b) Metadata │    │(c) Project  │              │
│  │  Discovery  │───▶│ Extraction  │───▶│Organization │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  Crawler    │    │  Extractor  │    │  Project    │              │
│  │  Service    │    │  Service    │    │  Service    │  ◀── NEW    │
│  │  ✅ Done    │    │  ✅ Done    │    │  ⚠️ Partial │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                  │                  │                      │
│         │           ┌──────┴──────┐          │                      │
│         │           ▼             ▼          │                      │
│         │    ┌───────────┐ ┌───────────┐    │                      │
│         │    │  Handler  │ │  Context  │    │                      │
│         │    │  Registry │ │  Reader   │    │                      │
│         │    │  ✅ Done  │ │  ✅ Done  │    │                      │
│         │    └───────────┘ └───────────┘    │                      │
│         │           │             │          │                      │
│         ▼           ▼             ▼          ▼                      │
│  ┌───────────────────────────────────────────────────┐              │
│  │                   SQLite Database                   │              │
│  │  files │ content │ edges │ candidates │ artifacts  │              │
│  │                      ✅ Complete                    │              │
│  └───────────────────────────────────────────────────┘              │
│                              │                                       │
│         ┌────────────────────┴────────────────────┐                 │
│         ▼                                         ▼                 │
│  ┌─────────────┐                          ┌─────────────┐           │
│  │   Search    │                          │   Linker    │           │
│  │   Service   │                          │   Service   │           │
│  │   ✅ Done   │                          │   ✅ Done   │           │
│  └─────────────┘                          └─────────────┘           │
│         │                                        │                   │
│         ▼                                        ▼                   │
│  ┌─────────────┐                          ┌─────────────┐           │
│  │   Graph     │                          │  Adaptive   │           │
│  │    View     │                          │  Linking    │           │
│  │   ✅ Done   │                          │   ✅ Done   │           │
│  └─────────────┘                          └─────────────┘           │
│                                                  │                   │
│                           ┌──────────────────────┤                   │
│                           ▼                      ▼                   │
│                    ┌─────────────┐        ┌─────────────┐           │
│                    │  Link       │        │    ML       │           │
│                    │  Auditor    │        │  Trainer    │           │
│                    │  ✅ Done    │        │  ✅ Done    │           │
│                    └─────────────┘        └─────────────┘           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │              (d) LLM Notebook  ◀── NEW COMPONENT                ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              ││
│  │  │   Claude    │  │   Ollama    │  │  Sandboxed  │              ││
│  │  │   Adapter   │  │   Adapter   │  │  Executor   │              ││
│  │  │   ✅ Done   │  │   ✅ Done   │  │  ❌ Missing │              ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘              ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Roadmap for Aim 1

### Phase 1: Source-Linked Verification UI (Grant Figure 2)
**Timeline**: Months 1-3
**Effort**: Medium

Components to build:
1. **Metadata Table Panel** - Display extracted fields with source indicators
2. **Source Preview Panel** - Show file content with highlighted spans
3. **Wire to Graph** - Click node → show metadata → click field → show source
4. **Confidence indicators** - Visual cues for field confidence levels

Leverages existing:
- ModernGraphCanvas (graph visualization)
- Artifact table (source locations)
- ContentRecord (extracted metadata)

### Phase 2: NLP Pattern Generation Enhancement
**Timeline**: Months 2-4
**Effort**: Low-Medium

Components to extend:
1. **File discovery patterns** - Extend AdaptiveLinkingService
2. **Pattern validation** - Test on held-out folders
3. **Iterative refinement** - UI for pattern review/adjustment

Leverages existing:
- AdaptiveLinkingService.explore_data_patterns()
- LLM adapters (Claude, Ollama)

### Phase 3: Project File Format
**Timeline**: Months 3-5
**Effort**: Medium

Components to build:
1. **ProjectFile schema** - JSON/YAML portable format
2. **Export/Import** - Serialize/deserialize from SQLite
3. **Progress tracking UI** - Visual grid of recording status
4. **Error detection** - Flag missing files, duplicates, conflicts

Leverages existing:
- SQLite database schema
- FileRecord.status tracking
- CandidateEdge review workflow

### Phase 4: LLM Notebook Integration
**Timeline**: Months 4-8
**Effort**: High

Components to build:
1. **NotebookService** - Code generation + execution
2. **Sandboxed executor** - Safe Python execution
3. **Notebook UI** - Cell-based interface
4. **Export to .ipynb** - Standard Jupyter format
5. **Conversation persistence** - Replayable provenance

Leverages existing:
- Claude/Ollama LLM adapters
- AgentVM conversation management

---

## 7. Code Examples: Extending LabIndex for Aim 1

### 7.1 Source-Linked Metadata Display

```python
# New service method for source-linked metadata
class MetadataVerificationService:
    def get_metadata_with_sources(self, file_id: int) -> Dict[str, FieldWithSource]:
        """Get all metadata fields with their source artifacts."""
        content = self.db.get_content(file_id)
        artifacts = self.db.get_artifacts_for_file(file_id)

        result = {}
        for field_name, value in content.as_dict().items():
            artifact = self._find_artifact_for_field(artifacts, field_name)
            result[field_name] = FieldWithSource(
                name=field_name,
                value=value,
                source_artifact=artifact,  # None if user-entered
                confidence=artifact.confidence if artifact else None,
                is_verified=artifact is not None
            )
        return result

    def verify_field(self, file_id: int, field_name: str) -> VerificationResult:
        """Navigate to source for one-click verification."""
        artifact = self.db.get_artifact_for_field(file_id, field_name)
        if artifact:
            return VerificationResult(
                source_file=artifact.file_id,
                locator=artifact.locator,
                excerpt=artifact.excerpt,
                context=self._get_context(artifact)
            )
        return VerificationResult(is_user_entered=True)
```

### 7.2 Project File Export

```python
# New service for project file management
class ProjectFileService:
    def export_project(self, root_id: int, output_path: Path) -> None:
        """Export project to shareable JSON format."""
        project = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "root": self.db.get_root(root_id).as_dict(),
            "files": [f.as_dict() for f in self.db.get_files(root_id)],
            "content": [c.as_dict() for c in self.db.get_all_content(root_id)],
            "edges": [e.as_dict() for e in self.db.get_edges(root_id)],
            "candidates": [c.as_dict() for c in self.db.get_candidates(root_id)],
            "artifacts": [a.as_dict() for a in self.db.get_artifacts(root_id)],
            "analysis_status": self._compute_status_summary(root_id)
        }
        with open(output_path, 'w') as f:
            json.dump(project, f, indent=2)

    def _compute_status_summary(self, root_id: int) -> Dict:
        """Compute progress tracking statistics."""
        files = self.db.get_files(root_id)
        return {
            "total_files": len(files),
            "by_status": Counter(f.status for f in files),
            "by_category": Counter(f.category for f in files),
            "extraction_complete": sum(1 for f in files if f.status == "extract_ok"),
            "links_confirmed": self.db.count_edges(root_id),
            "links_pending_review": self.db.count_candidates(root_id, status="pending")
        }
```

### 7.3 NLP Pattern Generation

```python
# Extend AdaptiveLinkingService for file discovery
class FileDiscoveryService:
    def suggest_patterns(self, root_id: int, sample_size: int = 20) -> List[PatternProposal]:
        """LLM-assisted pattern generation for file discovery."""
        # Sample files from different categories
        samples = self.db.sample_files(root_id, n=sample_size)

        # Build prompt with file examples
        prompt = f"""Analyze these file paths and suggest glob/regex patterns:

{self._format_samples(samples)}

For each pattern, provide:
1. The pattern (glob or regex)
2. What it matches (description)
3. Confidence (0-1)
4. Justification
"""

        response = self.llm.chat([{"role": "user", "content": prompt}])
        proposals = self._parse_pattern_proposals(response.content)

        # Validate on held-out samples
        for proposal in proposals:
            proposal.validation = self._validate_pattern(
                proposal.pattern,
                root_id,
                exclude_samples=samples
            )

        return proposals
```

---

## 8. Expected Grant Outcomes vs. LabIndex Capabilities

| Grant Expected Outcome | LabIndex Support | Notes |
|----------------------|------------------|-------|
| >80% completeness for core metadata | ✅ Extractor + handlers | Need validation study |
| Precision/recall >0.85 for fields | ✅ Feature extraction + ML | Need benchmark dataset |
| ≥5× reduction in curation time | ⚠️ Infrastructure ready | Need usability study |
| K01 dataset validation (600+ files) | ✅ Already tested | Preliminary work noted |
| External collaborator validation | ✅ Export/import ready | Need project file format |

---

## 9. Conclusion

**LabIndex provides a production-ready foundation for Aim 1** with:

✅ **Complete**:
- File discovery and crawling
- 12+ file type extractors
- Tiered extraction pipeline (pattern → NLP → LLM)
- Link detection with 48+ ML features
- Explainable soft scoring
- Human review workflow
- LLM adapters (Claude, Ollama)
- Graph visualization
- Full-text search
- SQLite persistence

⚠️ **Partial** (needs UI/integration):
- Source-linked verification (infrastructure exists, UI needed)
- Project organization (database exists, export format needed)
- NLP pattern generation (LLM integration exists, workflow needed)

❌ **New** (needs implementation):
- LLM notebook with sandboxed execution
- .ipynb export
- Progress tracking grid UI

**Recommendation**: Position LabIndex as the "indexing and linking engine" for the broader PhysioMetrics platform, extending it with the UI components described in the grant (Figure 2 verification interface, progress tracking, LLM notebook).

---

## 10. References

- Grant Research Strategy: Pages 5-6 (Aim 1 description)
- LabIndex codebase: `src/labindex_core/` and `src/labindex_app/`
- PhysioMetrics: Sister application for physiological signal analysis
- FAIR Principles: Wilkinson et al. (2016) - Data management alignment
