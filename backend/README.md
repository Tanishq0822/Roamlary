# Roamlary Backend

FastAPI backend for **Roamlary**, an AI-powered travel companion and personal
safety prototype (CODE X 3.0 hackathon).

> **Honesty note:** this is a local hackathon prototype. It does **not** connect
> to emergency services, real responders, SMS/push providers, or live AI.
> Those integrations belong to later phases and will only be documented as
> working after they are actually verified.

## Current scope (Phase 5 — SOS & emergency workflow, simulated)

Implemented now (on top of the Phase 1 foundation + Phase 2 database +
Phase 3 authentication + Phase 4 contacts/check-ins):

- Runnable FastAPI application with versioned routing (`/api/v1`)
- `GET /api/v1/health` liveness endpoint (documented contract below)
- Environment-based configuration (`.env` / environment variables)
- CORS configured for Flutter development origins
- Interactive API documentation (Swagger UI / ReDoc)
- **PostgreSQL persistence** via SQLAlchemy 2.x (engine + per-request sessions)
- **Five domain models**: `User`, `TrustedContact`, `CheckIn`, `SosEvent`,
  `CommunityReport` — with UUID keys, timestamps, CHECK constraints and
  `ON DELETE RESTRICT` foreign keys
- **Alembic migrations** (initial schema + `password_hash` column +
  Phase 4 contact/check-in columns & `cancelled` status +
  Phase 5 SOS description/location-timestamp/cancellation columns &
  `cancelled` status)
- **Local authentication**: `POST /auth/register`, `POST /auth/login`
  (Argon2id password hashing + HS256 JWT access tokens)
- **Protected profile endpoints**: `GET /users/me`, `PATCH /users/me`
- **Trusted contacts**: `POST/GET /trusted-contacts`,
  `GET/PATCH/DELETE /trusted-contacts/{contact_id}`
- **Safety check-ins**: `POST/GET /check-ins`,
  `GET/PATCH /check-ins/{checkin_id}`, `POST /check-ins/{checkin_id}/complete`
- **SOS incidents (simulated)**: `POST/GET /sos`,
  `GET /sos/{sos_id}`, `POST /sos/{sos_id}/cancel`, `POST /sos/{sos_id}/resolve`
- Automated test suite: **158 tests** (142 offline + 16 real-PostgreSQL
  integration; contacts + check-ins + SOS + auth + profiles + models +
  migrations)

**Intentionally NOT implemented yet** (assigned to later phases, do not expect
them to exist): Firebase Authentication, refresh tokens, password reset, email
verification, roles/permissions, community **report workflow endpoints**, AI
companion, notifications, **overdue-check-in alerts**, pagination, production
deployment. Phase 5 only *records* SOS incidents locally — it never contacts
emergency services, never messages a contact, and never shares a location.
Authentication here is a **local prototype** — it needs real security work
(HTTPS, rate limiting, token revocation) before any production claim.

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
| `JWT_SECRET_KEY` | Secret used to sign/verify access tokens (HS256). **Empty by default → auth returns 503 (fail-closed)** | *(empty)* |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes (short; no refresh tokens) | `60` |

> **Credentials:** the real `DATABASE_URL` (with the container password) and the
> real `JWT_SECRET_KEY` live only in `.env`, which is gitignored. `.env.example`
> holds placeholders. Never commit the real `.env`, and never paste the real URL
> or secret into chat, docs, or logs.

### Generating a safe JWT secret (never commit it)

Produce a random value locally and paste it into your `.env` as
`JWT_SECRET_KEY=...`. Do **not** use a guessable or reused string. On PowerShell:

```powershell
-join ((33..126) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
```

The empty default is deliberate: if the secret is missing, `create/decode_access_token`
refuse to run (503) rather than sign with a weak built-in value. The public
`/api/v1/health` endpoint still works with an empty secret.

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

## Authentication (local prototype)

Four endpoints. Register and login are public; the two `/users/me` routes need a
bearer token.

| Method + Path | Auth | Body | Success |
| --- | --- | --- | --- |
| `POST /api/v1/auth/register` | none | `display_name`, `email`, `password` | `201` → `{access_token, token_type}` |
| `POST /api/v1/auth/login` | none | `email`, `password` | `200` → `{access_token, token_type}` |
| `GET /api/v1/users/me` | Bearer | — | `200` → public profile |
| `PATCH /api/v1/users/me` | Bearer | `display_name` (only) | `200` → public profile |

