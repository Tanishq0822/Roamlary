# Roamlary Backend — Development Report

**Project:** Roamlary — AI travel companion & personal safety (CODE X 3.0 hackathon)
**Workstream:** Backend (Laptop 1) · **Branch:** `backend` · **Maintainer:** Backend technical lead
**File:** `backend/report.md` (mandatory living document — updated with every task)

> **How to read this file:** Part 1 is the always-current overview (project,
> environment, phases, API, database plans). Part 2 is the chronological record
> of completed work — every task with the real commands, real outputs, and
> beginner-friendly explanations. Nothing here is aspirational: anything marked
> "proposed" is NOT built; anything marked "implemented" was executed and
> verified on this machine.

---

# PART 1 — CURRENT STATE (always up to date)

## 1. Project overview

Roamlary is a Flutter mobile app (travel companion + personal safety) with a
Python/FastAPI backend. Planned features: user profiles & authentication,
trusted emergency contacts, safety check-ins, simulated SOS workflows,
community safety reports, location sharing, AI companion chat, and
notifications. This repository is a **local hackathon prototype** — no
emergency services, real SMS/push, or live AI are connected, and none will be
claimed unless actually verified and documented here.

Workstreams: Laptop 1 = backend/DB (`backend` branch, this report) · Laptop 2 =
Flutter (`frontend` branch) · Laptop 3 = AI/ML + QA (`ai-ml` branch) ·
Project owner = reviews and merges into `main`. **Phase assignments come from
the project owner; the backend lead implements only assigned phases.**

## 2. Current environment and baseline (verified 2026-10-12)

| Item | Verified status |
|---|---|
| Repository | `C:\Projects\Roamlary` (Git, remote `origin` → github.com/Tanishq0822/Roamlary.git) |
| Branch | `backend` (created with owner approval; local only, never pushed) |
| History | `4761b41` initial setup → `c06d092` scaffolding → `11f2d7e` report → *(Phase 1 delta uncommitted, see §7)* |
| Python | 3.13.2 in project venv (system also has 3.11.3) |
| pip | 26.2.1 inside `.venv` |
| PostgreSQL | **Running locally** — server 16.15 in the Docker container `roamlary-postgres-dev` (databases: `roamlary_dev`, `roamlary_test`). No system-wide install | 
| Docker | Engine started for Phase 2 (image `postgres:16-alpine`). Stop it when not needed: `docker stop roamlary-postgres-dev` |
| Flutter | 3.47.7 stable (frontend untouched by backend work) |
| Secrets in repo | **None found** — only `.env.example` templates exist |
| Frontend project | `frontend/roamlary_app` — default Flutter template, no app logic, no HTTP package |

## 3. Development phases and status

Roadmap assigned by the project owner (Phases 2+ are NOT started; the backend
lead waits for each phase assignment):

| Phase | Name | Status |
|---|---|---|
| 0 | Repository inspection & planning | ✅ Complete (approved by owner: "ok you can do that") |
| 1 | FastAPI foundation | ✅ **Complete — implemented & verified** (this report §7) |
| 2 | PostgreSQL connection, models, migrations | ✅ **Complete — implemented & verified** (this report §8) |
| 3 | Authentication & user profiles | ⏳ Not started — awaiting owner assignment |
| 4 | Trusted contacts & safety check-ins | ⏳ Not started |
| 5 | SOS & emergency workflow (simulated) | ⏳ Not started |
| 6 | Community safety reports & location data | ⏳ Not started |
| 7 | AI companion & safety signals | ⏳ Not started (needs Laptop 3 contract) |
| 8 | Notifications & background-job interfaces | ⏳ Not started |
| 9 | Flutter integration & API contract alignment | ⏳ Not started (needs frontend report) |
| 10 | Automated testing, security checks, QA | ⏳ Not started |
| 11 | Final integration, documentation, demo readiness | ⏳ Not started |

**Strict phase boundaries:** Phase 2 added the database *foundation* only —
configuration, engine, sessions, five ORM models, and Alembic migrations. It
contains **NO** API CRUD endpoints, NO authentication, NO check-in/SOS/report
*workflows*, NO AI, NO notifications — the tables exist but nothing exposes
them over HTTP. Each of those belongs to its assigned later phase.

## 4. Chronological change log

| Date | Task | What happened | Git state |
|---|---|---|---|
| 2026-10-11 | Phase 0 / Task 001 | Read-only repository inspection: found empty `backend/`+`docs/`, Flutter template frontend, Python 3.13 available, no PostgreSQL, Docker engine off, no secrets, no API contract | no changes |
| 2026-10-11 | Phase 0 / Task 002 (pre-Phase-1 approval) | Owner approved scaffolding: created `backend` branch + FastAPI skeleton, config, `/api/v1/health` v1 response, 3 tests, gitignores, README | commit `c06d092` (local) |
| 2026-10-12 | REPORT.md | Owner requested development log file → created `backend/REPORT.md` | commit `11f2d7e` (local) |
| 2026-10-12 | Phase 0 (formal) | Formal read-only re-inspection & plan delivered (architecture, proposed API, proposed DB, Phases 0–11 plan, reporting standard). Zero changes made | no changes |
| 2026-10-12 | **Phase 1** | Owner assigned Phase 1 → aligned health contract to owner-specified format, removed premature `database_url` setting, expanded tests 3→7, updated README, renamed `REPORT.md`→`report.md`, rewrote this report | **uncommitted working-tree changes** (owner rule: no commits during phases) |
| 2026-10-12 | **Phase 2** | Owner assigned Phase 2 → started Docker engine (approved K4), ran `postgres:16-alpine` container, added `DATABASE_URL` config, engine/session/get_db, 5 models, Alembic + initial migration (applied to `roamlary_dev`), 28 new tests, README + this report | **uncommitted working-tree changes** (Phase 1 + Phase 2 both uncommitted; still no commits) |

