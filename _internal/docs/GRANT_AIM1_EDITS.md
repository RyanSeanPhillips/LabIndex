# Aim 1 Approach Section - Suggested Edits for LabIndex Integration

> **Document Purpose**: Line-by-line guidance on where to reference LabIndex in the grant's Aim 1 Approach section
> **LabIndex DOI**: 10.5281/zenodo.18458509 (update when available)
> **GitHub**: https://github.com/RyanSeanPhillips/LabIndex

---

## Overview: Where LabIndex Fits

LabIndex should be referenced as **preliminary work demonstrating feasibility**, not as completed work. The grant funds **rigorous validation**, not initial development.

```
Current Grant Structure for Aim 1:
├── C.1 Aim 1: NLP-Based Data Curation...
│   ├── (a) File Discovery          ← LabIndex: CrawlerService
│   ├── (b) Tiered Metadata...      ← LabIndex: ExtractorService + handlers
│   ├── (c) Project Organization... ← LabIndex: SQLite schema (partial)
│   ├── (d) Integrated Notebook...  ← LabIndex: LLM adapters (foundation only)
│   ├── Expected Outcomes
│   ├── Potential Pitfalls...
│   └── Validation
```

---

## Section-by-Section Edit Guide

### 1. Opening Paragraph (page 5, after section header)

**CURRENT TEXT:**
> "Data analysis requires organized datasets, but data curation is a major bottleneck..."

**SUGGESTED ADDITION** (after "...diverts researcher time from scientific questions"):

```markdown
ADD AFTER "...typically lacks any link between extracted metadata and its original source.":

To address this gap, we have developed LabIndex (GitHub: RyanSeanPhillips/LabIndex;
DOI: 10.5281/zenodo.18458509), a prototype indexing system demonstrating the
feasibility of tiered extraction with source-linked verification. The proposed
work will rigorously validate these methods and integrate them into the
PhysioMetrics platform.
```

---

### 2. Section (a) File Discovery

**CURRENT TEXT (page 5):**
> "(a) File Discovery. Data files and associated notes are often scattered across folder hierarchies... *Preliminary work: The current release includes file and notes discovery with basic pattern matching, tested on the K01 dataset structure (600+ files).*"

**SUGGESTED EDIT** - Replace the preliminary work sentence:

```markdown
REPLACE:
"Preliminary work: The current release includes file and notes discovery with
basic pattern matching, tested on the K01 dataset structure (600+ files)."

WITH:
"Preliminary work: LabIndex implements recursive directory scanning with
automatic file categorization (50+ extensions across 8 categories: DATA,
DOCUMENTS, SPREADSHEETS, IMAGES, CODE, SLIDES, VIDEO, ARCHIVES). The crawler
service has been tested on the K01 dataset structure (600+ files, 7 genotypes)
with sub-second indexing performance. The proposed work will add NLP-assisted
pattern generation with validation on held-out folders."
```

---

### 3. Section (b) Tiered Metadata Extraction with Source Linking

**CURRENT TEXT (page 5):**
> "(b) Tiered Metadata Extraction with Source Linking... *Preliminary work: The tiered pipeline tested on surgery notes achieved 32%/44%/70–85% completeness (core fields) across tiers; source linking interface is working.*"

**SUGGESTED EDIT** - Expand the preliminary work:

```markdown
REPLACE:
"Preliminary work: The tiered pipeline tested on surgery notes achieved
32%/44%/70–85% completeness (core fields) across tiers; source linking
interface is working."

WITH:
"Preliminary work: LabIndex implements the three-tier architecture with 12+
file-type extractors (ABF, SMRX, NPZ, PDF, DOCX, XLSX, CSV, etc.). Tier 1
pattern extraction achieves high accuracy for standardized formats (e.g.,
channel names and sampling rates from ABF headers). Tier 2 NLP extraction
includes entity detection (animal IDs, dates, treatments) and reference
finding. Tier 3 LLM extraction uses Claude/Ollama adapters with budget-
controlled gating conditions. Testing on surgery notes achieved 32%/44%/70-85%
completeness across tiers. The source linking infrastructure (Artifact table
with text span, table cell, and row locators) is implemented; the proposed
work will build the one-click verification UI and validate extraction
precision/recall."
```

---

### 4. Section (c) Project Organization with Progress Tracking

**CURRENT TEXT (page 5-6):**
> "(c) Project Organization with Progress Tracking... *Preliminary work: The project system has been deployed on K01 datasets (600+ files across 7 genotypes) and is being used for ongoing analysis.*"

**SUGGESTED EDIT** - Add detail:

