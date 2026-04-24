# Repo Hygiene

This repo mixes core runtime code with a large amount of generated state, local backups, ad hoc debugging output, and one-off operational scripts. The goal of this document is to keep the operational surface clear without breaking active modules.

## Supported Operational Surface

These are the primary entrypoints that should remain stable and easy to find:

- `startall.sh` — canonical multi-service bring-up
- `bin/start_server.py` — SIMP broker startup
- `dashboard/server.py` — monitoring dashboard
- `simp/organs/ktc/start_ktc.py` — KTC startup and broker registration
- `simp/projectx/runtime_server.py` — ProjectX runtime wrapper
- `keep-the-change/backend/main.py` — standalone Keep The Change backend

## Generated and Local-Only State

The following should be treated as runtime noise, not source:

- log files and pid files
- broker state files under `data/`
- dashboard activity/operator event logs
- graph snapshots, Playwright state, generated output, and local reports
- local env variants and timestamped backup copies
- copied backup files with suffixes like `.bak`, `.backup`, `.manual_backup`

Those files are ignored by `.gitignore` so they stop polluting `git status`.

## Backup Archival

Use the archive helper to quarantine obvious backup snapshots without deleting them:

```bash
bash scripts/repo_hygiene_archive.sh
```

It only moves explicit backup/snapshot files into `backups/repo_hygiene/<timestamp>/`. It does not touch live code paths, runtime logs, or active service directories.

## Rules For Ongoing Cleanup

- Keep new product or runtime code inside existing package/app directories, not the repo root.
- Put ad hoc reports in `reports/` or `docs/`, not beside entrypoint scripts.
- Put one-off operational helpers under `scripts/` or `tools/`.
- Keep tests in `tests/` unless they are intentionally standalone smoke scripts.
- Prefer archiving over deleting when a file might still be useful for rollback or audit.
