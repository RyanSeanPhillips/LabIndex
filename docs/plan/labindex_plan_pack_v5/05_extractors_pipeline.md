# 05 — Extractors Pipeline (Tier 1/2)

## Plugin interface
- `can_handle(ext, mime, size, path) -> bool`
- `extract(file_id, ReadOnlyFS, budgets) -> ContentUpdate`
Budgets:
- `max_bytes`, `max_seconds`, `sample_mode` (head/tail/sample)

## Tier 1 (lightweight)
- md/txt/log: read head N KB
- csv: read header + first M rows
- code: read head N KB
- derive tokens from filename/path

## Tier 2 (format parsing)
- PPTX: slide text + speaker notes (no rendering)
- PDF: limited pages/snippet extraction (budgeted)
- ABF/SMRX: header parsing only (no full data read)
- DOCX: text extraction (budgeted)

## Storage policy
- Prefer `summary`, `entities_json`, `content_excerpt` over full `content_text`.
- Store `extraction_version` and timestamps.

## Scheduling
- `extract_content` jobs created for:
  - new files of supported types
  - changed fingerprints
- Prioritize “notes/slides” over large binaries.

## Failure handling
- Record errors in `files.error_msg` and job status.
- Retry with limited attempts and exponential backoff.
