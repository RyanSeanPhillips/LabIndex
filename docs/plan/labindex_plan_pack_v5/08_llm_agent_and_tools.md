# 08 — LLM Agent & Tooling (Read-Only)

## Agent principles
- Tool-using only; no direct filesystem access.
- Operates on `file_id` handles.
- Asks follow-ups on ambiguity; never guesses.
- Always cites evidence (paths + snippet + confidence).

## Tool API (examples)
- `search_files(text, filters, limit)`
- `search_fts(query, filters, limit)`
- `resolve_name_fuzzy(name, filters, limit)`
- `get_related(file_id, relation_types, depth)`
- `read_snippet(file_id, max_bytes, mode=head/tail/sample)`
- `extract_pptx_text(file_id)`
- `parse_abf_header(file_id)` / `parse_smrx_header(file_id)`

## Intent recipes (recommended)
1. Find notes for `XXX.abf`
2. Find conference slides
3. “Have we done experiments with X?” (Cre/virus/protocol)

## Clarifying questions
Trigger when:
- multiple candidates
- missing constraints (year/conference/tool/type)

## Output format
- ranked hits with paths
- evidence snippets
- suggested next actions (expand scope, refine filters)