## 5. Proposed API contract — only what is IMPLEMENTED is a contract

**Implemented and verified (Phase 1):**

| Method + Path | Purpose | Auth | Response |
|---|---|---|---|
| `GET /api/v1/health` | Liveness check (process is running). Does NOT check database/AI/notifications | none | see below |

```json
GET /api/v1/health  →  HTTP 200
{
  "status": "ok",
  "service": "roamlary-backend",
  "version": "1.0.0"
}
```

Unknown routes return HTTP 404. Interactive documentation at `/docs`, machine
contract at `/api/v1/openapi.json`.

**Proposed for future phases — NOT IMPLEMENTED, do not call these:**
`POST /auth/login`, `GET/PATCH /users/me`, `GET/POST/DELETE /contacts…`,
`POST /check-ins`, `POST /check-ins/{id}/response`, `POST/GET/PATCH /sos/events…`,
`POST /reports`, `GET /reports?lat&lon&radius`, `POST /ai/companion/messages`.
(To be formalized with the owner during Phase 9 frontend alignment.)

## 6. Database design — IMPLEMENTED (Phase 2)

Schema is now real: Alembic migration `cc78d54068bb` ("initial schema")
applied to `roamlary_dev`. Full design rationale in §8.4.

| Table | Purpose | Owner / deletion rule |
|---|---|---|
| `users` | Account profile (UUID PK, `firebase_uid` nullable+unique, `display_name`, `email` nullable+unique, timestamps) | — |
| `trusted_contacts` | Nominated safety contact (`name`, `phone`, `email` nullable) | `users` · `ON DELETE RESTRICT` |
| `check_ins` | "Ping me by time T" (`status`, `due_at`, `completed_at`) | `users` · `ON DELETE RESTRICT` |
| `sos_events` | **Simulated** incident (`status`, lat/lon, `resolved_at`) | `users` · `ON DELETE RESTRICT` |
| `community_reports` | Crowd-sourced note (`category`, `description`, lat/lon, `status`) | `users` · `ON DELETE RESTRICT` |

Status values are enforced by CHECK constraints; lat/lon are range-guarded.
Deletion is deliberately **RESTRICT** (not cascade) so safety history can never
disappear by accident — revisit with the owner in the phase that owns account
deletion.

## 7. Phase 1 record — FastAPI foundation ✅

### 7.1 Phase information

- **Phase:** 1 — FastAPI Foundation · **Status:** Complete, awaiting owner review
- **Objective:** minimal structured FastAPI backend that starts locally, exposes
  a versioned health endpoint, loads configuration safely, and is tested
  automatically.
- **Prerequisites:** Phase 0 approved; Python 3.13 + venv (verified). No
  database, Firebase, or AI dependencies required — and none used.
- **Owner rules applied:** work only on verified `backend` branch; no commits,
  no pushes; no Phase 2 features; document everything here.

### 7.2 File-by-file change log (Phase 1)

| Path | Created / Modified | Why it exists & how it works (simple language) | What breaks without it |
|---|---|---|---|
| `app/api/v1/endpoints/health.py` | **Modified** | The `GET /api/v1/health` route. Phase 1 change: response aligned to the owner-approved contract — exactly `status`, `service` ("roamlary-backend"), `version` (from settings). The previous response also carried an `environment` field and a different service name; the owner's Phase 1 spec defined the target format, so it now matches. Docstring states it is liveness-only. Interacts with: `config.py` (reads `app_version`), `router.py` (registers it) | Without it: `/api/v1/health` returns 404 and there is no liveness signal for anyone — frontend, owner, or tests |
| `app/core/config.py` | **Modified** | The `Settings` class (pydantic-settings) reads env vars / `.env` with types + defaults. Phase 1 changes: default `app_version` → `1.0.0`; **removed `database_url`** because the owner's spec assigns database settings to Phase 2 ("do not add PostgreSQL connection settings… belongs to later phases"). It will return in Phase 2 when actually used. CORS origins parsing (comma-separated string → list) unchanged | Without it: configuration would be hard-coded, CORS not adjustable per machine, and secrets-avoidance impossible |
| `.env.example` | **Modified** | Template of every setting with placeholder values + comments explaining each origin scenario (web, emulator `10.0.2.2`, real phone LAN IP). DATABASE_URL section removed with a note explaining it returns in Phase 2. Never overwritten: a real `.env` (if created) is gitignored and untouched | Without it: the owner/Laptop 2 would guess which settings exist |
| `pyproject.toml` | **Modified** | Package version bumped `0.1.0 → 1.0.0` so the package metadata agrees with the health contract version. (Editable-install metadata refreshes on the next `pip install -e .`; runtime and tests are unaffected.) Dependencies unchanged — already exactly what Phase 1 needs | Without it: version confusion between docs, package, and API |
| `tests/test_health.py` | **Rewritten** | Now 7 tests covering every owner-required check: (1) app imports & initializes (2) health returns HTTP 200 (3) body has exactly the 3 contract fields with correct values (4) all OpenAPI paths live under `/api/v1/` (router registered correctly) (5) unknown route → 404 (6a) configured CORS origin receives `access-control-allow-origin` (6b) unknown origin gets none (7) `/docs` renders. Runs without DB/network | Without it: no proof the contract holds; regressions would reach Flutter silently |
| `README.md` | **Rewritten** | Human quick-start: Phase 1 scope, explicit "not implemented yet" list, verified Python version, setup/run/test commands, the exact health contract, CORS explanation (what it is, when it matters, emulator vs real phone), a "Common problems" troubleshooting table | Without it: owner/Laptop 2 cannot reproduce the setup without reading this whole report |
| `backend/report.md` | **Renamed + rewritten** | This file. `git mv REPORT.md report.md` records a clean case-only rename so the mandated lowercase name works on GitHub (case-sensitive URLs). Contents restructured to the approved reporting standard; all Phase 0 findings preserved in Part 2 | Without it: no living record of decisions, commands, results, and limitations |