```markdown
REPLACE:
"Preliminary work: The project system has been deployed on K01 datasets
(600+ files across 7 genotypes) and is being used for ongoing analysis."

WITH:
"Preliminary work: LabIndex stores curated metadata in SQLite with status
tracking per file (PENDING → INVENTORY_OK → EXTRACT_OK → LLM_OK). The
database schema includes tables for files, content, edges (confirmed links),
candidate_edges (review queue), and artifacts (source anchors). The system
has been deployed on K01 datasets (600+ files across 7 genotypes). The
proposed work will add shareable project file export and visual progress
tracking UI."
```

---

### 5. Section (d) Integrated Notebook with LLM-Assisted Code Generation

**CURRENT TEXT (page 6):**
> "(d) Integrated Notebook with LLM-Assisted Code Generation... *Preliminary work: The LLM notebook with code execution is working.*"

**SUGGESTED EDIT** - Clarify what exists vs. proposed:

```markdown
REPLACE:
"Preliminary work: The LLM notebook with code execution is working."

WITH:
"Preliminary work: PhysioMetrics includes a working LLM notebook with code
execution. LabIndex provides the underlying LLM infrastructure with Claude
(Anthropic API) and Ollama (local) adapters supporting tool calling and
conversation management. The proposed work will integrate sandboxed execution
with explicit dependency capture and .ipynb export for reproducibility."
```

---

### 6. Add to "Potential Pitfalls and Alternatives" (page 6)

**CURRENT TEXT:**
> "Potential Pitfalls and Alternatives. (1) LLM extraction accuracy may vary with notes quality; the tiered approach ensures pattern matching handles standard formats, and source linking enables human verification..."

**SUGGESTED ADDITION** at the end of this section:

```markdown
ADD:
"(4) The tiered extraction architecture may need refinement for new file types;
LabIndex's plugin-based handler system enables adding new extractors without
modifying core logic, and the 48+ feature extraction pipeline for link
confidence scoring provides a foundation for iterative improvement."
```

---

### 7. Validation Section (page 6)

**CURRENT TEXT:**
> "Validation. We will validate Aim 1 methods on the K01 dataset (600+ files, 7 genotypes) plus one external collaborator dataset..."

**SUGGESTED EDIT** - Add baseline reference:

```markdown
REPLACE:
"We will validate Aim 1 methods on the K01 dataset (600+ files, 7 genotypes)
plus one external collaborator dataset."

WITH:
"We will validate Aim 1 methods on the K01 dataset (600+ files, 7 genotypes)
plus one external collaborator dataset. LabIndex provides the baseline
implementation; the proposed work will establish precision/recall benchmarks
with expert-labeled ground truth and measure improvement from each tier of
extraction."
```

---

## Summary Table: What to Add Where

| Section | Current State | Add |
|---------|--------------|-----|
| Opening | Generic problem statement | LabIndex as prototype demonstrating feasibility |
| (a) File Discovery | "basic pattern matching" | 50+ extensions, 8 categories, sub-second performance |
| (b) Tiered Extraction | "32%/44%/70-85%" | 12+ extractors, 3-tier architecture, LLM gating |
| (c) Project Organization | "deployed on K01" | SQLite schema, status tracking, artifact locators |
| (d) LLM Notebook | "working" | Claude/Ollama adapters, tool calling infrastructure |
| Pitfalls | 3 items | Add #4: plugin architecture for extensibility |
| Validation | K01 + collaborator | LabIndex as baseline for benchmarking |

---

## Key Framing Guidelines

### DO Say:
- "LabIndex demonstrates the **feasibility** of..."
- "The **prototype** implements..."
- "The proposed work will **rigorously validate**..."
- "LabIndex provides the **baseline** for..."
- "The proposed work will **establish benchmarks**..."

### DON'T Say:
- ~~"LabIndex already achieves..."~~ (sounds like work is done)
- ~~"We have completed..."~~ (no need for funding)
- ~~"LabIndex solves..."~~ (oversells)

---

## Citation Format

For the References section, add:

```bibtex
@software{phillips_labindex_2026,
  author       = {Phillips, Ryan S.},
  title        = {{LabIndex}: {NLP}-Assisted Lab Directory Indexing and
                  File Relationship Discovery},
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v0.1.0},
  doi          = {10.5281/zenodo.18458509},
  url          = {https://github.com/RyanSeanPhillips/LabIndex}
}
```

In-text citation: "We have developed LabIndex,^XX an open-source prototype..."

---

## Figure 2 Note

The grant has a placeholder for Figure 2 (Source-linked metadata extraction). LabIndex's graph visualization could provide a screenshot, but ensure the caption emphasizes it's a **prototype** with the proposed work adding the full three-panel verification interface.

---

## Checklist Before Submission

- [ ] Update DOI placeholder (10.5281/zenodo.18458509) with real DOI
- [ ] Update GitHub URL if needed
- [ ] Add reference to References section
- [ ] Ensure all "preliminary work" statements use appropriate framing
- [ ] Verify LabIndex repo is public and accessible to reviewers
