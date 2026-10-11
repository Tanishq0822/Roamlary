# ROAMLARY — BACKEND REPORT

**Author:** Backend engineer (Laptop 1) · **Branch:** `backend` · **Last updated:** 2026-10-12
**Status:** Milestone 1 complete (scaffolding). No database yet.

> **How to read this report:** Section 1 explains the plan and branch workflow.
> Section 2 covers Task 001 (inspection). Section 3 explains **every file** in
> plain language — what it is, why it exists, how it works. Section 4 shows how a
> browser request travels through the code, step by step. Sections 5–7 cover
> running/testing, dependencies, and verification proof. Sections 8–11 cover
> decisions, roadmap, frontend connection, and honest prototype limits. The
> glossary at the bottom defines every technical term.

---

## 1. Big picture: what are we building and how is the work split?

Roamlary is an **AI-powered travel companion and personal safety app** (CODE X
3.0 hackathon prototype). The backend is the "brain" that the Flutter phone app
talks to over the internet (HTTP/JSON). It will eventually handle user
profiles, emergency contacts, safety check-ins, SOS incidents, community safety
reports, and location-sharing sessions.

Three laptops own three Git branches:

| Laptop | Owns | Branch | What it does |
|---|---|---|---|
| **Laptop 1 (this machine)** | `backend` | Python/FastAPI API + database |
| Laptop 2 | `frontend` | Flutter mobile app |
| Laptop 3 | `ai-ml` | AI models + testing |
| Project owner | `main` | Stable integration; only the owner merges/pushes to `main` |

Rule of the project: **nobody pushes without the owner's approval; `main` only
changes through owner-approved merges.**

### Progress so far

| Task | What it was | Status | Commit |
|---|---|---|---|
| Task 001 | Inspect repository & environment only (no changes) | ✅ Done | none (read-only) |
| Task 002 | Backend scaffolding: app skeleton, health check, tests | ✅ Done | `c06d092` on `backend` (local, not pushed) |
| Task 003 | Database foundation (PostgreSQL + SQLAlchemy + Alembic + User model) | ⏳ Next | — |
| Task 004 | Trusted contacts + login/auth | ⏳ Planned | — |
| Task 005 | Check-ins + SOS incident lifecycle | ⏳ Planned | — |
| Task 006 | Community reports + location sharing + notifications + API contract freeze | ⏳ Planned | — |

---

## 2. Task 001 — Repository inspection (read-only)

**Goal:** understand what already exists before writing any code. No file was
created, edited, or deleted; no branch was switched; no package was installed.

### What I checked and found (all verified by running commands)

| # | Check | Verified result |
|---|---|---|
| 1 | Repository root | Contains only `.git`, `backend/` (empty), `docs/` (empty), `frontend/roamlary_app/` |
| 2 | Git branch & state | On `main`, working tree clean, single commit `4761b41` "Initial Roamlary project setup" |
| 3 | Git remotes | One remote: `origin` → `https://github.com/Tanishq0822/Roamlary.git` (unchanged) |
| 4 | Flutter project | Exists at `frontend/roamlary_app` — a brand-new default template (counter demo), **no app logic, no internet/HTTP package, so it does not depend on any backend contract yet** |
| 5 | Backend files | None existed. Git tracked 24 files, all Flutter template files |
| 6 | Python | Python **3.13.2** (default) and 3.11.3 installed; pip available; no `uv`/`poetry`/`pipx` |
| 7 | PostgreSQL | **Not installed** — no `psql`, no Windows service, port 5432 closed. Docker CLI exists (v29.7.2) but its engine (daemon) was not running |
| 8 | Secrets | **No `.env` or secret files anywhere** — nothing dangerous committed. Only `.gitignore` was the standard Flutter template |
| 9 | Backend directory | `backend/` existed but was completely empty (same for `docs/`) |
| 10 | API contracts | **None exist.** The frontend has nothing hard-coded, so the backend defines the API shape first and Laptop 2 builds against it |

### Risks that were found (and how Task 002 fixed them)

