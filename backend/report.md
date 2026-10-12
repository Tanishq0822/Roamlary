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
| Branch | `backend` (Phases 1–3 pushed to `origin/backend`; Phase 3 audit-fix delta uncommitted, see §9.14) |
| History | `4761b41` initial setup → `c06d092` scaffolding → `11f2d7e` report → `5ea9b59` Phase 1 → `eb8e709` Phase 2 → `3d728ac` Phase 3 → *(Phase 3 audit-fix delta uncommitted, see §9.14)* |
| Python | 3.13.2 in project venv (system also has 3.11.3) |
| pip | 26.2.1 inside `.venv` |
| PostgreSQL | **Running locally** — server 16.15 in the Docker container `roamlary-postgres-dev` (databases: `roamlary_dev`, `roamlary_test`). No system-wide install | 
| Docker | Engine started for Phase 2 (image `postgres:16-alpine`). Stop it when not needed: `docker stop roamlary-postgres-dev` |
| Flutter | 3.47.7 stable (frontend untouched by backend work) |
| Secrets in repo | **None found** — only `.env.example` templates exist (the real `JWT_SECRET_KEY` lives only in the gitignored `.env`) |
| Auth libraries | `argon2-cffi==25.1.0` (Argon2id password hashing) + `PyJWT==2.15.1` (HS256 JWTs), added in Phase 3 |
| Frontend project | `frontend/roamlary_app` — default Flutter template, no app logic, no HTTP package |

## 3. Development phases and status

Roadmap assigned by the project owner (Phases 0–3 complete; Phases 4+ are NOT
started — the backend lead waits for each phase assignment):

| Phase | Name | Status |
|---|---|---|
| 0 | Repository inspection & planning | ✅ Complete (approved by owner: "ok you can do that") |
| 1 | FastAPI foundation | ✅ **Complete — implemented & verified** (this report §7) |
| 2 | PostgreSQL connection, models, migrations | ✅ **Complete — implemented & verified** (this report §8) |
| 3 | Authentication & user profiles | ✅ **Complete** — implemented, committed `3d728ac`, pushed; owner-assigned audit & fix round done (§9.14), its delta uncommitted |
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
| 2026-10-12 | **Phase 1** | Owner assigned Phase 1 → aligned health contract to owner-specified format, removed premature `database_url` setting, expanded tests 3→7, updated README, renamed `REPORT.md`→`report.md`, rewrote this report | committed as `5ea9b59`, pushed to `origin/backend` (owner later said "commit and push") |
| 2026-10-12 | **Phase 2** | Owner assigned Phase 2 → started Docker engine (approved K4), ran `postgres:16-alpine` container, added `DATABASE_URL` config, engine/session/get_db, 5 models, Alembic + initial migration (applied to `roamlary_dev`), 28 new tests, README + this report | committed as `eb8e709`, pushed to `origin/backend` (owner approval) |
| 2026-10-12 | **Phase 3** | Owner assigned Phase 3 → local JWT auth (register/login), Argon2id hashing, protected `/users/me`, `password_hash` column + migration `d9841015aec7` (applied to `roamlary_dev`), 34 new tests, README + this report | committed as `3d728ac`, pushed to `origin/backend` (owner said "commit and push") |
| 2026-10-12 | **Phase 3 audit & fix** | Owner assigned Phase 3 verification round → audited all 4 endpoints, config, migration, and tests; fixed strict request schemas (422 on injected fields), login timing equalization, fail-closed-before-DB-write ordering, no-op PATCH `updated_at`, stale `config.py` docstring; added 12 new tests (fail-closed, required claims, race condition, impersonation, hermetic secret); corrected report/README contradictions | **uncommitted working-tree changes** (owner rule: no commits during a phase) |

## 5. Proposed API contract — only what is IMPLEMENTED is a contract

**Implemented and verified (Phase 1 + Phase 3):**

