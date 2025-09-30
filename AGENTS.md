# Repository Guidelines

## Project Structure & Module Organization
- Backend lives in `app/`; `api/v1/` holds FastAPI routes, `models/` and `schemas/` back the database layer, while audit logs land in `log/`.
- Vue client sits in `web/`; use `web/src/` for features, `web/src/assets/` and `public/` for static assets, and `.env.*` files for environment toggles.
- Supporting assets include `deploy/` for Docker samples and root-level tooling such as `Makefile`, `Dockerfile`, `pyproject.toml`, and `run.py`.

## Build, Test, and Development Commands
- `uv venv && uv add pyproject.toml`: prepare the backend virtual environment with pinned dependencies.
- `python run.py` or `make start`: boot the API at http://localhost:9999 for local development.
- `make lint`, `make format`, `make check`: run ruff, black/isort, or both in dry-run mode to keep code quality high.
- `make test`: export `.env` and execute the pytest suite.
- `pnpm install`, `pnpm dev`, `pnpm build`, `pnpm lint`: manage the Vue client lifecycle from dependency install through production build.

## Coding Style & Naming Conventions
- Python defaults to black with a 120-character line limit and isort ordering; prefer snake_case functions, PascalCase Pydantic/ORM models, and UPPER_SNAKE constants.
- Vue/TypeScript uses two-space indentation, PascalCase component filenames in `src/components`, and camelCase composables/stores; run `pnpm prettier` before sweeping UI edits.

## Testing Guidelines
- Backend tests live under `tests/`, colocated with features (e.g., `tests/api/test_users.py`); cover RBAC, JWT auth, and CRUD flows with fixtures reset between cases.
- Frontend automated tests are optional today; document manual QA steps in PR descriptions if no Vitest coverage is added.
- Run `make test` before pushing code; add new cases when altering business logic or API contracts.

## Commit & Pull Request Guidelines
- Follow the existing imperative commit style, e.g., `fix login's loading message` or `adjust audit log filter`.
- PRs should note backend/frontend touchpoints, link relevant issues, include screenshots or curl samples for UI/API updates, and confirm that lint and tests succeed.
- Call out new environment variables or migrations in the PR body and coordinate schema changes with `make migrate`/`make upgrade`.

## Security & Configuration Tips
- Keep secrets in local `.env` files; never commit credentials.
- Update defaults in `app/settings` cautiously and rotate JWT keys plus database credentials via the deployment configs in `deploy/` when they change.