| Risk | Impact | Fix |
|---|---|---|
| No root `.gitignore` | Future `.env` files with real secrets, or `.venv` folders (thousands of files), could be committed by accident | Added root `.gitignore` + `backend/.gitignore` in Task 002 |
| `backend/` and `docs/` were untracked empty folders | Git cannot track empty folders — they would vanish on any clone/backup | `backend/` now contains real committed files |
| No API contract | Frontend and backend teams could build mismatched expectations | Backend publishes OpenAPI docs automatically; contract freeze planned in Task 006 |

---

## 3. Task 002 — Backend scaffolding, file by file

**Goal:** an empty folder → a runnable, tested, documented API skeleton with
one working endpoint (`/api/v1/health`). **No database yet** — that is Task 003.

### 3.1 The folder that was created

```
Roamlary/
├── .gitignore                         ← NEW (root level)
└── backend/
    ├── .gitignore                     ← NEW
    ├── .env.example                   ← NEW
    ├── pyproject.toml                 ← NEW  (the "recipe" of the project)
    ├── README.md                      ← NEW  (quick-start guide)
    ├── REPORT.md                      ← NEW  (this file)
    ├── .venv/                         ← exists locally but IGNORED by git (not committed)
    ├── app/                           ← NEW  (all application code)
    │   ├── __init__.py                ← NEW  (empty; marks folder as a Python package)
    │   ├── main.py                    ← NEW  (entry point — the app itself)
    │   ├── core/
    │   │   ├── __init__.py            ← NEW  (empty)
    │   │   └── config.py              ← NEW  (settings from environment)
    │   └── api/
    │       ├── __init__.py            ← NEW  (empty)
    │       └── v1/
    │           ├── __init__.py        ← NEW  (empty)
    │           ├── router.py          ← NEW  (attaches all v1 endpoints)
    │           └── endpoints/
    │               ├── __init__.py    ← NEW  (empty)
    │               └── health.py      ← NEW  (the /health endpoint)
    └── tests/                         ← NEW  (automated tests)
        ├── conftest.py                ← NEW  (shared test setup)
        └── test_health.py             ← NEW  (3 tests, all passing)
```

> **Why are there several empty `__init__.py` files?** Python needs them to
> treat a folder as an importable "package". Without them, `from app.main import
> app` fails. They stay empty on purpose.

### 3.2 File-by-file explanation

#### `backend/pyproject.toml` — the project's recipe
**What it is:** one configuration file that tells Python tools three things:
(1) which packages this project needs, (2) how to build/install itself, (3) how
tools like pytest and ruff should behave.

**Why this file:** before Task 002 there was no way for another laptop to
recreate this environment. Now anyone runs two commands and gets the exact same
setup. This is also why versions are **pinned exactly** (e.g. `fastapi==0.143.0`)
— pinned versions guarantee "it worked on Laptop 1" = "it works on Laptop 2".

**How it works (key sections):**

```toml
[project]
requires-python = ">=3.13"          # which Python this needs
dependencies = [                    # libraries the app needs to RUN
    "fastapi==0.143.0",             # the web framework
    "uvicorn[standard]==0.54.0",    # the server that runs FastAPI
    "sqlalchemy==2.1.4",            # ORM (database toolkit) — used from Task 003
    "psycopg[binary]==3.3.6",       # PostgreSQL driver — used from Task 003
    "alembic==1.20.0",              # database migrations — used from Task 003
    "pydantic-settings==2.15.0",    # reads config from environment/.env
]
[project.optional-dependencies]
dev = [                             # libraries needed only for tests/linting
    "pytest==8.4.2",                # test runner
    "httpx2==2.13.1",               # HTTP client used by FastAPI's test client
    "ruff==0.17.0",                 # linter + formatter (code quality)
]
[tool.pytest.ini_options]
testpaths = ["tests"]               # pytest: look for tests in tests/
pythonpath = ["."]                  # pytest: make `app` importable
[tool.ruff]
line-length = 100                   # style rules for the linter
```