**Unchanged on purpose** (verified correct for Phase 1, deliberately not
touched): `app/main.py` (app factory + CORS middleware + v1 router — already
matches Task B), `app/api/v1/router.py` (aggregation point), all `__init__.py`
packages, `tests/conftest.py` (shared TestClient fixture), both `.gitignore`
files.

> **Structure note (Task A):** the owner's example suggested
> `app/api/router.py` + `app/api/routes/health.py`. The actual Phase 0-approved
> structure nests a `v1/` folder (`app/api/v1/router.py` + `app/api/v1/
> endpoints/health.py`). This is a deliberate, documented difference: versioning
> is expressed in the filesystem, so `/api/v2/` can be added later without
> touching v1 files. Behavior and URL paths are identical.

### 7.3 How a request travels through the app (actual implementation)

```
Flutter/browser  GET http://127.0.0.1:8000/api/v1/health
      ↓
uvicorn (server process, port 8000)
      ↓
CORS middleware  → caller's Origin checked against cors_origins (from .env/env)
      ↓              allowed → request continues (+ allowance header)
      ↓              unknown → request continues but BROWSER blocks the response
FastAPI router   → "/api/v1" prefix → app/api/v1/router.py → endpoints/health.py
      ↓
get_health() returns {"status","service","version"}
      ↓
FastAPI serializes dict → JSON + HTTP 200
      ↓
Flutter receives: {"status":"ok","service":"roamlary-backend","version":"1.0.0"}
```

### 7.4 Dependencies (unchanged from approved set)

`fastapi==0.143.0` (framework) · `uvicorn[standard]==0.54.0` (server) ·
`pydantic-settings==2.15.0` (typed env config) · dev: `pytest==8.4.2` (tests),
`httpx2==2.13.1` (powers FastAPI's test client — newer starlette deprecates
`httpx`), `ruff==0.17.0` (lint/format). **Not added:** SQLAlchemy, Alembic,
psycopg (Phase 2), auth packages (Phase 3), AI/notification SDKs (later) —
Phase 1 needs none of them and installing unused packages is risk without value.

### 7.5 Commands executed (Windows PowerShell, from `backend/`)

