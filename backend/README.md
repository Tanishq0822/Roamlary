# Roamlary Backend

FastAPI backend for **Roamlary**, an AI-powered travel companion and personal
safety prototype (CODE X 3.0 hackathon).

> **Honesty note:** this is a local hackathon prototype. It does **not** connect
> to emergency services, real responders, or any production notification
> provider. Notification and AI integrations are interface stubs by design.

## Status

Milestone 1 (scaffolding) complete: app skeleton, versioned router, typed
configuration, health endpoint, tests. **No database is wired yet** — that
arrives in Milestone 2 (PostgreSQL via Docker + SQLAlchemy + Alembic).

## Prerequisites

- Python 3.13 (`py -0p` lists installed versions on Windows)
- Docker Desktop (only needed from Milestone 2 for PostgreSQL)

## Setup (Windows / PowerShell)

```powershell
cd backend
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Run

```powershell
.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Interactive docs (Swagger UI): <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON: <http://127.0.0.1:8000/api/v1/openapi.json>
- Health check: <http://127.0.0.1:8000/api/v1/health>

## Test & lint

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format .
```

## Configuration

All settings are environment variables (or a local `.env` file). Copy
`.env.example` to `.env` and adjust values; `.env` is gitignored. Keys:

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_ENV` | Environment label (development/test/production) | `development` |
| `APP_HOST` / `APP_PORT` | Bind address for uvicorn | `127.0.0.1` / `8000` |
| `CORS_ORIGINS` | Comma-separated allowed origins for Flutter dev | `http://localhost:3000,http://10.0.2.2:3000` |
| `DATABASE_URL` | SQLAlchemy URL (used from Milestone 2) | local Docker Postgres |

## Project layout

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory, CORS, router mounting
│   ├── core/config.py       # pydantic-settings configuration
│   └── api/v1/              # versioned endpoints (/api/v1/...)
├── tests/                   # pytest suite (fastapi TestClient)
├── alembic/                 # migrations (added in Milestone 2)
├── pyproject.toml           # dependencies + tool config
└── .env.example             # configuration template (no secrets)
```