**Public profile shape** (the only fields ever returned — never `password_hash`):

```json
{ "id": "…", "display_name": "Asha", "email": "asha@example.com",
  "created_at": "…", "updated_at": "…" }
```

Errors: duplicate email → `409`; wrong password **or** unknown email → `401`
(same message *and* similar response time, so accounts can't be enumerated);
missing/bad/expired token → `401`; unknown or protected fields in **any**
request body (`register`, `login`, `PATCH`) → `422` (all request schemas are
strict). Emails are normalized (trimmed + lowercased), so `Asha@Example.COM` and
`asha@example.com` are the same account.

### Try it in the Swagger UI

1. Start the server and open <http://127.0.0.1:8000/docs>.
2. Expand `POST /auth/register` → **Try it out** → fill `display_name`, `email`,
   `password` (min 8 chars) → **Execute**. Copy the `access_token` from the 201
   response.
3. Expand `GET /users/me` → **Try it out** → set **Value** to `Bearer <paste the token>`
   (or click **Authorize** at the top and paste the raw token) → **Execute**.
4. `PATCH /users/me` works the same way; send `{"display_name": "New Name"}`.

### Using the token from a client (high level)

Send it on every protected request as a header:
`Authorization: Bearer <access_token>`. Store it securely on-device (e.g. the
platform keystore/keychain), **not** in plain logs. The token expires after
`ACCESS_TOKEN_EXPIRE_MINUTES`; because there are **no refresh tokens**, the user
simply logs in again to get a new one. Real token storage is the frontend
workstream's job — no Flutter screens exist yet.

## Trusted contacts (Phase 4)

Five endpoints, **all requiring a bearer token**. Every contact belongs to
the user in the token — `user_id` is never read from the request body, and
request bodies are strict: sending `user_id`, `id`, or any unknown field is a
`422`.

| Method + Path | Auth | Body | Success |
| --- | --- | --- | --- |
| `POST /api/v1/trusted-contacts/` | Bearer | `name`, `phone` (required); `relationship`, `email` (optional) | `201` → contact |
| `GET /api/v1/trusted-contacts/` | Bearer | — | `200` → array (mine only, oldest first) |
| `GET /api/v1/trusted-contacts/{contact_id}` | Bearer | — | `200` → contact / `404` |
| `PATCH /api/v1/trusted-contacts/{contact_id}` | Bearer | any subset of the four fields | `200` → contact / `404` |
| `DELETE /api/v1/trusted-contacts/{contact_id}` | Bearer | — | `204` (no body) / `404` |

```json
POST /api/v1/trusted-contacts/
{ "name": "Asha", "phone": "+91 98765 43210",
  "relationship": "mother", "email": "asha@example.com" }

201 response — the only fields ever returned:
{ "id": "3f2a…", "user_id": "9c1d…", "name": "Asha",
  "phone": "+919876543210", "relationship": "mother",
  "email": "asha@example.com",
  "created_at": "2026-10-12T07:09:54Z", "updated_at": "2026-10-12T07:09:54Z" }
```

**Field rules**

- `name` — required, 1–80 chars, trimmed (blank → `422`).
- `phone` — required. Normalized before storage: spaces, dashes,
  parentheses, and dots are removed; a leading `+` is kept. What remains must
  be **7–15 digits**, optionally with `+`. **No country code is assumed or
  added** (Roamlary users travel): `"+1 (415) 555-2671"` stores as
  `+14155552671`, `"(415) 555-2671"` stores as `4155552671`.
- `email` — optional (a phone is enough); real format check, trimmed and
  lowercased. Send `null` on PATCH to clear it.
- `relationship` — optional, ≤50 chars free text (`mother`, `friend`, …);
  blank or `null` clears it.
- `PATCH` with `{}` is a valid no-op (`200`, `updated_at` unchanged).

**Ownership & errors:** `401` no/invalid/expired token · `422` invalid or
injected fields · `404` for a missing **or** another user's contact — the
response is byte-identical in both cases, so contact IDs can't be probed.
Deleting a contact never touches your account, your other contacts, or your
check-ins.

> Saving a contact stores a name and a number. **Nothing is sent, no one is
> notified, and no number is verified as reachable.**

## Safety check-ins (Phase 4)

Five endpoints, **all requiring a bearer token**, all scoped to the token's
user (same identical-`404` rule as contacts).

| Method + Path | Auth | Body | Success |
| --- | --- | --- | --- |
| `POST /api/v1/check-ins/` | Bearer | `note`, `due_at` (both optional) | `201` → check-in |
| `GET /api/v1/check-ins/` | Bearer | — (query `?status=` optional) | `200` → array (mine only, newest first) |
| `GET /api/v1/check-ins/{checkin_id}` | Bearer | — | `200` → check-in / `404` |
| `PATCH /api/v1/check-ins/{checkin_id}` | Bearer | `note`, `due_at`, `status` | `200` → check-in / `404` / `409` |
| `POST /api/v1/check-ins/{checkin_id}/complete` | Bearer | — | `200` → check-in / `404` / `409` |

```json
POST /api/v1/check-ins/
{ "note": "north trail hike", "due_at": "2026-10-12T18:30:00Z" }

201 response — the only fields ever returned:
{ "id": "7b9e…", "user_id": "9c1d…", "status": "pending",
  "note": "north trail hike", "due_at": "2026-10-12T18:30:00Z",
  "completed_at": null, "created_at": "…", "updated_at": "…" }
```

**Status values and allowed transitions**

```
pending ──▶ safe           (PATCH {"status":"safe"}  or  POST …/complete)
        ├──▶ needs_help    (PATCH {"status":"needs_help"})
        └──▶ cancelled     (PATCH {"status":"cancelled"})

safe / needs_help / expired / cancelled  →  terminal: no exits at all
```

- `status` always starts as **`pending`** — the client cannot choose it on
  create (and sending one is a `422`).
- Any other move — including setting the same status again, or trying to
  reactivate a finished check-in → **`409`** with a plain-language message.
  There is deliberately **no** reactivate transition; create a new check-in
  instead.
- `note` and `due_at` can be edited **only while `pending`**; once answered,
  the record is read-only (`409`).
- `expired` exists for a future phase's expiry job — **nothing sets it
  automatically today**.

**`POST …/complete` idempotency (safe for network retries)**

| Current state | Result |
| --- | --- |
| `pending` | → `safe`, `completed_at` = server clock now, `200` |
| already `safe` | `200`, unchanged — `completed_at` keeps the **first** completion time |
| `needs_help` / `cancelled` / `expired` | `409` (completing must never overwrite a `needs_help` answer) |

`completed_at` is always set by the server — there is no client-supplied
completion timestamp, and `cancelled` leaves it `null` (nothing completed).

**Timestamp format & timezone behaviour**

- Send ISO 8601 **with a timezone**: `2026-10-12T18:30:00Z` or
  `2026-10-12T18:30:00+05:30`. A naive value (no `Z`, no offset) → `422`.
- `due_at` must be in the **future** at create *and* update time (server
  UTC) — a past deadline → `422`, never silently accepted.
- Responses always return UTC (values end in `Z`).

**Filtering:** `GET /api/v1/check-ins/?status=pending` (or
`safe`/`needs_help`/`expired`/`cancelled`); an unknown value → `422`.

> **Safety boundary:** an overdue check-in is *not* proof of danger. Phase 4
> stores data only — it never notifies contacts, never triggers an SOS, and
> never contacts emergency services. Those behaviours belong to later phases.

## SOS incidents (Phase 5 — simulated)

Five endpoints, **all requiring a bearer token**, all scoped to the token's
user (same identical-`404` rule as contacts and check-ins). Note the paths
have **no trailing slash** (`/sos`, per the Phase 5 spec; a trailing-slash
request is redirected by FastAPI).

| Method + Path | Auth | Body | Success |
| --- | --- | --- | --- |
| `POST /api/v1/sos` | Bearer | `description`, `latitude`, `longitude` (all optional) | `201` → incident |
| `GET /api/v1/sos` | Bearer | — | `200` → array (mine only, newest first) |
| `GET /api/v1/sos/{sos_id}` | Bearer | — | `200` → incident / `404` |
| `POST /api/v1/sos/{sos_id}/cancel` | Bearer | — (no body) | `200` → incident / `404` / `409` |
| `POST /api/v1/sos/{sos_id}/resolve` | Bearer | — (no body) | `200` → incident / `404` / `409` |

```json
POST /api/v1/sos
{ "description": "flat tyre on highway 7", "latitude": 28.6139, "longitude": 77.2090 }

201 response — the only fields ever returned:
{ "id": "a41c…", "user_id": "9c1d…", "status": "active",
  "description": "flat tyre on highway 7", "latitude": 28.6139,
  "longitude": 77.2090, "location_recorded_at": "2026-10-12T11:05:12Z",
  "created_at": "…", "updated_at": "…",
  "cancelled_at": null, "resolved_at": null }
```

**Coordinate rules**

- `latitude` and `longitude` must be provided **together** — one without the
  other → `422` (a single coordinate locates nothing).
- Ranges: latitude `-90…90`, longitude `-180…180`; outside → `422`.
- Both omitted → no location stored; `location_recorded_at` stays `null`.
- When coordinates are given, `location_recorded_at` is stamped with the
  **server clock at activation** — there is no client field for it.
- The server never obtains or guesses a location, and a user's location is
  never exposed to any other user (every query is owner-filtered).

**Status values and allowed transitions**

```
active ──▶ cancelled    (POST …/cancel)
      └──▶ resolved     (POST …/resolve)

cancelled / resolved  →  terminal: no exits at all
```

- `status` always starts **`active`** — the client cannot choose it (sending
  one is a `422`).
- `cancelled_at` / `resolved_at` are set by the **server clock** on the
  transition; the cancel/resolve routes accept **no body**, so a client
  timestamp can never be applied.
- Any move except `active → cancelled/resolved` — including repeating a
  transition, or crossing between the two terminal states → **`409`** with a
  plain-language message, and the record stays exactly as it was.
- Unlike check-in `/complete` (idempotent by design), SOS repeats always
  conflict: a terminal incident is a closed record whose first timestamp is
  never rewritten.
- `acknowledged` / `false_alarm` exist in the Phase 2 schema for a future
  phase but are **unreachable now** (no responder system exists).

**Validation:** `description` optional, 1–500 chars; a blank/whitespace-only
description → `422` (provide text or omit the field). `user_id`, `status`,
`id`, `created_at`, `updated_at`, `cancelled_at`, `resolved_at`,
`location_recorded_at` are server-controlled — sending any of them → `422`.
Responses always return UTC timestamps.

> **Safety boundary:** activating an SOS **only writes a row** in this
> prototype. It does **not** contact police, ambulance, or any emergency
> number, does **not** notify trusted contacts or nearby users, and shares
> no location with anyone. Do not present this as an emergency-response
> system; real delivery needs integrations and safeguards from later phases.

## Migrations (Alembic)

Alembic creates and evolves the schema. The migration files live in
`alembic/versions/` and are committed as source code.

Applied migrations on `roamlary_dev`:
- `cc78d54068bb` — initial schema (Phase 2): the five tables.
- `d9841015aec7` — adds the nullable `users.password_hash` column (Phase 3).
- `ccd362671e07` — Phase 4: adds nullable `trusted_contacts.relationship`
  (VARCHAR 50) and `check_ins.note` (VARCHAR 500), and allows the
  `cancelled` value in the `check_ins` status CHECK constraint.
  Round-trip verified (`upgrade` → `downgrade` → `upgrade` reproduced the
  identical schema) **when no `cancelled` check-ins exist**. If any
  `cancelled` check-ins exist, `downgrade` deliberately **refuses** with an
  actionable error *before* touching the schema or data (cancelled records
  need an explicit data-handling decision first — see Common problems).
  `alembic current` → `ccd362671e07 (head)`.
- `0dd8995649b4` — Phase 5: adds nullable `sos_events.description`
  (VARCHAR 500), `sos_events.location_recorded_at`, and
  `sos_events.cancelled_at` (timezone-aware), and allows the `cancelled`
  value in the `sos_events` status CHECK constraint. Same downgrade rule
  as Phase 4: round-trip verified when no `cancelled` SOS incidents
  exist; if any exist, `downgrade` deliberately **refuses** before
  touching anything (data-safety guard — see Common problems).
  `alembic current` → `0dd8995649b4 (head)`.

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

- **Offline unit tests** (142) — use an in-memory SQLite database and the
  FastAPI `TestClient`. No PostgreSQL, no network. They prove model
  behaviour, auth flows (register/login/JWT/profile), contact & check-in
  endpoint contracts (ownership, transitions, timestamps), SOS endpoint
  contracts (activation validation, ownership, lifecycle), fail-closed
  behaviour, route contracts, and the migration chain (including the
  Phase 4 and Phase 5 downgrade data-safety guards). They always run with
  a fixed TEST-ONLY JWT secret (never the real `.env` value).
- **PostgreSQL integration tests** (16) — run against a **disposable**
  database and prove real PostgreSQL behaviour (native `uuid` columns, CHECK
  constraint enforcement — including the Phase 4/5 `cancelled` values and
  new columns — timezone-aware timestamps, the `password_hash` column, and
  both downgrade guards: refused with `cancelled` rows, allowed without
  them). They are **skipped** unless you point them at a throwaway database.

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
| Auth endpoints return `503` | `JWT_SECRET_KEY` is empty (auth fails closed by design) | Generate a secret (see Environment config) and set `JWT_SECRET_KEY=` in `.env`, restart |
| `401` on `/users/me` right after login | Token missing/expired, or sent without the `Bearer ` prefix | Send `Authorization: Bearer <token>`; re-login if it expired (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| `401 Invalid email or password` when the account exists | Wrong password — or the account has no `password_hash` (Firebase-only) | Confirm the password; local login only works for accounts that set a password at register |
| `409` on register | That email already has an account | Log in instead, or use a different email |
| `422` on register or login | Body contains a field the strict schema doesn't allow (e.g. `password_hash`, `id`, `role`) | Send only the documented fields: register → `display_name`, `email`, `password`; login → `email`, `password` |
| `422` on `PATCH /users/me` | Body contains a protected/unknown field | Send **only** `display_name`; `id`, `email`, `password_hash`, `firebase_uid` are not editable here |
| `422` on contact create/update | Missing `name`/`phone`, bad email, overlong field, or a phone that isn't 7–15 digits after cleanup — or an injected `user_id`/`id` | Send only `name`, `phone`, `relationship`, `email`; phone may contain spaces/dashes/parentheses but must be 7–15 digits (optionally starting `+`) |
| `422` on check-in create/update with `due_at` | Timestamp has no timezone, is malformed, or is already in the past | Send ISO 8601 **with** `Z`/offset (e.g. `2026-10-12T18:30:00Z`) and a future moment |
| `409` on `PATCH /check-ins/{id}` | Illegal status move (e.g. reactivating `safe`/`cancelled`), same-status set, or editing `note`/`due_at` on an answered check-in | Only `pending → safe/needs_help/cancelled` is allowed; answered check-ins are read-only |
| `409` on `POST /check-ins/{id}/complete` | The check-in is `needs_help` or `cancelled` (already answered another way) | Only `pending` can be completed; repeats on `safe` return `200` unchanged |
| `404` on someone else's contact/check-in | Deliberate: foreign IDs return the same `404` as missing ones (no ownership probing) | Use only your own records — list them first (`GET /trusted-contacts/`, `GET /check-ins/`) |
| Pydantic error mentioning `email-validator` | `EmailStr` needs the `email-validator` package | Re-run `.venv\Scripts\python -m pip install -e ".[dev]"` |
| `RuntimeError: Refusing to downgrade migration ccd362671e07 …` | At least one check-in has `status='cancelled'`, which the older constraint would reject | Intentional data-safety guard: nothing was changed. Decide what to do with those rows (delete them, or move them to an allowed status), then re-run the downgrade — or keep the Phase 4 schema |
| `RuntimeError: Refusing to downgrade migration 0dd8995649b4 …` | At least one SOS incident has `status='cancelled'`, which the older constraint would reject | Intentional data-safety guard: nothing was changed. Decide what to do with those rows (delete them, or move them to an allowed status), then re-run the downgrade — or keep the Phase 5 schema |
| `409` on `POST /sos/{id}/cancel` or `…/resolve` | The incident is already `cancelled` or `resolved` (terminal states are locked; repeats always conflict — SOS transitions are deliberately not idempotent) | Read the incident first (`GET /sos/{id}`); only `active` incidents can transition |
| `422` on `POST /sos` with coordinates | Only one of `latitude`/`longitude` sent, a value out of range, a blank `description`, or an injected server-controlled field (`user_id`, `status`, `cancelled_at`, …) | Send both coordinates together (lat −90…90, lon −180…180), non-blank `description` or none, and only the documented fields |

## Development log

Every task, file-by-file explanations, actual test outputs, and decisions live
in [`report.md`](report.md).
