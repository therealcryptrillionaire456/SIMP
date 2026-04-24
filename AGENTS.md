# Repository Guidelines

## Project Structure & Module Organization

Primary Python source lives in `simp/`, with the broker in `simp/server/`, routing/orchestration in `simp/routing/` and `simp/orchestration/`, and domain modules under `simp/organs/` and `simp/projectx/`. The operator dashboard is in `dashboard/`. Runtime state, inboxes, and logs are stored under `data/` and `logs/` and should be treated as generated artifacts. Use `scripts/bootstrap/`, `scripts/diagnostics/`, `scripts/recovery/`, and `scripts/manual_checks/` for operational helpers; avoid adding more root-level scripts.

## Build, Test, and Development Commands

- `python3 -m pip install -r requirements.txt`: install core dependencies.
- `python3 -m pip install -e .[dev]`: install the package plus dev tools from `pyproject.toml`.
- `python3 -m simp.server.http_server`: run the SIMP broker locally.
- `python3 dashboard/server.py`: start the dashboard.
- `bash startall.sh`: bring up the main local stack when working on integrated flows.
- `python3.10 -m pytest tests -q`: run the tracked test suite only.
- `python3.10 scripts/manual_checks/test_qip_issue.py`: run a live/manual probe against a local broker.

## Coding Style & Naming Conventions

Use 4-space indentation and keep Python lines at 120 chars. `black` and `flake8` are the active style tools; `mypy` is configured but permissive. Follow existing naming patterns: `snake_case` for modules/functions, `PascalCase` for classes, and `test_*.py` for tests. Put reusable diagnostics in `scripts/diagnostics/`; keep one-off live probes in `scripts/manual_checks/`, not `tests/`.

## Testing Guidelines

Pytest is configured in `pyproject.toml` with `tests/` as the canonical suite. Add automated coverage there, and keep file names as `test_*.py`. Root-level or manual scripts that hit real services, wallets, or brokers should stay out of pytest and live under `scripts/manual_checks/`. Before submitting, run the narrowest relevant test file plus any affected integration path.

## Commit & Pull Request Guidelines

Recent history favors short, imperative subjects such as `feat: add ...` or `Add ProjectX ...`. Keep commits focused and scoped to one subsystem. PRs should state the operational impact, list commands/tests run, mention config or migration changes, and include screenshots for dashboard/UI work.

## Security & Configuration Tips

Do not commit secrets, `.env` files, broker state, or ad hoc backups. Prefer `.env.example` and config files under `config/`. If a change touches runtime wiring, verify both the direct entrypoint and any corresponding `scripts/bootstrap/` wrapper.