**One deviation from the approved plan:** the plan said `httpx`, but the
newly-installed starlette version (1.7.0, pulled in by fastapi 0.143.0)
*deprecates* `httpx` for its test client and requires **`httpx2`**. I verified
this by seeing the deprecation warning in the first test run, swapping the
package, and confirming the warning disappeared with tests still green.

#### `backend/.env.example` — configuration template
**What it is:** a text file listing every configuration setting with safe
placeholder values.

**Why:** the app must read settings from the environment (a core security rule)
so real secrets never live in code. Each machine copies this file to `.env`
(real file, **gitignored** — never committed) and fills in local values.

**How it works:** contains `APP_ENV`, `APP_NAME`, `APP_VERSION`, `APP_HOST`,
`APP_PORT`, `CORS_ORIGINS` (comma-separated websites allowed to call the API),
and `DATABASE_URL` (PostgreSQL connection string — active from Task 003).

#### `backend/app/core/config.py` — typed settings
**What it is:** a `Settings` class that loads the variables above and validates
them.

**Why:** instead of scattered `os.environ[...]` calls, one class defines every
setting with a type and a default value. Typos in variable names are caught
immediately (`extra="ignore"` tolerates unrelated env vars).

**How it works:**

```python
class Settings(BaseSettings):                       # reads env vars / .env
    app_port: int = 8000                            # typed with default
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", ...]

    @field_validator("cors_origins", mode="before")  # "a,b,c" → ["a","b","c"]
    def split_cors_origins(cls, value): ...

settings = Settings()   # one global instance used everywhere
```

So when `.env` says `CORS_ORIGINS=http://localhost:3000,http://10.0.2.2:3000`,
the validator splits it into a Python list of two strings.

#### `backend/app/main.py` — the application itself (entry point)
**What it is:** builds the FastAPI application. This is what the server runs.

**Why a factory function (`create_app()`) instead of one big global object:
tests can build a fresh app instance, and settings can differ per environment.
The line `app = create_app()` at the bottom is what uvicorn actually loads.

**How it works — three steps inside `create_app()`:**

1. `FastAPI(title=..., version=..., openapi_url=...)` — creates the app and
   automatically generates the API documentation (Swagger UI at `/docs`).
2. `app.add_middleware(CORSMiddleware, ...)` — adds CORS: a security layer that
   answers the browser question *"is this website allowed to call my API?"*.
   Without it, Flutter/web apps get blocked. Our list allows
   `http://localhost:3000` and `http://10.0.2.2:3000` (the Android emulator's
   alias for the host machine).
3. `app.include_router(api_router, prefix="/api/v1")` — attaches every
   version-1 endpoint under the `/api/v1` prefix, so URLs look like
   `/api/v1/health` instead of `/health`. Versioning means a future v2 can live
   alongside v1 without breaking the app.

The app description explicitly states: *"This is a local prototype; no
emergency services or real responders are connected."* — honesty by design.

#### `backend/app/api/v1/router.py` — the endpoint aggregator
**What it is:** one place that collects all v1 endpoint files.

**Why:** as we add contacts, check-ins, SOS… each gets its own file; this router
attaches them all. `main.py` never needs to change again.

**How it works:** creates `api_router = APIRouter()` and calls
`api_router.include_router(health.router)`. In Task 003+ we add more
`include_router(...)` lines here — one per feature.

#### `backend/app/api/v1/endpoints/health.py` — the first real endpoint
**What it is:** the `GET /api/v1/health` route.

**Why:** every app needs a trivial "are you alive?" check. It proves the whole
pipeline works (server → CORS → routing → JSON response) and will later be used
by Docker/Laptop 2 to verify the backend is running.

**How it works:**

```python
router = APIRouter(tags=["health"])       # groups it in the /docs page

@router.get("/health", summary="Service health check")   # defines the URL+method
def get_health() -> dict[str, str]:
    return {"status": "ok", "service": "roamlary-api",
            "environment": settings.app_env, "version": settings.app_version}
```