| Method + Path | Purpose | Auth | Response |
|---|---|---|---|
| `GET /api/v1/health` | Liveness check (process is running). Does NOT check database/AI/notifications | none | see below |
| `POST /api/v1/auth/register` | Create a local account; returns a bearer token (auto-login) | none | `{access_token, token_type}` (HTTP 201) |
| `POST /api/v1/auth/login` | Authenticate with email + password; returns a bearer token | none | `{access_token, token_type}` (HTTP 200) |
| `GET /api/v1/users/me` | Return the authenticated user's public profile | Bearer JWT | `UserProfile` (see §9.6) |
| `PATCH /api/v1/users/me` | Update the authenticated user's `display_name` | Bearer JWT | `UserProfile` |

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

Auth error behaviour: `POST /auth/register` returns **409** for a duplicate
email; `POST /auth/login` returns **401** with the *same* message for "unknown
email" and "wrong password" (so an attacker cannot enumerate accounts); a
missing/invalid/expired token on `/users/me` returns **401**; a request body
containing protected fields (e.g. `password_hash`, `id`, `firebase_uid`) on
`PATCH /users/me` returns **422**.

**Proposed for future phases — NOT IMPLEMENTED, do not call these:**
`GET/POST/DELETE /contacts…`, `POST /check-ins`,
`POST /check-ins/{id}/response`, `POST/GET/PATCH /sos/events…`, `POST /reports`,
`GET /reports?lat&lon&radius`, `POST /ai/companion/messages`.
Refresh tokens, password reset, and email verification are also **not**
implemented. (To be formalized with the owner during Phase 9 frontend
alignment.)

## 6. Database design — IMPLEMENTED (Phase 2)

Schema is real and now spans Phase 2 + Phase 3 migrations, all applied to
`roamlary_dev`:

- `cc78d54068bb` — "initial schema" (Phase 2): the five tables below.
- `d9841015aec7` — "add password_hash to users" (Phase 3): adds a nullable
  `password_hash` (varchar 255) to `users`. Full rationale in §9.10.

| Table | Purpose | Owner / deletion rule |
|---|---|---|
| `users` | Account profile (UUID PK, `firebase_uid` nullable+unique, `display_name`, `email` nullable+unique, `password_hash` nullable, timestamps) | — |
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
were performed in Phase 1** (all Phase 1 changes sat in the working tree for
owner review). *Post-phase fact:* after the owner later said "commit and
push", Phase 1 was committed as `5ea9b59` and pushed to `origin/backend`.

Incomplete/blocked: nothing within Phase 1 scope. *As of Phase 1's
completion,* PostgreSQL, SQLAlchemy, Alembic, and everything from Phase 2
onward were explicitly NOT implemented (Phases 2 and 3 have since been
completed — see §8 and §9; this sentence records the Phase 1 point in time).

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
| Git branch and changes checked | ✅ (`backend`; zero commits/pushes *during the phase* — Phase 2 was later committed as `eb8e709` and pushed after owner approval) |
| No later-phase business workflows implemented | ✅ (no CRUD/auth/workflow code) |

### 8.14 Scope confirmation

Phase 2 implemented **no** authentication or authorization, no Firebase, no
user-profile/contact/check-in/SOS/report **API endpoints**, no check-in
scheduling, no SOS escalation, no AI, no notifications, no background workers,
no production deployment, and no seeded/fake records. The five tables are
foundation only.

**Recommended next step:** the owner reviews this phase (report + working-tree
diff) and, when satisfied, **assigns Phase 3** (authentication & user
profiles). Phase 1 and Phase 2 are already committed (`5ea9b59`, `eb8e709`) and
pushed to `origin/backend`, so they are safely backed up before Phase 3.

## 9. Phase 3 record — Authentication & user profiles ✅

### 9.1 Phase information

- **Phase:** 3 — Local authentication (register/login) + protected user-profile
  endpoints · **Status:** Complete, awaiting owner review
- **Objective:** let a person create an account, log in, and read/edit their own
  profile — securely, locally, with **no** Firebase and no later-phase
  workflows.
