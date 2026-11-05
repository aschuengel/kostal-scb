# kostal-scb

## What this repo is
- This is a tiny `uv`-managed Python 3.15 FastAPI project.
- Reusable REST auth and readout code lives in `kostal_api.py`; `main.py` exposes the HTTP app and currently only serves the `GET /power_flow` endpoint.
- `swagger.json` is a local snapshot of the inverter's `/api/v1` API. Use it as the source of truth for endpoint shapes before guessing request payloads.

## Commands
- Install deps: `uv sync`
- Run the API locally: `uv run uvicorn main:app --reload`
- Build the container: `docker build -t kostal-scb .`
- Run the container: `docker run --rm -p 8000:8000 --env-file .env kostal-scb`
- Safe syntax check: `uv run python -m py_compile main.py kostal_api.py kostal_models.py`
- For every changed Python file, run `uvx basedpyright <files>` and `uvx ruff check <files>` before finishing.

## Important gotchas
- Python 3.15 is required (`pyproject.toml`, `.python-version`, and `uv.lock` all agree). Do not downgrade commands to older Python versions.
- Do not use the FastAPI endpoint as a routine verification step unless you intend to contact the inverter and authenticate.
- Connection/auth settings must stay outside Python. Use env vars such as `KOSTAL_BASE_URL`, `KOSTAL_USERNAME`, `KOSTAL_PASSWORD`, and optionally `KOSTAL_SERVICE_CODE`.
- `.gitignore` ignores `.venv` but not `.env`; treat `.env` as sensitive local state.
- There is no repo-configured test suite yet, but Python changes should still be checked with `basedpyright` and `ruff` on the touched files.
