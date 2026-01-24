# 07 — Retrieval & Ranking (SQL/FTS/Fuzzy/Optional Vectors)

## Candidate generation
- filename/path LIKE queries + token normalization
- SQLite FTS5 on title/summary/entities/excerpts
- filters: ext/category/date_range/path_prefix/root

## Fuzzy matching
- tokenized similarity for filenames
- trigram similarity (or rapidfuzz) for near misses
- alias dictionaries for domain terms (Cre/FLEx/DIO/virus)

## Graph expansion
- `get_neighbors(file_id, relation_types, depth)`
- “Find notes for this file” = edges + proximity fallback

## Optional semantic layer
- store embeddings for summaries/excerpts of selected types
- rerank top-N from FTS (N small, e.g., 50)

## Performance
- keep heavy operations off UI thread
- cache repeated queries