```powershell
# Tests + lint
.venv\Scripts\python -m pytest -v
.venv\Scripts\python -m ruff check .

# Live verification (server started, queried, stopped)
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

### 7.6 Actual test results (real output, 2026-10-12)

```
platform win32 -- Python 3.13.2, pytest-8.4.2
collected 7 items
tests/test_health.py::test_app_can_be_imported_and_initialized PASSED   [ 14%]
tests/test_health.py::test_health_returns_ok PASSED                     [ 28%]
tests/test_health.py::test_versioned_api_router_is_registered PASSED    [ 42%]
tests/test_health.py::test_unknown_route_returns_404 PASSED             [ 57%]
tests/test_health.py::test_cors_allows_configured_dev_origin PASSED     [ 71%]
tests/test_health.py::test_cors_does_not_allow_unknown_origin PASSED    [ 85%]
tests/test_health.py::test_docs_page_is_available PASSED                [100%]
============================== 7 passed in 0.11s ==============================
ruff: All checks passed!
```

Live server verification (real output):

```
ACTUAL HEALTH RESPONSE: {"status":"ok","service":"roamlary-backend","version":"1.0.0"}
DOCS STATUS: 200
UNKNOWN ROUTE STATUS: 404
```

Limitations of these checks: they run on one Windows machine, in-process for
pytest (no real network) plus one real uvicorn smoke test; CORS was verified
via HTTP headers, not inside a real browser.

### 7.7 Security notes (Phase 1)

- No secrets exist or are needed yet. `.env` is gitignored; `.env.example`
  contains placeholders only; the real `.env` is never overwritten.
- CORS: explicit origin list (no `*`), credentials allowed only for
  allow-listed origins, deny-by-default proven by test. **Development-grade** —
  a production review (HTTPS, rate limiting, stricter origins) is required
  before any production claim (Phase 10/11).
- The health response intentionally exposes nothing environment-specific.
- Unresolved concerns: none for Phase 1. (Firebase/DB secrets arrive with
  their phases and will be handled then.)

### 7.8 Completion and next steps

Complete: app starts; `GET /api/v1/health` returns the documented contract;
7/7 tests pass; lint clean; CORS documented & verified; README + this report
written; frontend untouched; **no commits, pushes, merges, or branch changes
were performed in Phase 1** (all Phase 1 changes sit in the working tree for
owner review).

Incomplete/blocked: nothing within Phase 1 scope. **PostgreSQL, SQLAlchemy,
Alembic, and everything from Phase 2 onward are explicitly NOT implemented.**

Recommended next action: owner reviews the Phase 1 diff (`git diff` on
`backend`), then **assigns Phase 2** (which will include starting Docker
Desktop for the `postgres:16` container — separate explicit approval needed).

## 8. Phase 2 record — PostgreSQL, models & migrations ✅

### 8.1 Phase information

- **Phase:** 2 — PostgreSQL database, SQLAlchemy models, Alembic migrations,
  database testing · **Status:** Complete and verified on this machine
  (awaiting owner review; nothing committed)
- **Objective:** a maintainable persistence foundation — secure config, engine
  and session management, five initial domain models, Alembic as the single
  authority over the schema, an applied initial migration, and tests that
  report honestly what they do and do not prove.
- **Prerequisites:** Phase 1 foundation; Python 3.13 venv with SQLAlchemy,
  Alembic and psycopg **already installed and pinned** (no new packages were
  needed); Docker engine (started with the owner-approved K4 decision).
- **Owner rules applied:** work only on the verified `backend` branch; no
  commits, no pushes, no branch/merge/reset; do not touch the frontend; never
  print secrets; document everything here.

### 8.2 File-by-file change log

**Path:** `backend/app/db/base_class.py`
**Action:** Created.
**Purpose:** One shared foundation every table inherits, so all tables get the
same primary key, timestamps and constraint names without duplicated code.
**How it works:** `Base` is SQLAlchemy's declarative base carrying a naming
convention (e.g. every CHECK constraint is named `ck_<table>_<name>`) so
identical names are produced on PostgreSQL *and* SQLite and migrations stay
stable. `UUIDPrimaryKeyMixin` adds an `id` column of type `Uuid` (random
128-bit identifier — no sequential numbers leaking how many rows exist).
`TimestampMixin` adds `created_at`/`updated_at`, both timezone-aware UTC;
`updated_at` refreshes automatically on every update. `utc_now()` is the one
place that produces "now" in UTC.
**Connections:** inherited by all five models in `app/models/`; `Base.metadata`
is what Alembic reads to know the full schema.
**Verification:** `tests/test_models.py::test_primary_keys_are_uuid_columns`
and the metadata tests; migration `cc78d54068bb` generated from this metadata.

**Path:** `backend/app/db/session.py`
**Action:** Created.
**Purpose:** The three moving parts every future API route will need — an
engine, a session factory, and a per-request session helper.
**How it works:** `engine = create_engine(settings.database_url,
pool_pre_ping=True)` builds the pooled connection channel. Crucially,
`create_engine` does **not** open a connection — the first real connection
happens on first use, so importing the app never requires the database to be
up. `SessionLocal` is the factory that produces one short-lived session (one
"conversation" with the database). `get_db()` is a generator dependency: it
yields one session and, in a `finally` block, closes it even if a route
raises — sessions can never leak.
**Connections:** reads `settings.database_url` from `config.py`; will be used
by Phase 3+ routes as `Depends(get_db)`; exercised offline by
`tests/test_db_operations.py::test_get_db_yields_a_session_and_always_closes_it`.
**Verification:** the offline session-lifecycle test above plus every SQLite
fixture test.

**Path:** `backend/app/db/__init__.py`
**Action:** Created.
**Purpose:** Package marker that re-exports `Base`, `engine`, `SessionLocal`,
`get_db` so callers can `from app.db import get_db`.
**Connections/Verification:** import-level only; covered by the app import
test.

**Path:** `backend/app/models/enums.py`
**Action:** Created.
**Purpose:** The *only* allowed values for the three status columns, defined
once as Python `StrEnum`s.
**How it works:** `CheckInStatus` (pending/safe/needs_help/expired),
`SosStatus` (active/acknowledged/resolved/false_alarm), `ReportStatus`
(pending/approved/rejected). Using an enum means a typo fails immediately
instead of silently reaching the database; the model files mirror the same
values in CHECK constraints for defence in depth.
**Connections:** referenced by `check_in.py`, `sos_event.py`,
`community_report.py`; asserted in `tests/test_models.py` and the PostgreSQL
integration tests.
**Verification:** `test_status_enums_match_the_contract`.

**Path:** `backend/app/models/user.py`
**Action:** Created.
**Purpose:** The account/profile table every other table points at.
**How it works:** `User` mixes in the UUID key and timestamps, then adds
`firebase_uid` (optional, unique, indexed — the external auth identity that a
later phase will fill; empty until then), `display_name` (required, max 80),
`email` (optional, unique, max 254). **No password column exists anywhere** —
authentication is Phase 3. Four relationships (`trusted_contacts`,
`check_ins`, `sos_events`, `community_reports`) are declared with
`back_populates` so both directions of each one-to-many stay in sync.
**Connections:** FK target for all four child tables; imported by Alembic
through `app/models/__init__.py`.
**Verification:** `test_user_columns_and_uniqueness`,
`test_create_and_read_user`, PostgreSQL `test_user_and_contact_round_trip`.

**Path:** `backend/app/models/trusted_contact.py`
**Action:** Created.
**Purpose:** One nominated emergency contact belonging to exactly one user.
**How it works:** `user_id` is a required foreign key to `users.id` with
`ondelete="RESTRICT"` and an index (join/lookup performance). `name` and
`phone` are required; `email` is optional.
**Connections:** `owner` relationship back to `User.trusted_contacts`.
**Verification:** `test_contact_requires_an_owner`,
`test_user_with_trusted_contact_relationship`.

**Path:** `backend/app/models/check_in.py`
**Action:** Created.
**Purpose:** A "ping me by time T" promise — the data shape for the future
check-in feature, without implementing any scheduling logic.
**How it works:** `status` defaults to `pending` and is index (the future
expiry job queries pending rows) and guarded by a CHECK constraint listing the
four valid values. `due_at` (optional deadline) and `completed_at` (when the
user answered) are nullable timezone-aware timestamps.
**Connections:** `user` relationship back to `User.check_ins`.
**Verification:** `test_check_in_defaults_to_pending`,
`test_check_in_invalid_status_is_rejected`,
PostgreSQL `test_check_constraint_allows_valid_status`.

**Path:** `backend/app/models/sos_event.py`
**Action:** Created.
**Purpose:** One **simulated** emergency incident. This prototype contacts no
emergency services.
**How it works:** `status` defaults to `active` (lifecycle
active→acknowledged→resolved/false_alarm) with a CHECK constraint;
`latitude`/`longitude` are optional and range-guarded by CHECK constraints
(−90..90 / −180..180); `resolved_at` records cancellation or resolution.
**Connections:** `user` relationship back to `User.sos_events`.
**Verification:** `test_sos_event_defaults_and_location_stored`,
`test_sos_event_out_of_range_location_rejected`.

**Path:** `backend/app/models/community_report.py`
**Action:** Created.
**Purpose:** A crowd-sourced safety observation attached to the authenticated
user who submitted it (accountability), focused on the location and concern.
**How it works:** `category` (required, max 40 — deliberately no hard-coded
list, since categories are a later product decision), `description`
(required `Text`), optional range-guarded lat/lon, `status` defaulting to
`pending` with a CHECK constraint.
**Connections:** `user` relationship back to `User.community_reports`.
**Verification:** `test_community_report_created_pending`.

**Path:** `backend/app/models/__init__.py`
**Action:** Created.
**Purpose:** Imports every model so that `import app.models` registers **all**
tables with SQLAlchemy's registry. This single import is exactly how Alembic
discovers the schema.
**Connections:** imported by `alembic/env.py` and by the PostgreSQL
integration tests.
**Verification:** `test_all_tables_are_registered`.

**Path:** `backend/app/core/config.py`
**Action:** Modified.
**Purpose:** Re-introduce `database_url` (removed in Phase 1 because it was
premature) now that the database is real.
**How it works:** `database_url` is read from the environment / `.env` like
every other setting; the built-in default is a placeholder-credential URL so
the app imports cleanly without a real database.
**Connections:** consumed by `app/db/session.py` and `alembic/env.py`.
**Verification:** every database test uses it indirectly; the live health
smoke test confirms the app still boots with it present.

**Path:** `backend/.env.example`
**Action:** Modified.
**Purpose:** Document `DATABASE_URL` in the placeholder template.
**How it works:** Shows the SQLAlchemy URL shape
(`postgresql+psycopg://USER:PASSWORD@localhost:5432/DBNAME`) with fake
credentials. The real `.env` (with the container password) was created locally
and is **gitignored**; it was never overwritten or printed.
**Connections:** paired with `config.py`.
**Verification:** `git status --ignored` shows `backend/.env` as ignored (`!!`).

