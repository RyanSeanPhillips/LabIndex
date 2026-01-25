# 09 — Learning / Write-Back to the Index (Safe Improvement)

## Why
Agent and targeted reads can discover new metadata (mentions, links, entities). Persisting it makes future retrieval faster and better.

## Strict rule
Write-back only to **local SQLite index**, never to the network drive.

## What can be written back
- `edges` (validated links)
- `candidate_edges` (needs review)
- `assertions` (entity facts with evidence/confidence)
- `alias_map` (user/system alias → canonical)

## Guardrails to prevent index pollution
- provenance required (created_by, tool_trace_id, versions)
- evidence required (snippet/offset/header field)
- confidence thresholds for auto-accept
- curated truth never overwritten
- invalidation when evidence source changes

## UX
- show “Proposed link” cards with Accept/Reject/Edit
- optional “auto-accept high confidence” mode for power users
