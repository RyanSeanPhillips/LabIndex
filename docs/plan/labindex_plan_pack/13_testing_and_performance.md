# 13 — Testing, QA, and Performance

## Safety tests
- unit tests patch forbidden calls (remove/rename/write)
- integration test on read-only mount

## Correctness tests
- fixtures with synthetic folder trees
- known “notes_for” pairs and expected edges
- ABF/SMRX header parsing sanity checks

## Performance tests
- crawl throughput on representative network share
- query latency: FTS and filename lookup
- memory usage under large result sets

## Observability
- structured logs (crawl/extract/link/agent tool calls)
- job stats and error dashboards
- prompt/extractor version logging