**Path:** `backend/alembic.ini`
**Action:** Created.
**Purpose:** Alembic's own configuration file.
**How it works:** Points `script_location` at `alembic/`. The
`sqlalchemy.url` value in this file is an unused placeholder — the real URL is
supplied at runtime by `alembic/env.py` from Settings, so **no credentials are
ever committed here**.
**Connections:** read by every `python -m alembic …` command.
**Verification:** all migration tests and the applied migration.

**Path:** `backend/alembic/env.py`
**Action:** Created.
**Purpose:** Runs on every Alembic command; answers two questions — *which
database* and *which tables*.
**How it works:** It inserts the backend directory into `sys.path`, imports
`app.models` (registering every table), imports `Base.metadata` as
`target_metadata`, and sets the connection URL from
`settings.database_url` (escaping `%` so passwords containing it survive the
config parser). It supports offline mode (emit SQL only, no connection) and
online mode (apply against the live database).
**Connections:** `config.py`, `app/models`, `alembic.ini`, all files in
`alembic/versions/`.
**Verification:** `tests/test_migrations.py` runs real `alembic upgrade` /
`downgrade` / `history` subprocesses against a throwaway SQLite file.

**Path:** `backend/alembic/versions/cc78d54068bb_initial_schema.py`
**Action:** Created (generated by autogenerate, then **reviewed**).
**Purpose:** The initial schema: creates all five tables with their columns,
UUID primary keys, foreign keys with `ON DELETE RESTRICT`, CHECK constraints
and the six justified indexes; `downgrade()` drops them again.
**How it works:** Autogenerate diffed the empty `roamlary_dev` against
`Base.metadata` and proposed these operations. I reviewed every line against
the models before applying. It is committed as source code.
**Connections:** the authoritative schema for `roamlary_dev`.
**Verification:** applied successfully; `alembic current` → `cc78d54068bb
(head)`; `psql \dt` listed all six tables; migration round-trips on SQLite.