FastAPI turns that dictionary into a JSON HTTP response automatically.

#### `backend/tests/conftest.py` — shared test setup
**What it is:** defines a pytest *fixture* named `client`.

**Why:** every test that needs to call the API should use the same client
setup; putting it in `conftest.py` means tests don't repeat themselves.

**How it works:** `TestClient(app)` is FastAPI's built-in fake web client — it
calls endpoints **in-process** (no real network, no real server process), which
makes tests run in ~0.04 s.

#### `backend/tests/test_health.py` — the proof it works
**What it is:** three automated tests:

| Test | What it asserts | Why it matters |
|---|---|---|
| `test_health_returns_ok` | `/api/v1/health` returns HTTP 200 with `status: "ok"` and a version | Protects the core liveness contract |
| `test_openapi_schema_exposes_health` | The auto-generated OpenAPI JSON contains our route | Guarantees the frontend contract is published |
| `test_docs_page_is_available` | `/docs` (Swagger UI) returns HTTP 200 | Guarantees humans can browse the API |

Run them any time with `python -m pytest`. If a future change breaks the API,
these tests fail loudly *before* the Flutter app notices.

#### `.gitignore` (root) and `backend/.gitignore` — accident prevention
**What they are:** lists of patterns Git must never track.

**Why:** two disasters are prevented: (1) committing `.venv/` (≈10,000 library
files) which would destroy repo clarity, and (2) committing a real `.env` with
secrets — the pattern `!.env.example` keeps the *template* tracked while the
real `.env` stays out. Verified working: `git status` shows a clean tree even
though `.venv/` exists on disk.

#### `backend/README.md` — teammate quick-start
The commands to set up, run, test, and lint the backend — enough for Laptop 2
or the owner to reproduce everything without reading this report.

---

## 4. How a request flows through the code (plain walkthrough)

When the Flutter app (or your browser) sends `GET http://127.0.0.1:8000/api/v1/health`:

```
1. uvicorn (the server process) receives the HTTP request
        ↓
2. CORSMiddleware checks: is the caller's origin in cors_origins?
        → If a blocked website calls: it receives an error (by design)
        → Our allowed origins: http://localhost:3000, http://10.0.2.2:3000
        ↓
3. FastAPI looks at the URL: method=GET + path=/api/v1/health
        → prefix "/api/v1" matches, then router.py points to endpoints/health.py
        ↓
4. get_health() runs and returns a dict
        ↓
5. FastAPI converts the dict → JSON body + HTTP 200 header
        ↓
6. Response arrives: {"status":"ok","service":"roamlary-api",
                      "environment":"development","version":"0.1.0"}

Meanwhile, FastAPI also auto-builds the documentation:
   Swagger UI (humans):  http://127.0.0.1:8000/docs
   OpenAPI JSON (machines, e.g. Laptop 2 codegen):
                          http://127.0.0.1:8000/api/v1/openapi.json
```

**Verified live:** both URLs returned HTTP 200 with correct content during the
Task 002 smoke test (server started, queried, then stopped).

---

## 5. How to run everything on your machine (verified commands)

```powershell
# 1. Go to the backend folder
cd C:\Projects\Roamlary\backend

# 2. Create the virtual environment (only once)
py -3.13 -m venv .venv

# 3. Install the pinned libraries (only once, or after dependency changes)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"

# 4. Start the server
.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
#    → then open http://127.0.0.1:8000/docs in your browser (Ctrl+C stops the server)

# 5. Run the tests (server can be stopped)
.venv\Scripts\python -m pytest

# 6. Check code quality
.venv\Scripts\python -m ruff check .
```

> **What is `.venv` (virtual environment)?** A private, project-local Python
> install. It keeps Roamlary's libraries separate from your system Python and
> from other projects, so nothing conflicts. It is gitignored on purpose.

---

## 6. Dependencies — why each one is here

