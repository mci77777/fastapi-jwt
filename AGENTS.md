# Repository Guidelines

## Project Structure & Module Organization
- Backend FastAPI lives in `app/`; `api/v1/` for routes, `models/` + `schemas/` for DB and validation, `settings/` for config, and audit logs land in `log/`.
- Vue client in `web/`; `src/` for features, `build/` for Vite helpers, `.env.*` for environment toggles, static assets under `public/` and `src/assets/`.
- Supporting assets include `deploy/` for Docker samples plus root `Makefile`, `Dockerfile`, `pyproject.toml`, and `run.py` for local entrypoints.

## Build, Test, and Development Commands
- Backend: `uv venv && uv add pyproject.toml` prepares dependencies; `python run.py` or `make start` boots the API on http://localhost:9999; `make install` refreshes pinned libs.
- Quality: `make lint` (ruff) and `make format` (black + isort); `make check` runs both in dry-run mode.
- Tests: `make test` exports `.env` then calls `pytest`; install `pytest` in your venv if missing.
- Frontend (inside `web/`): `pnpm install`, `pnpm dev`, `pnpm build`, `pnpm lint` / `pnpm lint:fix`, and `pnpm preview` for post-build smoke checks.

## Coding Style & Naming Conventions
- Python favors `black` 120-char limits and `isort` ordering; modules and functions snake_case, Pydantic/ORM classes PascalCase, constants UPPER_SNAKE.
- Vue/TS code keeps two-space indent, PascalCase component files in `src/components`, camelCase composables and stores, shared tokens in `src/styles`; run `pnpm prettier` before sweeping UI edits.

## Testing Guidelines
- Place backend tests beside features under `tests/` (e.g., `tests/api/test_users.py`); cover RBAC, JWT auth, and CRUD flows, and reset DB fixtures between cases.
- Frontend suites are optional today—document manual QA in PRs; if you add Vitest, colocate specs in `web/src/__tests__` and wire `pnpm vitest` in scripts.

## Commit & Pull Request Guidelines
- Use succinct imperative commits as in history (`fix login's loading message`, `adjust audit log filter`); split unrelated work across commits.
- PRs should note backend/frontend touchpoints, link issues, include screenshots or curl samples for UI/API tweaks, and confirm lint/tests succeeded.
- Call out new env vars or migrations; coordinate schema changes with `make migrate`/`make upgrade` steps.

## Security & Configuration Tips
- Keep secrets in local `.env` files and never commit them; update `app/settings` defaults cautiously.
- Rotate JWT keys and database creds through deployment configs under `deploy/` whenever they change.
