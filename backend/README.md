# Roamlary Backend

FastAPI backend for **Roamlary**, an AI-powered travel companion and personal
safety prototype (CODE X 3.0 hackathon).

> **Honesty note:** this is a local hackathon prototype. It does **not** connect
> to emergency services, real responders, SMS/push providers, or live AI.
> Those integrations belong to later phases and will only be documented as
> working after they are actually verified.

## Current scope (Phase 2 — PostgreSQL, models & migrations)

Implemented now (on top of the Phase 1 foundation):

- Runnable FastAPI application with versioned routing (`/api/v1`)
- `GET /api/v1/health` liveness endpoint (documented contract below)
- Environment-based configuration (`.env` / environment variables)
- CORS configured for Flutter development origins
- Interactive API documentation (Swagger UI / ReDoc)
- **PostgreSQL persistence** via SQLAlchemy 2.x (engine + per-request sessions)
- **Five domain models**: `User`, `TrustedContact`, `CheckIn`, `SosEvent`,
  `CommunityReport` — with UUID keys, timestamps, CHECK constraints and
  `ON DELETE RESTRICT` foreign keys
- **Alembic migrations** (initial schema generated and applied to `roamlary_dev`)
- Automated test suite: **35 tests** (31 offline + 4 real-PostgreSQL integration)

**Intentionally NOT implemented yet** (assigned to later phases, do not expect
them to exist): API CRUD endpoints for these models, authentication and user
profiles, trusted-contact/check-in/SOS/report workflows, AI companion,
notifications, production deployment. Phase 2 built the database *foundation*
only — the tables exist but nothing exposes them over HTTP yet.

## Prerequisites

- Python **3.13** (verified on 3.13.2; `py -0p` lists installed versions)
- Docker Desktop (for the local PostgreSQL container used in development)

## Setup (Windows / PowerShell)

```powershell
cd backend
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Environment configuration

Copy the template and adjust values (never commit the real `.env`):

```powershell
Copy-Item .env.example .env
```

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_ENV` | Environment label (development/test/production) | `development` |
| `APP_NAME` | Name shown in the API docs | `Roamlary API` |
| `APP_VERSION` | Version reported by `/api/v1/health` | `1.0.0` |
| `APP_HOST` / `APP_PORT` | Bind address (keep in sync with the uvicorn flags) | `127.0.0.1` / `8000` |
| `CORS_ORIGINS` | Comma-separated origins allowed by the browser CORS policy | `http://localhost:3000,http://10.0.2.2:3000` |
| `DATABASE_URL` | SQLAlchemy URL: `postgresql+psycopg://USER:PASSWORD@localhost:5432/DBNAME` | `.../roamlary_dev` |

> **Credentials:** the real `DATABASE_URL` (with the container password) lives
> only in `.env`, which is gitignored. `.env.example` holds a placeholder. Never
> commit the real `.env`, and never paste the real URL into chat, docs, or logs.

## Database architecture

Four separate concerns, so each stays small and testable:

| Layer | File(s) | Job |
| --- | --- | --- |
| **Configuration** | `app/core/config.py` | Reads `DATABASE_URL` from the environment/`.env`. No credentials in code. |
| **Engine** | `app/db/session.py` | `engine` = the pooled communication channel to PostgreSQL. Creating it does **not** open a connection — the first real connection happens on first use. |
| **Session** | `app/db/session.py` → `get_db()` | A session is one unit of database work. `get_db()` hands each request exactly one session and **always** closes it (even if the route raises). Future API routes will use it as a FastAPI dependency. |
| **Models** | `app/models/*.py` | Each class maps to one table (`User`→`users`, etc.). This is the ORM. |

**Migrations are the authoritative schema mechanism.** The app never calls
`create_all()` in production — Alembic owns the schema, so every change is a
reviewed, replayable file.

### The five tables

| Table | Purpose | Key columns |
| --- | --- | --- |
| `users` | App account / profile | `id` (UUID PK), `firebase_uid` (optional, unique), `display_name`, `email` (optional, unique) |
| `trusted_contacts` | People to notify in an SOS | `user_id` (FK→users), `name`, `phone`, `email` |
| `check_ins` | "Ping me by time T" promises | `user_id` (FK), `status`, `due_at`, `completed_at` |
| `sos_events` | **Simulated** emergency incidents | `user_id` (FK), `status`, `latitude`/`longitude`, `resolved_at` |
| `community_reports` | Crowd-sourced safety notes | `user_id` (FK), `category`, `description`, `latitude`/`longitude`, `status` |

All children use **`ON DELETE RESTRICT`**: deleting a user who still has safety
records is blocked at the database level, so safety history can never vanish by
accident. Status columns are protected by CHECK constraints, and lat/long are
range-guarded (−90..90 / −180..180).

### What CORS is and when it matters

CORS (Cross-Origin Resource Sharing) is a **browser** security rule: when
website A (the Flutter web/desktop app) calls API B (this backend) hosted on a
different address, the browser blocks the call unless API B explicitly allows
A's origin. You set allowed origins in `.env` via `CORS_ORIGINS`.

- Native Android/iOS builds generally are not subject to CORS (only browsers
  are), but Flutter **web** and some tooling are — so configuring it now avoids
  surprises in Phase 9.
