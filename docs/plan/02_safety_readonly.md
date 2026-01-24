# 02 — Safety Model (Read-Only by Construction)

## Principles
- Never write to the lab drive.
- Only write to the **local SQLite index** (and local caches).
- Enforce at OS + app + UI levels.

## OS-level
- Prefer read-only mount/options for SMB/NFS.
- Run under read-only permissions.
- Optional container with bind-mount `:ro` + AppArmor/SELinux deny-write.

## App-level (required)
- Centralize all file access in `ReadOnlyFS`.
- Allowed operations: `scandir/list_dir`, `stat`, `open_read`.
- Enforce budgets (bytes/time), never accept agent-supplied paths (use `file_id`).

## Guardrails
- Pre-commit hooks: block dangerous calls (`open(...,'w')`, rename/remove/move).
- Unit tests monkeypatch `os.remove`, `os.rename`, `shutil.move`, write-modes.
- Integration test: run on read-only mount and validate success.

## UI-level
- No destructive actions.
- “READ-ONLY” indicator always visible.
- Any “export” is metadata-only (JSON/ZIP), never file moves.

## Agent constraints
- Tools accept `file_id`, not raw paths.
- Tools are read-only and budgeted.
- Agent answers must cite evidence.
