# 16 — LLM‑Guided Linker Tuning & Evidence‑Backed Navigation

This component builds on:
- `06_linking_and_edges.md` (rule‑based linker + `candidate_edges`)
- `08_llm_agent_and_tools.md` (tooling patterns)
- `09_learning_writeback.md` (safe, provenance‑tracked “learning”)

Purpose: use an LLM **as a controlled assistant** to (a) learn lab‑specific conventions, (b) propose and iterate on linking rules, and (c) improve precision/recall without turning the LLM into the primary decision-maker.

---

## 1) Non‑negotiables
- **Read‑only to the drive**: no writes, renames, deletes, or moves; all outputs go to the local DB/cache.
- **Evidence required**: every promoted link stores an evidence anchor (row/cell/span) and a short excerpt.
- **Version everything**: linker strategy, prompt versions, and rule sets are immutable once activated (new versions for changes).

---

## 2) Two‑stage linking (retainable + debuggable)

### 2.1 Stage A: Candidate generation (high recall, cheap)
Populate `candidate_edges` using deterministic signals:
- path proximity (same folder / parent / sibling conventions)
- basename matching (normalized; extension‑optional)
- known file‑type roles (ABF/SMRX as “data”; XLSX/CSV/MD/TXT as “notes”)
- token matches (animal IDs, dates, chamber IDs, rig IDs)

Candidates are not shown by default unless requested.

### 2.2 Stage B: Validation & promotion (high precision)
Promote `candidate_edges → edges` only when at least one *strong* evidence condition holds:
- explicit filename mention (with extension) in extracted text
- spreadsheet/table cell evidence in canonical column (e.g., “pleth file”)
- compatible context fields (video file, chamber, animal id) match extracted metadata
- sequence logic resolves missing/duplicate references with secondary evidence

Use a scoring threshold and enforce constraints (e.g., one‑to‑one per session row where applicable).

---

## 3) Evidence anchors (“click to the exact spot”)

### 3.1 Artifact anchors
Introduce an `artifacts` concept to represent sub‑document anchors. Each anchor has:
- `file_id` (parent file)
- `artifact_type`:
  - `text_span` (txt/md/docx text run)
  - `table_cell` / `table_row` (csv/xlsx)
  - `ppt_slide` (pptx slide number + shape id)
  - `ipynb_cell` (cell index + output index)
- `locator_json` sufficient to re-open and highlight the evidence
- `excerpt` (small; safe for display and audit)

### 3.2 Edge evidence
For each promoted edge store:
- `evidence_artifact_id`
- `evidence_excerpt`
- `created_by` (rule / llm / user)
- `confidence`
- `linker_strategy_version`

---

## 4) “Linker Trainer” (LLM‑assisted rule induction)

### 4.1 Why a trainer
Lab organization is idiosyncratic:
- notes in parent folder vs same folder
- filename referenced without extension
- “pleth file” column containing basenames
- sequence copy/paste errors and typos

Trainer goal: converge quickly on a small, robust set of rules.

### 4.2 Trainer workflow (branch‑scoped deep dive)
1. **Select subtree** (project branch)
2. **Sample files** (N notes + N data + optional videos)
3. **Summarize conventions** (cheap analytics):
   - common column headers + header synonyms
   - common filename patterns (prefix + numeric suffix)
   - common folder layouts (notes ↔ data ↔ video)
4. **LLM discussion**:
   - show summaries and a few small, representative evidence snippets
   - ask only the minimum clarifying questions
5. **Rule proposal**:
   - LLM outputs a constrained JSON strategy:
     - header synonym map (e.g., “pleth file” variants)
     - filename normalization rules
     - relation‑specific evidence requirements
     - thresholds and disambiguation policies
6. **Evaluate**:
   - run the strategy on the branch
   - report precision proxies (conflict counts, candidate explosion rate, top‑K ambiguity)
7. **Human review**:
   - accept/reject samples; store as training labels (future ML) and as regression tests
8. **Activate**:
   - freeze and version the strategy (no edits in place)

### 4.3 LLM output contract (JSON)
LLM returns JSON only:
- `column_mappings`: header variants → canonical fields
- `token_patterns`: regexes for animal ids, dates, chamber ids
- `folder_layout_rules`: allowed note/data proximity patterns
- `relation_rules`: per relation evidence requirements and weights
- `thresholds`: promote/candidate boundaries
- `typo_policy`: edit distance + numeric suffix continuity

---

## 5) Typo + copy/paste increment handling

### 5.1 Detect
- duplicated basenames in a canonical column
- missing expected suffix numbers in a run (based on adjacent rows and existing files)
- rows referencing non-existent files

### 5.2 Suggest
- propose corrected targets using:
  - numeric suffix continuity (±1, ±2)
  - nearest edit-distance matches
  - same session/date/animal/chamber context
- keep as candidates unless auditor/user confirms

---

## 6) Performance & safety
- Trainer and deep scans are **branch-scoped** and budgeted (bytes, files, LLM calls).
- Cache everything by fingerprint to avoid repeated reads over the network share.
- LLM never gets write tools; tool surface is read-only.

---

## 7) Integration notes
- This doc pairs with addendum `17_llm_link_auditor_and_feature_layer.md` for:
  - bounded LLM auditing of ambiguous links
  - feature extraction to enable future ML scorers
