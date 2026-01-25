# LabIndex — Master Plan (Read‑Only Lab Drive Index + Agent)

This is the **top-level** plan for a PyQt6 app (MVVM) that builds a **local SQLite index** of a large lab/network drive, supports layered extraction and a relationship graph, and provides classic search + an evidence-based LLM agent interface.

This document stays intentionally high-level and points to component plans.

---

## Goals (What you’re building)
- **Read-only** indexing of lab drives (never modify files or structure).
- **Layered indexing** (Tier 0 inventory → Tier 1 lightweight → Tier 2 format parsing → Tier 3 selective LLM enrichment).
- **Search** (filename fuzzy + SQLite FTS5) + **graph navigation** (notes ↔ data ↔ histology).
- **LLM agent** that uses **read-only tools**, asks follow-ups, and cites evidence.
- **Learning loop**: user/agent-confirmed metadata writes back to the **local index DB** (not the filesystem).
- **Embeddable core**: `labindex_core` is headless and reusable from other apps.

---

## Non-negotiables
- **Safety:** file operations must be read-only at OS + app + UI layers.
- **Performance:** keep network I/O minimal; store index locally (SSD).
- **Auditability:** every derived fact/edge has provenance + evidence + confidence.
- **Resumability:** indexing and extraction must be crash-safe and restartable.

---

## Repository structure (recommended)
- `labindex_core/` (headless)
  - `domain/` DTOs and enums
  - `ports/` interfaces (FS, DB, LLM, clock)
  - `adapters/` sqlite, filesystem_ro, llm_provider
  - `services/` crawler, extractor, linker, search, agent_tools
  - `schema/` migrations
- `labindex_app_pyqt/` (UI)
  - `viewmodels/` Search/Explore, Index/Build, Graph, Agent, Inspector
  - `views/` Qt widgets
  - `resources/` icons, styles

---

## Order of implementation (phased)
### Phase 1 — Inventory MVP
1. SQLite schema + migrations (WAL, indices)
2. ReadOnlyFS facade + safety tests
3. Crawler: Tier 0 inventory (scandir/stat), resumable jobs
4. Minimal UI (Index tab): add root → start/pause/stop; show progress
5. Minimal UI (Search tab): filename search (LIKE/fuzzy), results list

### Phase 2 — Search MVP
6. FTS5 (`fts_docs`) + updates
7. Text extraction for lightweight formats (md/txt/py/csv sample)
8. UI: search bar + filters + inspector preview

### Phase 3 — Relationship linking + graph
9. Tokenization (animal/date/session tokens)
10. Rule-based linker (same folder/basename/sibling folders)
11. Graph view (contextual subgraphs) + “find notes for file” UX

### Phase 4 — Selective LLM enrichment
12. LLM schema + prompt versioning + caching
13. Candidate edges + validation/disambiguation flow
14. UI: proposed links accept/reject; show provenance/evidence

### Phase 5 — Agent UX + learning write-back
15. Tool API for agent (file_id handles, budgets)
16. Intent recipes + follow-ups
17. Write-back guardrails (candidate_edges/assertions/alias_map)

### Phase 6 — Integration into experiment/project apps
18. Experiment bundle service/API
19. Optional normalization tables (animals/sessions/procedures)
20. Export utilities (metadata only)

---

## Component documents
1. **Architecture & layered tiers** — `01_architecture_and_tiers.md`
2. **Safety model (read-only)** — `02_safety_readonly.md`
3. **SQLite schema + FTS** — `03_sqlite_schema_and_fts.md`
4. **Crawler (Tier 0)** — `04_crawler_inventory.md`
5. **Extractors (Tier 1/2)** — `05_extractors_pipeline.md`
6. **Linker + graph edges** — `06_linking_and_edges.md`
7. **Retrieval (SQL/FTS/fuzzy/optional vectors)** — `07_retrieval_and_ranking.md`
8. **LLM agent tools + recipes** — `08_llm_agent_and_tools.md`
9. **Learning/write-back guardrails** — `09_learning_writeback.md`
10. **PyQt6 UI + MVVM** — `10_ui_mvvm_design.md`
11. **Plugin registries & hot-swapping** — `11_plugins_and_iteration.md`
12. **Experiment/project integration** — `12_experiment_integration.md`
13. **Testing, QA, and performance** — `13_testing_and_performance.md`

---

## Acceptance criteria (high level)
- Runs against a read-only mounted share.
- Search feels instantaneous (local DB).
- “Find notes for this ABF” works via rules + FTS without LLM.
- Agent answers always cite evidence and asks follow-ups on ambiguity.
- No index pollution: proposed links are reviewable and provenance-tracked.


## Add-ons
- `14_standards_mcp_and_agent_sdks.md` — Notes on agent tool standards (MCP, tool schemas, safety).
- `16_llm_guided_linking_and_evidence_navigation.md` — LLM-assisted linker tuning and evidence anchors.
- `17_llm_link_auditor_and_feature_layer.md` — Bounded auditor + feature layer for future ML.
