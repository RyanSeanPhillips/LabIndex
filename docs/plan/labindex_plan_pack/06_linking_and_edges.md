# 06 — Linking & Edges (Graph Construction)

## Controlled relation types (start small)
- `notes_for`, `describes`, `generated_from`, `analysis_of`
- `same_animal`, `same_session`, `histology_for`, `surgery_notes_for`
- `mentions` (soft link)

## Rule-based linker (high precision first)
- Same folder notes → nearby data files.
- Same basename: `X.abf` ↔ `X_notes.*`.
- Sibling folders: `raw/` ↔ `notes/` ↔ `analysis/` ↔ `figures/`.
- Token match: animal/date/session tokens across names.

## LLM-assisted linking (optional; validated)
- Agent/LLM proposes `candidate_edges` with evidence + confidence.
- Validation step resolves dst targets (fuzzy + context filters).
- Ambiguous edges remain candidates until user confirmation.

## Evidence policy
- Every edge must store:
  - confidence
  - evidence snippet or extracted field reference
  - created_by (rule/llm/user)
  - versioning metadata

## Outputs
- Durable `edges` rows + optional `candidate_edges` for review.