- The Android emulator reaches your laptop as `10.0.2.2`, not `localhost`.
- A real phone on the same Wi-Fi needs your laptop's LAN IP (e.g.
  `http://192.168.1.50:8000`) added to `CORS_ORIGINS`.
- This development CORS setup is **not** a production security review.

## Run

```powershell
.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger UI (humans): <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON (machines / codegen): <http://127.0.0.1:8000/api/v1/openapi.json>

### Health endpoint (implemented contract)

`GET /api/v1/health` → HTTP 200:

```json
{
  "status": "ok",
  "service": "roamlary-backend",
  "version": "1.0.0"
}
```

This is a **liveness** check only: it confirms the process is running. It does
**not** claim database, AI, or notification connectivity — those phases do not
exist yet. Unknown routes return HTTP 404.

## Migrations (Alembic)

Alembic creates and evolves the schema. The migration files live in
`alembic/versions/` and are committed as source code.

```powershell
# Apply all pending migrations to the configured database (reads DATABASE_URL)
.venv\Scripts\python -m alembic upgrade head

# See the current revision and the migration history
.venv\Scripts\python -m alembic current
.venv\Scripts\python -m alembic history

# Preview the SQL a migration would run (no database changes)
.venv\Scripts\python -m alembic upgrade head --sql

# Generate a NEW migration after you edit an app/models/ file
.venv\Scripts\python -m alembic revision --autogenerate -m "describe the change"
```

> **Rule:** `--autogenerate` compares your models against the *live* database.
> Always open the generated file in `alembic/versions/` and review it before
> applying — autogenerate is a helper, not an authority.

### Creating a dedicated development database

Use a throwaway local container; never point at a shared/staging/production DB.

```powershell
# Start a local PostgreSQL 16 container (port 5432, data kept in a Docker volume)
docker run -d --name roamlary-postgres-dev -e POSTGRES_USER=roamlary `
  -e POSTGRES_PASSWORD=<your-dev-password> -e POSTGRES_DB=roamlary_dev -p 5432:5432 postgres:16-alpine

# Confirm it accepts connections
docker exec roamlary-postgres-dev pg_isready -U roamlary -d roamlary_dev
```

Then put the matching `DATABASE_URL` in `.env`.

## Tests & lint

Two test layers exist. Do not confuse them:

- **Offline unit tests** (31) — use an in-memory SQLite database and the FastAPI
  `TestClient`. No PostgreSQL, no network. They prove model behaviour and route
  contracts.
- **PostgreSQL integration tests** (4) — run against a **disposable** database
  and prove real PostgreSQL behaviour (native `uuid` columns, CHECK
  constraint enforcement, timezone-aware timestamps). They are **skipped**
  unless you point them at a throwaway database.

```powershell
# Default run (PostgreSQL integration tests will be SKIPPED)
.venv\Scripts\python -m pytest

# Full run including PostgreSQL integration tests, against a DISPOSABLE database
$env:ROAMLARY_TEST_DATABASE_URL = "postgresql+psycopg://roamlary:<pw>@localhost:5432/roamlary_test"
.venv\Scripts\python -m pytest

# Lint + format
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format .
```

> The integration tests `CREATE` and `DROP` tables. Never set
> `ROAMLARY_TEST_DATABASE_URL` to a database holding data you care about.

## Common problems

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `py -3.13` → "No Python 3.13 found" | Python 3.13 not installed | Install Python 3.13, or use an available 3.1x and tell the backend lead |
| `uvicorn` not recognized | Virtual env not active / wrong shell path | Use `.venv\Scripts\uvicorn.exe` exactly as shown, from `backend/` |
| Port 8000 already in use | Another process (maybe an old server) holds the port | Stop it in Task Manager, or run with `--port 8001` |
| Changes to code not visible | Server without `--reload` is running | Restart with `--reload` |
| Browser blocked call: CORS error | Frontend origin missing from `CORS_ORIGINS` | Add the exact `scheme://host:port` origin to `.env`, restart |
| Settings seem wrong / ignored | `.env` not in `backend/` or syntax error in it | Keep `.env` next to `pyproject.toml`; one `KEY=value` per line, quotes around values with spaces |
| Tests fail after dependency change | Environment out of sync with `pyproject.toml` | Re-run `.venv\Scripts\python -m pip install -e ".[dev]"` |
| `sqlalchemy.exc.OperationalError ... Connection refused` | PostgreSQL container not running, or wrong port | `docker start roamlary-postgres-dev`, then confirm `DATABASE_URL` host/port |
| `password authentication failed` | `.env` password ≠ the container's `POSTGRES_PASSWORD` | Re-check `.env`; the URL password must match the container's |
| `database ... does not exist` | DB was never created | Create it (`createdb`/`docker exec ... createdb`) or point `DATABASE_URL` at an existing one |
| `relation ... does not exist` | Tables not created yet | Run `python -m alembic upgrade head` |
| `alembic ... Can't locate revision` | Bad/empty `alembic/versions/` | Confirm migration files exist; check `alembic current` |
| PostgreSQL integration tests skipped | `ROAMLARY_TEST_DATABASE_URL` not set | Set it to a **disposable** database URL (see Tests above) |
| `CREATE DATABASE cannot run inside a transaction` | DDL run on a transactional connection | Use a real `createdb`/`docker exec`, not a plain SQL session |

## Development log

Every task, file-by-file explanations, actual test outputs, and decisions live
in [`report.md`](report.md).