| Library | Version (pinned) | Plain-language reason | Used from |
|---|---|---|---|
| `fastapi` | 0.143.0 | The web framework: turns URLs into Python functions and auto-creates the API docs | Task 002 (now) |
| `uvicorn[standard]` | 0.54.0 | The server process that actually listens on port 8000 and passes requests to FastAPI | Task 002 (now) |
| `pydantic-settings` | 2.15.0 | Reads + validates configuration from environment variables / `.env` | Task 002 (now) |
| `sqlalchemy` | 2.1.4 | The ORM — lets us work with the database using Python classes instead of raw SQL | Task 003 |
| `psycopg[binary]` | 3.3.6 | The PostgreSQL driver — the wire between SQLAlchemy and the Postgres server (binary wheel = no compiler needed on Windows) | Task 003 |
| `alembic` | 1.20.0 | Database migrations — version-controlled "update scripts" for the database schema | Task 003 |
| `pytest` | 8.4.2 | The test runner that executes `tests/` | Task 002 (now) |
| `httpx2` | 2.13.1 | HTTP client that powers FastAPI's in-process test client (new replacement for `httpx`) | Task 002 (now) |
| `ruff` | 0.17.0 | Linter + formatter: catches mistakes early and keeps style consistent | Task 002 (now) |

**Deliberately NOT added (and why):** Redis and Firebase SDKs (no real need at
prototype scale — notification/auth go behind plain interfaces first), AI SDKs
(Laptop 3's AI will be a simple HTTP contract, so no SDK needed), Celery
background workers (overkill for a single-process demo). Every extra dependency
is a risk; we add one only with a stated purpose.

---

## 7. Verification proof (Task 002 acceptance evidence)

| Check | Command | Result |
|---|---|---|
| Environment consistency | `pip check` | "No broken requirements found" |
| Unit tests | `python -m pytest` | **3 passed** in 0.04 s, zero warnings |
| Lint | `python -m ruff check .` | **All checks passed** |
| Live server | start uvicorn → `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health` | `{"status":"ok","service":"roamlary-api","environment":"development","version":"0.1.0"}` |
| Swagger UI | browser request to `/docs` | HTTP 200 |
| Git hygiene | `git status` with `.venv/` on disk | Clean tree — ignores work correctly |
| Commit | `git commit` on `backend` | `c06d092`, 16 files, 328 insertions, **not pushed** |

**Frontend & databases untouched.** `main` branch unchanged at `4761b41`.

---

## 8. Decisions made (with owner approval)

| Decision | Choice | Reason |
|---|---|---|
| Python version | **3.13.2** | Newest installed; all pinned wheels verified compatible |
| Package tooling | **venv + pip + pyproject.toml** | Nothing extra to install on a Windows laptop |
| PostgreSQL delivery | **Docker container** (`postgres:16`) | Fast, isolated, destroyable — decided, execution is Task 003 |
| Auth approach | **Minimal local JWT now, Firebase-ready interface later** | Works offline for the hackathon; Firebase can be slotted in without rewriting endpoints |
| API shape | **`/api/v1` prefix, port 8000, JSON** | Versioning now avoids breaking the app later |
| Database style | **Sync SQLAlchemy** (not asyncio) | Simpler to write/debug for a hackathon; the service layer allows switching later |
| Push policy | **Local commits only; owner reviews before any push** | Owner controls `main` and integration |

---

## 9. Roadmap — what comes next

| Task | Milestone | Deliverables |
|---|---|---|
| **Task 003** | M2 — DB foundation | Start Docker Desktop → `postgres:16` container; SQLAlchemy engine/session (`app/db/`); Alembic initialized with first migration; `User` model + `GET/PATCH /api/v1/users/me`; `.env` with real local credentials (gitignored) |
| **Task 004** | M3 — Contacts + auth | Login endpoint (local JWT) + Firebase-ready security abstraction; `TrustedContact` CRUD with per-user ownership checks |
| **Task 005** | M4 — Check-ins + SOS | Check-in schedule/response flow; SOS incident lifecycle (active → acknowledged → resolved) with append-only event timeline and location payloads |
| **Task 006** | M5 — Reports, sharing, contract freeze | Community safety reports (geo-filtered); permission-based location-sharing sessions; notification **interface** with console provider; exported OpenAPI spec → `docs/openapi.json` for Laptop 2; AI/ML contract stub for Laptop 3 |

Each task ends the same way: tests green → ruff clean → local commit on
`backend` → report updated here → owner review before push.

---

## 10. How the Flutter frontend will connect (preview — awaiting frontend report)

Once your `frontend/REPORT.md` arrives, I will produce the **merge/integration
document** (planned at `docs/INTEGRATION.md`) that maps, in plain language, each
Flutter screen → the backend endpoint it calls → the JSON it sends/receives.
Planned connection facts already true:

- The Flutter app must call the backend's `/api/v1/...` URLs as JSON over HTTP.
- Base URL depends on the device:
  - **Android emulator:** `http://10.0.2.2:8000` (the emulator's alias for your laptop)
  - **Real phone on same Wi-Fi:** `http://<your-laptop-LAN-IP>:8000` (needs a firewall allow-rule for port 8000)
  - **Windows desktop build:** `http://127.0.0.1:8000`
- CORS on the backend already allows the dev origins; the exact list will be
  aligned with the frontend report.
- The frontend currently has **no HTTP package** (only `cupertino_icons`), so
  Laptop 2 will need to add one (e.g. `dio` or `http`) when integration starts.
- The OpenAPI page (`/docs`) is the single source of truth for available
  endpoints, request bodies, and responses.

---

## 11. Honest prototype limits (read this before any demo)

- This is a **local hackathon prototype**. No emergency services, real
  responders, ambulance dispatch, or police integration exists or is claimed.
- No real SMS/WhatsApp/push notifications are sent yet. Notification delivery is
  an **interface with a console/log stub** until a provider is verified working.
- No AI is connected yet — Laptop 3 will provide it later through a documented
  contract.
- Authentication is development-grade (local JWT). Do not use real credentials.
- Data lives in a local Docker PostgreSQL container on this laptop only.

---

## Glossary (every technical term used above)

| Term | Plain meaning |
|---|---|
| **API** | Application Programming Interface — a documented way for one program (Flutter) to ask another (backend) for data/actions |
| **Endpoint / route** | A specific URL + HTTP method (e.g. `GET /api/v1/health`) that does one job |
| **HTTP method** | The verb of a request: `GET` = read, `POST` = create, `PUT/PATCH` = update, `DELETE` = remove |
| **JSON** | The universal text format for data exchange, e.g. `{"status":"ok"}` |
| **FastAPI** | A Python web framework that builds APIs from typed Python functions and auto-generates documentation |
| **uvicorn** | The server program that runs the FastAPI app and listens on a port |
| **Middleware** | Code that runs *before* every request — ours checks CORS |
| **CORS** | A browser security rule: which websites are allowed to call this API |
| **OpenAPI / Swagger** | Standard description of an API; Swagger UI (`/docs`) is the human-browsable page |
| **Pydantic** | Library for typed data validation (request bodies, settings) |
| **Environment variable / `.env`** | External configuration values; `.env` is a local file that must never be committed |
| **venv (virtual environment)** | A private project-local Python + library installation |
| **ORM (SQLAlchemy)** | Lets you use Python classes instead of writing SQL by hand |
| **Migration (Alembic)** | A versioned script that upgrades/downgrades the database schema safely |
| **PostgreSQL** | A powerful open-source relational database (runs via Docker in Task 003) |
| **Docker / container** | A lightweight, isolated "mini-computer" that runs e.g. PostgreSQL without polluting your system |
| **pytest / test fixture** | The test runner / a reusable setup helper for tests |
| **ruff** | A fast linter+formatter that enforces code quality |
| **JWT** | JSON Web Token — a signed digital "badge" proving who a user is |
| **Repository / branch / commit / remote** | Git concepts: project history / parallel line of work / saved snapshot / the GitHub copy |

---

*Next report update will follow Task 003 (database foundation). Owner review
required before anything is pushed.*