**Path:** `backend/tests/conftest.py`
**Action:** Modified (extended).
**Purpose:** Add two offline database fixtures alongside the existing
`client` fixture.
**How it works:** `sqlite_engine` builds an in-memory SQLite engine, turns on
SQLite's `PRAGMA foreign_keys=ON` (SQLite disables them by default, so
`RESTRICT` would otherwise not be testable), and creates/drops all tables
around each test. `db_session` yields one always-closed session per test.
**Connections:** used by `test_models.py` and `test_db_operations.py`.
**Verification:** every offline database test.

**Path:** `backend/tests/test_models.py` · `test_db_operations.py` ·
`test_migrations.py` · `test_postgres_integration.py`
**Action:** Created (28 new tests total).
**Purpose:** Cover metadata (tables, UUID keys, columns, foreign keys, CHECK
constraints), real behaviour (create/read, relationships, defaults, deletion
restriction, `updated_at`), migration wiring (upgrade creates exactly the
expected tables, downgrade removes them, history is a linear chain), and
PostgreSQL-specific behaviour.
**How it works:** The first three are offline and need no database. The fourth
is **skipped unless** `ROAMLARY_TEST_DATABASE_URL` points at a **disposable**
database; it then checks the `id` column is a native `uuid`, round-trips a
user + contact, and proves CHECK constraints accept/reject at the SQL level.
**Verification:** see §8.9.

**Path:** `backend/pyproject.toml`
**Action:** Modified (lint config only).
**Purpose:** Exclude the generated `alembic/versions/` from Ruff, since
auto-generated migration files legitimately use formatting Ruff would rewrite.
**How it works:** `extend-exclude = ["alembic/versions"]`.
**Verification:** `ruff check .` and `ruff format --check .` both pass clean.

**Path:** `backend/README.md`
**Action:** Modified (extended).
**Purpose:** Add database architecture, the five tables, how to create a dev
container, how to configure `DATABASE_URL`, migration commands, how to run the
two test layers, and database troubleshooting.
**Verification:** every documented command was executed during this phase.

**Unchanged on purpose:** `app/main.py`, `app/api/v1/router.py`,
`app/api/v1/endpoints/health.py` (health contract byte-identical to Phase 1),
all package `__init__.py` files, both `.gitignore` files.

### 8.3 How the models relate

One user → many of each child; the parent link is a required foreign key.
```
users ──┬──< trusted_contacts   (user_id, RESTRICT)
        ├──< check_ins          (user_id, RESTRICT)
        ├──< sos_events         (user_id, RESTRICT)
        └──< community_reports  (user_id, RESTRICT)
```
`back_populates` keeps both directions in sync. Deletion is **RESTRICT**, not
cascade: you cannot delete a user who still has safety records — a deliberate
data-integrity decision, since silently cascading would erase safety history.
Account deletion policy is the owner's call in the phase that owns deletion.

### 8.4 Configuration without exposing credentials

`DATABASE_URL` is read by pydantic-settings from the environment or `.env`.
The real `.env` (holding the container password) is gitignored and was never
printed, committed, or pasted anywhere. `.env.example` carries a placeholder.
`alembic.ini`'s URL is a deliberately unused placeholder overwritten at runtime
by `env.py`. The report and README reference the URL only by shape, never by
value. Missing/invalid configuration fails loudly when the database layer is
first used, not at import time.

### 8.5 Session lifecycle

`get_db()` opens exactly one session per request and closes it in a `finally`
block, so it is closed even when a route raises. `expire_on_commit=False`
avoids surprise re-queries after a commit; `pool_pre_ping=True` discards
stale pooled connections. No route uses it yet — it exists so Phase 3 can add
`Depends(get_db)` safely.

### 8.6 How Alembic discovers models and applies migrations

`alembic/env.py` imports `app.models`, which registers every table with
SQLAlchemy's registry. `target_metadata = Base.metadata` is therefore the full
schema as expressed in code. `alembic revision --autogenerate` compares that
against the live database and proposes a migration; `alembic upgrade head`
applies it. Because migrations are committed files, any machine can replay the
schema from zero.

### 8.7 Dependency changes

**None.** SQLAlchemy 2.1.4, Alembic 1.20.0 and psycopg 3.3.6 were already
installed and pinned in the approved Phase 0/1 set, awaiting exactly this
phase. No unrelated package was upgraded; nothing was installed globally.

