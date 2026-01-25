# 04 — Crawler (Tier 0 Inventory)

## Goals
- Fast directory enumeration on a network drive.
- Minimal syscalls: `os.scandir()` + stat info.
- Resumable and crash-safe.

## Algorithm
- Queue directories starting from selected root(s).
- For each dir:
  - `scandir` entries
  - upsert into `files` (is_dir=1 for folders, 0 for files)
  - enqueue subdirectories
- Record per-dir checkpoint to avoid repeated work.

## Incremental updates
- Re-scan strategy:
  - new/changed dirs more often (mtime heuristics)
  - configurable max depth for initial pass
- Changes detected by:
  - directory listing hash or file count+mtime sampling
  - file-level: (size, mtime) change → mark extract pending

## Jobs
- `crawl_dir` jobs per directory.
- Locking: claim job → run → mark done/error.

## Performance knobs
- Concurrency: 2–8 worker threads (network share dependent).
- Backoff on slow/errored paths.
- Avoid hashing full file contents.

## Outputs
- Populates `files` and sets `status_inventory=ok` or `error`.
