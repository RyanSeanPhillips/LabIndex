# 01 — Architecture & Layered Tiers

## System overview
- **Network Drive (Read-only):** the source of truth.
- **Local Index (SQLite + FTS5):** durable, queryable metadata store.
- **Workers:** crawler, extractor, linker, LLM enricher.
- **UI (PyQt6 MVVM):** Index/Build + Search/Explore tabs.
- **Agent:** tool-using, evidence-based, strictly read-only.

## Tier model (indexing)
- **Tier 0: Inventory**
  - scandir/stat only; no file opens.
  - outputs: `files` rows.
- **Tier 1: Lightweight signals**
  - sampled text reads for small/text files; filename/path tokenization.
  - outputs: `content_excerpt`, basic tags, FTS docs.
- **Tier 2: Format parsing**
  - PPTX text, PDF snippet, ABF/SMRX headers; strict budgets.
  - outputs: structured entities; higher-confidence rule links.
- **Tier 3: Selective LLM enrichment**
  - summaries/entities; candidate edges with evidence + confidence.

## Layered retrieval
- Candidate generation: SQL filters + FTS.
- Then: optional fuzzy rerank and/or embeddings on top-N only.
- Optional LLM rerank on tiny shortlist only (budgeted + cached).

## Data flow
1. Crawl → inventory
2. Extract → content + FTS
3. Link → edges
4. Query → results + contextual subgraph
5. Learn (optional) → write-back to local index with guardrails