### 8.8 Commands executed (Windows PowerShell, from `backend/`)

```powershell
# Container + connectivity (password generated locally, never printed)
docker run -d --name roamlary-postgres-dev -e POSTGRES_USER=roamlary `
  -e POSTGRES_PASSWORD=<generated> -e POSTGRES_DB=roamlary_dev -p 5432:5432 postgres:16-alpine
docker exec roamlary-postgres-dev pg_isready -U roamlary -d roamlary_dev   # → ready

# Migrations (DATABASE_URL read from .env)
.venv\Scripts\python -m alembic revision --autogenerate -m "initial schema"
.venv\Scripts\python -m alembic upgrade head          # → cc78d54068bb applied
.venv\Scripts\python -m alembic current               # → cc78d54068bb (head)
.venv\Scripts\python -m alembic history               # → <base> -> cc78d54068bb (head)
docker exec roamlary-postgres-dev psql -U roamlary -d roamlary_dev -c "\dt"

# Tests + lint (integration URL derived from .env, value never printed)
$env:ROAMLARY_TEST_DATABASE_URL = (…derived… /roamlary_test)
.venv\Scripts\python -m pytest -q                      # → 35 passed
.venv\Scripts\python -m ruff check .                   # → clean
.venv\Scripts\python -m ruff format --check .          # → clean
```

### 8.9 Actual test results (real output, 2026-10-12)

Full suite with PostgreSQL integration enabled:
```
35 passed in 13.87s
```
Offline proof — container stopped, integration tests auto-skip:
```
31 passed, 4 skipped in 6.88s
```
Lint and formatting: `ruff check .` → All checks passed; `ruff format --check .`
→ 28 files already formatted. Live server smoke test (server started, queried,
stopped): `GET /api/v1/health` returned
`{"status":"ok","service":"roamlary-backend","version":"1.0.0"}` — unchanged.

### 8.10 PostgreSQL connectivity & migration status

- **Connectivity: verified.** Real connection to PostgreSQL 16.15 established
  through psycopg via SQLAlchemy (`SHOW server_version` → 16.15). Databases
  `roamlary_dev` (schema) and `roamlary_test` (disposable, for integration
  tests) both exist on the container.
- **Migration: generated, reviewed, and actually applied.** `alembic upgrade
  head` ran against `roamlary_dev`; `alembic current` reports `cc78d54068bb
  (head)`; `\dt` lists all five domain tables plus `alembic_version`. Nothing
  was stamped, and no migration history was edited.
- PostgreSQL-specific behaviour (native `uuid` column, CHECK enforcement,
  timezone-aware round-trip) is proven by the four integration tests against
  `roamlary_test`.

### 8.11 Security & data-integrity considerations

- No plaintext passwords anywhere; no password column exists. `firebase_uid`
  is an external identity reference only.
- Credentials live only in the gitignored `.env`; templates carry placeholders.
- `ON DELETE RESTRICT` prevents accidental erasure of safety history.
- CHECK constraints enforce status values and coordinate ranges at the
  database level, so even raw SQL cannot insert invalid data.
- The schema records no live location; lat/lon are stored only where
  intentionally provided, and no user-tracking fields exist.

### 8.12 Known issues & incomplete checks

- Integration tests **create and drop tables**, so they must only ever target a
  disposable database (`roamlary_test`). Pointing them at real data would be
  destructive — documented in the README.
- SQLite and PostgreSQL can still differ in subtle ways; the four PostgreSQL
  integration tests cover UUID, CHECK and timestamp behaviour but not every
  possible dialect difference.
- CORS, HTTPS and rate limiting remain development-grade (inherited from
  Phase 1; production review belongs to Phase 10/11).
- No query-performance testing has been done (no data volume yet).

### 8.13 Phase completion checklist

| Requirement | Status |
|---|---|
| Database configuration implemented | ✅ |
| Engine + session management implemented | ✅ |
| Five agreed domain models defined | ✅ |
| Alembic configured; initial migration generated, reviewed, applied | ✅ |
| Automated tests pass for what they cover | ✅ (35 passed) |
| Phase 1 health endpoint still works | ✅ (unchanged, re-verified live) |
| PostgreSQL connectivity & migration verified | ✅ (real connection; migration applied) |
| README updated | ✅ |
| This report contains an accurate file-by-file explanation | ✅ |
| Git branch and changes checked | ✅ (`backend`; zero commits/pushes) |
| No later-phase business workflows implemented | ✅ (no CRUD/auth/workflow code) |

### 8.14 Scope confirmation

Phase 2 implemented **no** authentication or authorization, no Firebase, no
user-profile/contact/check-in/SOS/report **API endpoints**, no check-in
scheduling, no SOS escalation, no AI, no notifications, no background workers,
no production deployment, and no seeded/fake records. The five tables are
foundation only.

**Recommended next step:** the owner reviews this phase (report + working-tree
diff) and, when satisfied, **assigns Phase 3** (authentication & user
profiles). Because Phase 1 and Phase 2 are both still uncommitted, the owner
may also ask for them to be committed first — the backend lead will not commit
or push without that instruction.

## 9. Known limitations (current)

- No API CRUD endpoints yet — the tables exist but nothing exposes them over
  HTTP; only `GET /api/v1/health` is served.
- No authentication, contacts, check-ins, SOS workflow, reports, AI, or
  notifications — all belong to later phases.
- Dev-grade CORS and configuration only; no HTTPS, no rate limiting.
- Runs only on this laptop, local machine, port 8000.
- Branch is local — nothing is backed up to GitHub until the owner approves a
  push. Phase 1 + Phase 2 changes are both still uncommitted.
- Database lives in a Docker container; if that container's volume is removed,
  recreate the (currently empty) schema with `alembic upgrade head`.
- Frontend cannot integrate beyond the health contract until Phase 9.

## 10. Pending tasks and next steps

1. Owner reviews Phase 1 **and** Phase 2 (this report + `git diff` on `backend`).
2. Decide whether to commit Phase 1 + Phase 2 before Phase 3 — the backend
   lead will not commit or push until explicitly instructed.
3. Owner assigns Phase 3 (authentication & user profiles).
4. Frontend `report.md` from Laptop 2 → enables Phase 9 contract-alignment
   planning and the `docs/merge-report.md` integration document.
5. Laptop 3 to publish the AI contract before Phase 7 can be real (stub until
   then).

---

# PART 2 — PRESERVED EARLIER FINDINGS

## A. Phase 0 — executive summary & inspection results (2026-10-12)

- Repository correctly initialized; three workstream folders (`backend`,
  `docs` (empty), `frontend`). Flutter project is a stock template with **no
  API dependency yet** — backend defines the contract first.
- Verified: branch `backend`, clean tree, remote `origin` configured, single
  remote. All verified with read-only commands.
- Environment: Python 3.13.2 ready; **PostgreSQL absent** (client/server/
  connection all confirmed absent — not assumed); Docker CLI present but
  engine OFF; Flutter 3.47.7 present for the frontend workstream.
- Security: **no secrets anywhere** in the repo; gitignores adequate
  (root + backend + Flutter's own). Risks logged: unpushed commits, personal
  email in commit metadata if repo is public, `REPORT.md` case naming (since
  resolved via `git mv` to `report.md`).

## B. Approved decisions (traceability)

| Decision | Choice | Status |
|---|---|---|
| Python version | 3.13 | in use |
| Packaging | venv + pip + pyproject.toml (pinned) | in use |
| PostgreSQL delivery | Docker `postgres:16` container | planned Phase 2 (needs Docker start approval) |
| Auth | local JWT now, Firebase-ready interface later | planned Phase 3 |
| API shape | `/api/v1`, port 8000, JSON, UUID PKs proposed | v1 prefix in use |
| DB style | sync SQLAlchemy | planned Phase 2 |
| Health contract | `status`/`service`/`version` = `ok`/`roamlary-backend`/`1.0.0` | **implemented** |
| Push policy | local commits only; owner reviews before push | in effect |
| Phase assignments | come from the project owner only | in effect |

## C. Task 002 — original scaffolding record (2026-10-11, commit `c06d092`)

Created the FastAPI application skeleton: `app/main.py` (app factory with CORS
middleware + versioned router mounting + Swagger `/docs`), `app/core/config.py`
(env-based settings), `app/api/v1/router.py` + `endpoints/health.py`, pytest
suite with TestClient fixture, `pyproject.toml` with exact pinned dependencies,
`.env.example`, `backend/.gitignore` and root `.gitignore`, and `README.md`.
Verified at the time: 3/3 tests green, ruff clean, live uvicorn smoke test
returned a health JSON, `/docs` 200. One deviation from the original plan:
`httpx` → `httpx2` because starlette 1.7.0 deprecates `httpx` for its test
client (deprecation warning observed, swap performed, warning verified gone).

## D. Task 001 — original inspection record (2026-10-11, read-only)

Repository root contained `.git`, empty `backend/`, empty `docs/`, and the
Flutter template. Git: single commit `4761b41` on `main`, clean tree, one
remote. Tools: Python 3.11.3 + 3.13.2, pip, no uv/poetry/pipx; psql absent; no
postgres service; Docker CLI 29.7.2 with engine off. No `.env`/secret-named
files anywhere (filename scan). Frontend: stock counter-demo app, only
`cupertino_icons` dependency — **no existing API contract for the backend to
preserve**.

## E. Glossary (survivor reference)

| Term | Plain meaning |
|---|---|
| API / endpoint | A documented URL+method for programs to talk to each other |
| HTTP verbs | GET=read · POST=create · PATCH/PUT=update · DELETE=remove |
| JSON | Standard text data format, e.g. `{"status":"ok"}` |
| FastAPI / uvicorn | The web framework / the server process that runs it |
| Middleware | Code that runs before every request (ours: CORS) |
| CORS | Browser rule deciding which sites may call this API |
| OpenAPI / Swagger | Standard API description; `/docs` is the browsable page |
| Pydantic-settings | Reads & validates config from env vars / `.env` |
| venv | Private project-local Python installation |
| Liveness check | "Is the process running?" — NOT a claim that dependencies work |
| ORM / migration | Python-classes-as-tables / versioned DB change scripts |
| Commit / branch / push | Saved snapshot / line of work / upload to GitHub |

---

*Owner review required before any Phase 1 change is committed. Next update
follows the assigned Phase 2.*
