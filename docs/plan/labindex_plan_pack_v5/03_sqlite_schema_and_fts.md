# 03 — SQLite Schema + FTS5

## Storage location
- Store DB on local SSD (never on network share).
- Enable WAL: `PRAGMA journal_mode=WAL;`

## Core tables (minimum)
### `roots`
- root_id, root_path, label, scan_config_json, timestamps

### `files`
- file_id, root_id, path, parent_path, name, ext, mime_guess
- size_bytes, mtime, ctime, is_dir
- category (derived)
- quick_fingerprint (size+mtime+optional hash sample)
- status_inventory/status_extract/status_llm + last_indexed_at + error_msg
Indexes:
- UNIQUE(root_id, path)
- (root_id, parent_path), (name), (ext), (mtime)

### `content`
- file_id (PK/FK), title, summary, keywords_json, entities_json
- content_excerpt, content_text (optional small only)
- extraction_version, extracted_at

### `edges`
- edge_id, src_file_id, dst_file_id, relation_type
- confidence, evidence, evidence_file_id, created_by, created_at
Indexes:
- (src_file_id), (dst_file_id), (dst_file_id, relation_type)

### `jobs`
- job_id, job_type, file_id(nullable), payload_json
- status, priority, attempts, locked_by/locked_at, timestamps

## Full-text search (FTS5)
Create `fts_docs` virtual table with:
- path, name, title, summary, keywords, entities, excerpt
Maintain via:
- triggers OR explicit update step in extractor pipeline

## Concurrency guidance
- Prefer a dedicated DB writer thread OR per-thread connections.
- Keep transactions small (per file/job).


## Extensions
- `candidate_edges`: stores proposed links prior to promotion into `edges` (see `06_linking_and_edges.md`).
- `artifacts`: stores sub-document anchors (row/cell/span/slide/cell) to support evidence-backed navigation (see `16_...`).
- `audits`: optional table for LLM auditor verdicts (see `17_...`).
