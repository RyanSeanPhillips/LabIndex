# 17 — Addendum: LLM Link Auditor + Feature Extraction Layer (for future ML)

This addendum extends the existing plan pack and the **LLM‑Guided Linker Tuning** document (`16_llm_guided_linking_and_evidence_navigation.md`) with:

1. A **bounded LLM “Link Auditor”** pattern (rules propose; LLM validates marginal cases)
2. A durable **feature extraction layer** to enable future ML scorers without redesign

---

## 1) Design intent

### 1.1 Keep determinism in the hot path
- Candidate generation + primary scoring should be deterministic and fast.
- The LLM should act as a **gated auditor** for ambiguous or high-impact cases.

### 1.2 Preserve auditability
- Every decision must be traceable to:
  - evidence anchor(s)
  - feature values
  - versioned rule/scorer configuration
  - optional auditor verdict (also evidence-bounded)

### 1.3 Enable future ML with minimal migration cost
- Introduce feature extraction now.
- Make the scoring stage **pluggable** so you can swap:
  - weighted rules → ML model → hybrid rule+ML
without changing candidate generation, evidence capture, or UI.

---

## 2) LLM Link Auditor (bounded validation)

### 2.1 What it does
Given a proposed link (note row/cell/span → data file), the auditor answers:
- Is this link supported by the provided evidence?
- If not, what is missing?
- If ambiguous, what additional tool call would disambiguate?

The auditor **must not** create links autonomously; it only:
- returns a verdict and confidence
- requests more evidence via tool suggestions (optional)
- provides a short rationale grounded in evidence

### 2.2 When to call the auditor (gating policy)
Call the auditor only when at least one condition holds:
- **Tie / near-tie**: top two candidates within Δscore threshold
- **No exact match**: requires typo/sequence inference
- **Constraint conflict**: one-to-one violation or duplicate mapping
- **Low-evidence edge**: candidate would be promoted but evidence type is weak
- **User-triggered**: user explicitly requests verification

Default path (no auditor) should cover the majority of links.

### 2.3 Auditor inputs (strictly bounded)
Provide only:
- `src_file_id`, `dst_file_id`, `relation_type`
- **evidence anchor** content:
  - excerpt from notes (row/col or lines; include small neighborhood)
- minimal candidate context:
  - normalized basenames
  - path proximity summary (same folder/parent/sibling)
  - ABF/SMRX header summary (channels, start time if available)
  - optional: neighboring row fields (video file, chamber, animal id)
- ambiguity context:
  - top-N alternative candidates with short summaries
- budgets:
  - max tokens
  - max tool calls (if you allow auditor to request “read more”)

Never provide entire documents unless explicitly user-requested.

### 2.4 Auditor outputs (forced JSON schema)
Require JSON only, e.g.:

```json
{
  "verdict": "accept | reject | needs_more_info",
  "confidence": 0.0,
  "rationale": "Evidence-based, short.",
  "missing_evidence": ["..."],
  "recommended_next_steps": [
    {"tool": "read_snippet", "args": {"file_id": 123, "mode": "head", "max_bytes": 8000}},
    {"tool": "get_related", "args": {"file_id": 456, "relation_types": ["notes_for"], "depth": 1}}
  ],
  "suggested_corrections": [
    {"dst_file_id": 789, "confidence": 0.62, "why": "Numeric suffix continuity and matching chamber column."}
  ]
}
```

### 2.5 Storage (audit trail)
Persist auditor results as first-class records:
- `audits` table OR fields on `candidate_edges`:
  - `auditor_model`, `auditor_prompt_version`
  - `auditor_verdict`, `auditor_confidence`
  - `auditor_rationale_excerpt`
  - `auditor_trace_id`
  - `audited_at`

Never “hide” auditor outputs; make them inspectable in the UI.

---

## 3) Feature Extraction Layer (future-proofing for ML)

### 3.1 Placement in the pipeline
Pipeline becomes:

1. Candidate generation (rules; high recall)
2. Evidence extraction (anchors; structured cell/span)
3. **Feature extraction (this addendum)**
4. Scoring / validation (weighted rules now; ML later)
5. Constraint resolver
6. Promotion policy (validated vs candidate)

### 3.2 Feature schema (recommended minimum set)
Store a feature vector per `(src, dst, relation_type)` candidate.

#### A) Path/name similarity
- `exact_basename_match` (0/1)
- `normalized_basename_match` (0/1)
- `edit_distance` (int)
- `rapidfuzz_ratio` (float)
- `numeric_suffix_delta` (int or null)
- `same_folder` / `parent_folder` / `sibling_folder` (0/1)

#### B) Evidence quality
- `evidence_type` (enum: explicit_mention | column_cell | inferred_sequence | proximity_only)
- `evidence_strength` (float: derived from rules)
- `has_canonical_column_match` (0/1)
- `column_header_similarity` (float)
- `evidence_span_len` (int)

#### C) Context agreement
- `date_token_agreement` (0/1 or score)
- `animal_id_agreement` (0/1 or score)
- `chamber_agreement` (0/1 or score)
- `video_filename_agreement` (0/1 or score)
- `abf_header_signature_match` (0/1 or score)

#### D) Uniqueness / conflict
- `num_candidates_for_src` (int)
- `num_candidates_for_dst` (int)
- `violates_one_to_one` (0/1)
- `dst_already_linked` (0/1)

#### E) Optional supervision signals
- `user_label` (accepted/rejected/unknown)
- `auditor_verdict` + `auditor_confidence` (as features, optional)

### 3.3 Storage options
Start simple:
- `candidate_edges.features_json` + `feature_schema_version`

Upgrade later (for analytics/training):
- `candidate_edge_features` table with one row per feature (normalized) or
- a wide table with fixed columns (fast for training exports)

### 3.4 Export for training
Implement a metadata-only exporter:
- `export_training_set(relation_type, date_range, filters)` → CSV/Parquet
Include:
- features
- labels (user accept/reject)
- auditor verdict (optional)
- provenance fields

---

## 4) Pluggable scorer interface

### 4.1 Interface
Define a scorer protocol:

- `score(candidate, features, evidence) -> ScoreResult`
- `ScoreResult`: `{score, confidence, reasons[], required_evidence_types[]}`

### 4.2 Scorer implementations
- `WeightedRuleScorerV1`: current production scorer
- `MLScorerV1`: a learned model (later) that outputs probability
- `HybridScorerV1`: weighted rules + ML rerank on top-K

### 4.3 Migration plan
- Keep candidate generation identical.
- Keep evidence anchors identical.
- Swap scorer with configuration + versioning only.

---

## 5) UI implications (minimal but important)

### 5.1 Review panel
For each candidate edge show:
- score + confidence
- top contributing features (“why”)
- evidence excerpt with jump-to-anchor
- auditor verdict (if present) and rationale excerpt
- buttons: Accept / Reject / Edit target

### 5.2 Debug tooling (for you)
- “Explain this link” → feature breakdown + rules fired + auditor outcome
- “Why not linked?” → missing evidence checklist

---

## 6) Budgets and safety
- Auditor calls must be rate-limited and cached.
- Tools remain read-only; auditor never receives write tools.
- Cache key: `(src_file_fingerprint, evidence_anchor_id, dst_file_fingerprint, scorer_version, prompt_version)`

---

## 7) Implementation checklist
1. Add `features_json` + `feature_schema_version` to `candidate_edges` (or new table)
2. Implement `extract_features(candidate_edge)` for your relation types
3. Implement `WeightedRuleScorerV1` as a pure function over features
4. Implement auditor tool contract + JSON enforcement
5. Add `audits` storage and UI display
6. Add training export utility