- **Approved decisions applied:** *local JWT first, Firebase-ready later.*
  Email/password registration & login; only securely hashed passwords stored
  (Argon2id); signed JWT access tokens (HS256); the existing `firebase_uid`
  column stays optional/unused so future Firebase accounts fit; **no** Firebase
  Authentication, refresh tokens, password reset, or email verification.
- **Owner rules applied:** work only on verified `backend` branch; no commits,
  no pushes; preserve the health contract & DB foundation; document here.

### 9.2 How an auth request travels (actual implementation)

```
POST /api/v1/auth/register  {display_name, email, password}
  → schemas/auth.py RegisterRequest validates + normalizes email (trim+lower)
  → endpoints/auth.py register(): reject 409 if email taken
  → security.py hash_password() = Argon2id hash (plaintext never stored)
  → INSERT user, COMMIT
  → security.py create_access_token(user.id) = HS256 JWT {sub, iat, exp}
  → 201 {access_token, token_type:"bearer"}

POST /api/v1/auth/login  {email, password}
  → look up user by normalized email
  → security.py verify_password() constant-time check against the hash
  → success: 200 {access_token,...}   failure: 401 "Invalid email or password."
     (same message for unknown-email and wrong-password → no account enumeration)

GET /api/v1/users/me   Authorization: Bearer <jwt>
  → deps.py get_current_user: OAuth2PasswordBearer extracts the token
  → security.py decode_access_token(): verify HS256 signature + exp + sub
  → load User by the sub UUID from the DB; if gone → 401
  → handlers return ONLY the public UserProfile (no password_hash)
```

Identity ALWAYS comes from the verified token's `sub` claim — never from a
client-supplied user id — so one user cannot read or edit another's profile.

### 9.3 File-by-file change log (Phase 3)

| Path | Created / Modified | Why it exists & how it works (simple language) | What breaks without it |
|---|---|---|---|
| `app/core/security.py` | **Created** | The two "security verbs": `hash_password`/`verify_password` (Argon2id via `argon2-cffi`, OWASP params time_cost=3, memory_cost=64 MiB, parallelism=4) and `create_access_token`/`decode_access_token` (HS256 via `PyJWT`). The algorithm is a **constant**, never read from the token (blocks algorithm-confusion). `_require_secret()` **fails closed** (503) if `JWT_SECRET_KEY` is empty, so no token is ever signed with a weak/default secret. Tokens carry only `sub`+`iat`+`exp` — no password/hash/PII | Without it: endpoints would hold crypto logic; a usable secret could leak into code; "none"-algorithm attacks possible |
| `app/api/v1/schemas/auth.py` | **Created** | Pydantic shapes for the API. `RegisterRequest`/`LoginRequest` (EmailStr + password 8–128), a `normalize_email` validator (trim+lower), `TokenResponse`, and crucially `UserProfile` — the PUBLIC shape that **omits `password_hash`** so it can never be returned. `UserProfileUpdate` has `extra="forbid"` so `PATCH` with `id`/`password_hash`/`firebase_uid` is a 422, not silently ignored | Without it: unvalidated input; the password hash could leak in a response; protected fields could be smuggled in |
| `app/api/v1/deps.py` | **Created** | `get_current_user` — the gatekeeper. `OAuth2PasswordBearer` pulls the bearer token (auto-401 if missing); `decode_access_token` validates it; then loads the User by `sub`. A valid token for a deleted user still gets 401. Exports `CurrentUser`/`DbSession` type aliases so handlers stay short | Without it: no reusable way to say "this route needs a logged-in user"; identity could be taken from the request body |
| `app/api/v1/endpoints/auth.py` | **Created** | `POST /auth/register` (409 on duplicate, incl. a race caught by the unique constraint via `IntegrityError`→rollback→409) and `POST /auth/login` (identical 401 for unknown-email vs wrong-password). Both stay thin; crypto lives in `security.py` | Without it: no way to create an account or obtain a token |
| `app/api/v1/endpoints/users.py` | **Created** | `GET /users/me` and `PATCH /users/me`. Identity from the token only. PATCH edits `display_name`, bumps `updated_at`, commits, and relies on `extra="forbid"` to reject protected fields | Without it: no protected profile to prove the token works and that hashes stay private |
| `app/models/user.py` | **Modified** | Added `password_hash: Mapped[str \| None]` (varchar 255). **Nullable** so a future Firebase-only account needs no local password; local registration always sets it. Never in any public schema | Without it: no place to store the hash → local login impossible |
| `app/core/config.py` | **Modified** | Added `jwt_secret_key` (empty by default → auth fails closed) and `access_token_expire_minutes` (60, short for the prototype). Both read from env/`.env` like every other setting | Without it: the signing secret & lifetime would be hard-coded |
| `.env.example` | **Modified** | Added `JWT_SECRET_KEY=` (empty) + `ACCESS_TOKEN_EXPIRE_MINUTES=60` with a PowerShell command to generate a random secret. Placeholders only | Without it: the owner wouldn't know these settings exist or how to make a secret safely |
| `app/api/v1/router.py` | **Modified** | Registered `auth.router` and `users.router` alongside `health` | Without it: the new routes would 404 |
| `pyproject.toml` | **Modified** | Pinned `argon2-cffi==25.1.0`, `PyJWT==2.15.1`, `email-validator==2.3.0` (needed by Pydantic's `EmailStr`). One library per job; no duplicates | Without it: reproducible installs break; `EmailStr` wouldn't validate |
| `alembic/versions/d9841015aec7_add_password_hash_to_users.py` | **Created (autogenerated, reviewed, applied)** | Adds nullable `users.password_hash`; `downgrade()` drops it. Review below | Without it: the DB has no hash column |
| `tests/test_auth.py` | **Created** | 21 tests: register (creates user / hashed-not-plaintext / no-hash-in-response / 409 duplicate / case-insensitive 409 / invalid email 422 / short password 422), login (success / wrong password 401 / identical error for unknown-vs-wrong / safe claims), JWT validation (missing/malformed/expired/bad-signature/`alg=none`/deleted-user all 401), plus hash round-trip & per-hash salt | Without it: auth could regress silently |
| `tests/test_users_profile.py` | **Created** | 10 tests: GET returns own profile / requires token / never exposes hash; PATCH updates+persists / rejects protected fields (422) / rejects blank / requires token; two users can't cross-read; email normalized | Without it: profile privacy & self-edit rules unproven |
| `tests/test_postgres_integration.py` | **Modified** | 3 new real-PostgreSQL tests: `password_hash` column exists & nullable, an Argon2id hash round-trips, and a Firebase-only row with NULL hash is storable | Without it: SQLite wouldn't prove the real column behaviour |

**Unchanged on purpose:** `app/api/v1/endpoints/health.py` (contract byte-identical),
`app/main.py`, the other four models, all `__init__.py` files, both `.gitignore`.

### 9.4 JWT configuration & security decisions

- **Algorithm fixed to HS256** in `security.py` — `decode` passes
  `algorithms=[ALGORITHM]`, so a token claiming `alg: none` or `RS256` is
  rejected (verified by `test_algorithm_confusion_none_rejected`).
- **Fail-closed:** an empty `JWT_SECRET_KEY` makes `create/decode_access_token`
  raise **503** before any token is issued or trusted. A usable secret is
  therefore never hard-coded and never defaulted.
- **Secret hygiene:** the real 48-char secret lives only in the gitignored
  `.env` (generated locally, never printed, never committed). `.env.example`
  shows the generation command, not a value.
- **Claims:** only `sub` (user UUID), `iat`, `exp`. No password, hash, email, or
  other PII inside the token.
- **Lifetime:** `ACCESS_TOKEN_EXPIRE_MINUTES=60` — deliberately short. **Known
  limitation:** there are **no refresh tokens**, so a user re-logs-in when the
  token expires. Acceptable for a hackathon prototype, not for production.
- **Public `/health` is independent of JWT config** — it starts and answers
  even with an empty secret (verified by `test_health_still_works_with_auth_configured`).
- **Password storage:** Argon2id, a modern memory-hard algorithm. It is
  intentionally slow/memory-heavy so a leaked hash database is expensive to
  crack. Each hash embeds a fresh random salt (two identical passwords →
  different hashes, verified by a test).

### 9.5 Registration & login — request/response examples

```jsonc
// POST /api/v1/auth/register  →  HTTP 201
// request
{ "display_name": "Asha", "email": "  Asha@Example.COM ", "password": "s3cure-Pass!" }
// response  (email is normalized to "asha@example.com"; NO password/hash returned)
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer" }

// duplicate email  →  409 { "detail": "An account with this email already exists." }
// weak password / bad email  →  422 (validation error)

// POST /api/v1/auth/login  →  HTTP 200
// request
{ "email": "asha@example.com", "password": "s3cure-Pass!" }
// response
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer" }
// wrong password OR unknown email  →  401 { "detail": "Invalid email or password." }
```

### 9.6 User-profile endpoints & the public shape

```jsonc
// GET /api/v1/users/me   Authorization: Bearer <jwt>  →  200
// The ONLY fields ever returned — password_hash & firebase_uid are absent:
{ "id": "3f1a…", "display_name": "Asha", "email": "asha@example.com",
  "created_at": "2026-10-12T…", "updated_at": "2026-10-12T…" }

// PATCH /api/v1/users/me   Bearer <jwt>   { "display_name": "Asha K" }  →  200 (UserProfile)
// PATCH with a protected field, e.g. { "display_name":"X", "password_hash":"evil" }  →  422
// no token / bad token  →  401
```

`PATCH` accepts **only** `display_name`. Changing `email` through this endpoint
is intentionally not supported in Phase 3 (the owner's spec limits self-edit to
display name), so the duplicate-email-on-change case does not arise here.

### 9.7 Commands executed (from `backend/`)

```powershell
.venv\Scripts\python -m pip install argon2-cffi PyJWT email-validator
.venv\Scripts\python -m alembic revision --autogenerate -m "add password_hash to users"
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m pytest tests/ -q
$env:ROAMLARY_TEST_DATABASE_URL = "<roamlary_test URL>"   # value read from .env, never printed
.venv\Scripts\python -m pytest tests/test_postgres_integration.py -q
.venv\Scripts\python -m ruff check app/ tests/
.venv\Scripts\python -m ruff format app/ tests/
.venv\Scripts\python -m uvicorn app.main:app --port 8017   # live end-to-end run
```

### 9.8 Actual test results (2026-10-12, real output)

- **Full suite (SQLite + PostgreSQL integration enabled): `69 passed`** in 13.0s.
  Breakdown: 21 auth + 10 profile + the earlier Phase 1/2 tests + 7 PostgreSQL
  integration tests. Zero failures, zero skipped when the test DB is provided.
- **Offline (no `ROAMLARY_TEST_DATABASE_URL`):** the 4→7 integration tests
  self-skip; the rest pass.
- **Live end-to-end against real PostgreSQL (uvicorn, port 8017):** register →
  token issued; `GET /users/me` returned the profile with `password_hash`
  **absent**; `PATCH` updated the name; login again worked; **no token → 401**;
  **wrong password → 401**; **duplicate register → 409**; `/api/v1/health`
  still returned the exact contract. The throwaway user was deleted afterwards
  (dev DB left with 0 users).

### 9.9 Database changes & migration status

- **Model:** `users.password_hash` added (`String(255)`, nullable).
- **Migration:** `d9841015aec7` ("add password_hash to users"), autogenerated
  then **reviewed** — `upgrade()` adds the nullable column, `downgrade()`
  drops it. It does **not** touch or rewrite the applied initial migration
  `cc78d54068bb`.
- **Applied:** yes, `alembic upgrade head` ran against `roamlary_dev`;
  `alembic current` → `d9841015aec7 (head)`. Existing user rows are preserved
  (the column is nullable, so old rows simply get NULL). Dev DB confirmed empty
  of leaked test users afterwards.
- **PostgreSQL verified:** the 7 integration tests run against the disposable
  `roamlary_test` database (never the dev DB) and prove the real column
  exists, accepts NULL, and round-trips an Argon2id hash.

### 9.10 Security decisions & known limitations

Decisions: Argon2id hashing; constant-time verification (library-provided);
HS256 pinned; signature + expiry + required-claim checks; fail-closed on
missing secret; identity only from the token `sub`; identical login error for
unknown-vs-wrong password; `password_hash` absent from every public schema;
`extra="forbid"` on PATCH; `IntegrityError` handled safely (rollback + 409);
no password/token logging; no secrets in source control.

**This is a local hackathon prototype, NOT production-grade auth.** Still
missing / needs real security work before production: refresh tokens, password
reset, email verification, rate limiting/lockout, HTTPS, token revocation or a
denylist, Argon2 parameter tuning under load, and secret rotation. No roles or
permission system was added (out of scope).

### 9.11 Deviations from the approved plan

- Added `email-validator` (not named in the spec) — it is required by
  Pydantic's `EmailStr` for real email validation. Documented in §9.3.
- `PATCH /users/me` does **not** allow changing `email`. The spec said "normally
  display_name and any other profile fields justified by the current model";
  since the schema keeps `email` optional+unique and self-service email change
  introduces confirmation/ownership questions, it is deferred to a later phase
  with the owner's sign-off. Documented in §9.6.
- No `docs/api-contract.md` was created: no `docs/` contract file exists and the
  approved plan does not require one for Phase 3, so the auth contract was
  written into README.md and this report instead (per Task I's "only if it fits
  the current scope").

### 9.12 Phase completion checklist

| Requirement | Status |
|---|---|
| Registration + login work (local auth) | ✅ |
| Passwords securely hashed (Argon2id) | ✅ |
| JWTs signed (HS256) & validated (sig+exp) | ✅ |
| Protected profile endpoints work | ✅ |
| Unauthorized requests rejected (401/422/409) | ✅ |
| User-model change recorded in a new migration | ✅ (`d9841015aec7`) |
| Existing DB records preserved | ✅ (nullable column; dev DB verified) |
| Phase 1 & 2 functionality intact | ✅ (health contract re-verified live) |
| Tests + migration reported honestly | ✅ (69 passed; live E2E run) |
| README + this report updated | ✅ |
| Git status reviewed; no commits/pushes during the phase | ✅ (Phase 3 was later committed as `3d728ac` and pushed after the owner said "commit and push") |
| No later-phase workflows implemented | ✅ (see §9.13) |

### 9.13 Scope confirmation

Phase 3 implemented **no** Firebase authentication or linking, **no** password
reset, email verification, refresh tokens, OAuth/social login, roles or
advanced permissions, **no** trusted-contact / check-in / SOS / community-report
/ AI / notification endpoints, no background workers, no Flutter screens, and no
production deployment. Only local auth + the two `/users/me` profile routes were
added on top of the existing health + DB foundation.

**Recommended next step:** the owner reviews this phase (report + `git diff` on
`backend`) and, when satisfied, **assigns Phase 4** (trusted contacts & safety
check-ins). Phase 3 was committed as `3d728ac` and pushed to `origin/backend`
after the owner said "commit and push"; the owner-assigned audit & fix round
(§9.14) sits uncommitted in the working tree, exactly as the earlier phases
did before their approval.

### 9.14 Phase 3 audit & fix round (owner-assigned verification)

The owner assigned a fix-and-verify pass over Phase 3 *after* it was
committed (`3d728ac`). This section records what the audit found, what was
changed, and the actual results. Everything below is in the **uncommitted
working tree** on top of `3d728ac`.

#### 9.14.1 Audit method

Every claim in §9.3–§9.13 was re-checked against the actual code, the
applied database schema, and fresh test runs — not taken from the earlier
report text. Preflight re-verified: branch `backend`, HEAD `3d728ac`,
clean tree, migration history linear (`cc78d54068bb → d9841015aec7 head`)
against the dedicated development database `roamlary_dev` only.

#### 9.14.2 Findings and fixes

Plain language: the audit found the auth flow **worked** (no critical
security hole), but it identified four correctness/robustness gaps, one
timing side-channel, and several documentation contradictions. Each is
listed with the fix actually applied.

| # | Finding | Severity | Fix applied |
|---|---|---|---|
| 1 | `RegisterRequest`/`LoginRequest` used Pydantic's default (`extra="ignore"`), so a smuggled `password_hash`, `id`, or `firebase_uid` was silently dropped instead of rejected. `UserProfileUpdate` was already strict — register/login were inconsistently lenient. | Medium (spec requires strict schemas) | Added `model_config = ConfigDict(extra="forbid")` to both request schemas → any unknown field is now a **422** |
| 2 | **Timing side-channel:** login with an *unknown email* skipped Argon2 verification entirely, returning its 401 measurably faster than a wrong-password 401 → response time could reveal whether an account exists. | Low-Medium | Login now always runs one real Argon2 verification; for unknown emails it verifies against a dummy hash (`_DUMMY_PASSWORD_HASH`) so both paths cost the same. The dummy hash is generated once at import (~0.1 s startup). |
| 3 | Register created the database row **before** the fail-closed secret check ran, so a missing `JWT_SECRET_KEY` could leave a half-created, unusable account. | Low | New public `ensure_auth_configured()` in `security.py`; register now calls it **before any database write**, so 503 happens with no row created. |
| 4 | `PATCH /users/me` with an empty body (`{}`) still bumped `updated_at`, so the timestamp did not mean "last real change". | Low | `updated_at` is now bumped only when `display_name` actually changed; `{}` is a valid no-op returning the profile unchanged. |
| 5 | Tests used the **real dev secret** from `.env` — not hermetic, and it exercised the actual signing key. | Low | New autouse fixture in `conftest.py` pins a fixed TEST-ONLY secret for every test (`TEST_JWT_SECRET`); the real `.env` secret is never used by tests. |
| 6 | `report.md` contradictions: Phase 3 still labeled "in progress"/"uncommitted" although committed as `3d728ac` and pushed; Phase 1/2 records lacked post-approval commit annotations; stale "Phase 1 scope" docstring in `config.py`. | Doc | Corrected in this round (§2, §3, §4, §7.8, §8.13, §9.13, §9.14, §10, §11 + `config.py` docstring). Historical commits were **annotated, never rewritten**. |

#### 9.14.3 New tests added (12)

| Test | Proves |
|---|---|
| `test_register_rejects_injected_internal_fields` | `password_hash`/`id`/`firebase_uid` in the register body → **422**, never stored |
| `test_login_rejects_extra_fields` | strict login schema → unknown fields are **422** |
| `test_register_race_duplicate_maps_to_409` | simulated concurrent duplicate (stale pre-check + real unique constraint) → **409**, no unhandled 500 |
| `test_login_unknown_email_still_runs_password_verification` | timing equalization: unknown email still performs one Argon2 verification |
| `test_token_missing_required_exp_claim_rejected` | correctly signed token without `exp` → **401** (required-claim validation) |
| `test_token_missing_required_sub_claim_rejected` | correctly signed token without `sub` → **401** |
| `test_token_with_non_uuid_sub_rejected` | signed token with a non-UUID `sub` → **401** |
| `test_sub_claim_cannot_be_swapped_to_impersonate` | re-signing another user's `sub` with any key the attacker has → **401**; the victim's real token still works |
| `test_missing_jwt_secret_blocks_token_issuance` | empty `JWT_SECRET_KEY` → register **and** login both return **503** |
| `test_missing_jwt_secret_blocks_token_verification` | empty secret → even a once-valid token is refused (**503**) |
| `test_missing_jwt_secret_does_not_create_account` | fail-closed happens **before** the DB write — no half-created account |
| `test_health_works_without_jwt_secret` | regression: `/health` stays **200** with auth unconfigured |

Plus profile hardening tests: `test_patch_me_empty_body_is_noop`,
`test_patch_me_real_change_bumps_updated_at`,
`test_patch_me_rejects_email_and_firebase_uid`.

#### 9.14.4 Actual test results (2026-10-12, this round)

- **Full suite (SQLite + PostgreSQL integration enabled): `84 passed`** in
  ~21 s (77 offline + 7 PostgreSQL integration). Zero failures, zero skipped.
- **Offline only (no `ROAMLARY_TEST_DATABASE_URL`): `77 passed`**, the 7
  integration tests self-skip.
- **Lint:** `ruff check app/ tests/` → *All checks passed*.
- **Format:** `ruff format --check app/ tests/` → *33 files already formatted*.
- **Live end-to-end (uvicorn, real PostgreSQL):** register → token issued;
  `GET /users/me` returned the profile with `password_hash` **absent**;
  `PATCH` updated the name; register with an injected `password_hash` →
  **422**; `/api/v1/health` returned the exact Phase 1 contract. Throwaway
  audit user deleted afterwards (dev DB left with 0 users).

#### 9.14.5 Migration & database status (re-verified)

No new migration was needed: `password_hash` already existed from
`d9841015aec7`. Re-verified against the dedicated dev database
`roamlary_dev`: `alembic current` → `d9841015aec7 (head)`; the
`users.password_hash` column is present and nullable (VARCHAR 255); no
records were dropped or altered. Integration tests again ran only against
the disposable `roamlary_test` database.

#### 9.14.6 Git state after this round

- HEAD is still `3d728ac` (Phase 3 commit) — **no commits, pushes, merges,
  resets, or branch changes were made in this audit round**, per the owner's
  rule. All audit changes sit in the working tree for review (`git diff`).
- `.env` and `.venv` remain gitignored; the frontend was not touched; a scan
  of changed files found only documentation placeholders, no real secrets.

#### 9.14.7 Deviations & remaining limitations

Deviations from the original Phase 3 plan: none in scope — this round only
hardened and corrected what Phase 3 already built. Known limitations are
unchanged and still real: **this is a local hackathon prototype, not
production-grade auth** — no refresh tokens, no password reset, no email
verification, no rate limiting/lockout, no HTTPS, no token revocation/denylist,
no secret rotation, and no roles/permissions. The dummy-hash timing fix
equalizes the two failure paths but does not make login constant-time in a
formal sense. Passing unit/integration tests is **not** a security audit or a
production-readiness claim.

## 10. Known limitations (current)

- No API CRUD endpoints yet — the tables exist but nothing exposes them over
  HTTP; only `GET /api/v1/health`, `POST /api/v1/auth/register`,
  `POST /api/v1/auth/login`, and `GET/PATCH /api/v1/users/me` are served.
- Authentication is a **local prototype**: Argon2id password hashing + HS256
  JWTs. No refresh tokens, password reset, email verification, rate limiting,
  or account recovery yet — all belong to later phases.
- No trusted contacts, check-ins, SOS workflow, community reports, AI, or
  notifications — those belong to later phases.
- Dev-grade CORS and configuration only; no HTTPS.
- Runs only on this laptop, local machine, port 8000.
- The `backend` branch is pushed to GitHub (`origin/backend`) through Phase 3
  (`3d728ac`). The Phase 3 audit-fix round (§9.14) is uncommitted in the
  working tree.
- Database lives in a Docker container; if that container's volume is removed,
  recreate the schema with `alembic upgrade head`.
- Frontend cannot integrate beyond the health + auth contract until Phase 9.

## 11. Pending tasks and next steps

1. Owner reviews the **Phase 3 audit & fix round** (§9.14 + `git diff` on
   `backend`).
2. Owner decides whether to commit the audit-fix round — the backend lead will
   not commit or push without explicit instruction.
3. Owner assigns Phase 4 (trusted contacts & safety check-ins).
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
