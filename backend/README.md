# Roamlary Backend

FastAPI backend for **Roamlary**, an AI-powered travel companion and personal
safety prototype (CODE X 3.0 hackathon).

> **Honesty note:** this is a local hackathon prototype. It does **not** connect
> to emergency services, real responders, SMS/push providers, or live AI.
> Those integrations belong to later phases and will only be documented as
> working after they are actually verified.

## Current scope (Phases 6–8: reports, identity verification & social access, travel buddies & discovery, stranger chat/blocking/sessions)

Implemented now (on top of the Phase 1 foundation + Phase 2 database +
Phase 3 authentication + Phase 4 contacts/check-ins + Phase 5 SOS +
Phase 6 reports + Phase 6 second assignment identity verification +
Phase 7 travel buddies + Phase 8 messaging):

- Runnable FastAPI application with versioned routing (`/api/v1`)
- `GET /api/v1/health` liveness endpoint (documented contract below)
- Environment-based configuration (`.env` / environment variables)
- CORS configured for Flutter development origins
- Interactive API documentation (Swagger UI / ReDoc)
- **PostgreSQL persistence** via SQLAlchemy 2.x (engine + per-request sessions)
- **Fifteen domain models**: `User`, `TrustedContact`, `CheckIn`, `SosEvent`,
  `CommunityReport`, `IdentityVerification`, `AppSetting`, `SettingChange`,
  `TravelProfile`, `TravelPlan`, `TravelPartnerRequest`,
  `UserBlock`, `Conversation`, `ChatMessage`, `AuthSession` —
  with UUID keys, timestamps, CHECK constraints and
  `ON DELETE RESTRICT` foreign keys
- **Alembic migrations** (initial schema + `password_hash` column +
  Phase 4 contact/check-in columns & `cancelled` status +
  Phase 5 SOS description/location-timestamp/cancellation columns &
  `cancelled` status + Phase 6 `community_reports.category` CHECK
  constraint + Phase 6 second assignment `users.verification_status`/
  `users.role` columns and the verification/policy/audit tables +
  Phase 7 travel profile/plan/partner-request tables +
  Phase 8 block/conversation/message/session tables, `users.token_version`,
  and the travel canonical-pair race-fix columns/index)
- **Local authentication**: `POST /auth/register`, `POST /auth/login`
  (Argon2id password hashing + HS256 JWT access tokens)
- **Protected profile endpoints**: `GET /users/me`, `PATCH /users/me`
- **Trusted contacts**: `POST/GET /trusted-contacts`,
  `GET/PATCH/DELETE /trusted-contacts/{contact_id}`
- **Safety check-ins**: `POST/GET /check-ins`,
  `GET/PATCH /check-ins/{checkin_id}`, `POST /check-ins/{checkin_id}/complete`
- **SOS incidents (simulated)**: `POST/GET /sos`,
  `GET /sos/{sos_id}`, `POST /sos/{sos_id}/cancel`, `POST /sos/{sos_id}/resolve`
- **Community safety reports**: `POST /reports`, `GET /reports`,
  `GET /reports/nearby`, `GET /reports/{report_id}` — with category/status
  filters, bounded offset/limit pagination, and a haversine radius search
- **Identity verification (manual review)**: `GET /verification/status`,
  `POST /verification/requests` — account states
  `unverified → pending → verified/rejected`; clients can never set any
  state themselves
- **Owner-only admin**: `GET /admin/verification-requests` (review queue),
  `POST /admin/verification-requests/{id}/approve|reject`,
  `GET/PATCH /admin/policy/social-verification` (audited + rate limited)
- **Server-side social gate**: `require_owner` / `require_verified_user`
  dependencies — reused unchanged by the travel-buddy surface below
- **Travel buddies & social discovery (Phase 7)**: `POST/GET/PATCH/DELETE
  /travel-profile/me` (one discoverable profile per account),
  `POST/GET /travel-plans` + `GET/PATCH/DELETE /travel-plans/{plan_id}`,
  `GET /travel-buddies/discover` (eligibility-aware, scored, paginated),
  `GET /travel-buddies/{user_id}` (limited public profile),
  `POST/GET /travel-buddies/requests` +
  `GET /travel-buddies/requests/{request_id}` +
  `POST /travel-buddies/requests/{request_id}/accept|reject|cancel`, and
  the real `GET /social/discovery` (broad verified-user feed)
- **Stranger chat (Phase 8)**: `POST/GET /chat/requests` +
  `GET /chat/requests/{id}` + `POST .../accept|reject|cancel`,
  `GET /chat/conversations` + `GET /chat/conversations/{id}`,
  `GET/POST /chat/conversations/{id}/messages` (bounded pagination),
  `DELETE /chat/messages/{id}` (sender-only soft delete) — one row per
  unordered pair, text-only, no auto-chat from travel partners
- **Blocking (Phase 8)**: `POST/GET /blocks`, `DELETE /blocks/{id}` —
  stops both directions of messaging/requests/discovery; history stays
  readable; reachable while unverified
- **Session security (Phase 8)**: every login mints a trackable session
  (`GET /auth/sessions`, `POST /auth/logout`,
  `POST /auth/sessions/{id}/revoke`, `POST /auth/sessions/revoke-others`,
  `POST /auth/revoke-all`) with immediate revocation enforcement
- **Owner provisioning CLI**: `python -m app.cli make-owner <email>` (the
  only path that grants the `owner` role)
- Automated test suite: **406 tests** (369 offline + 37 real-PostgreSQL
  integration; contacts + check-ins + SOS + reports + verification +
  admin/policy + auth + profiles + travel buddies + chat + blocks +
  sessions + models + migrations)

**Intentionally NOT implemented yet** (assigned to later phases, do not expect
them to exist): Firebase Authentication, refresh tokens, password reset, email
verification, report **moderation/approval workflow** (the
`approved`/`rejected` states are reserved — no endpoint can set them yet), AI
companion, notifications, **overdue-check-in alerts**, pagination on the
non-report/non-travel/non-chat endpoints, **group chat** and trip events
(one-to-one text chat exists since Phase 8; the two users are never
connected by any other channel), a real
identity-verification provider (verification here is **manual review only** —
no Aadhaar/ID documents or sensitive identity data are collected, stored, or
displayed anywhere), production deployment. Phase 5 only *records* SOS
incidents locally — it never contacts emergency services, never messages a
contact, and never shares a location. Phase 6 only *stores and searches*
reports — filing one sends nothing to anyone. Phase 7 only *matches and
requests* — accepting a travel-partner request creates a connection row,
never notifies anyone, never opens a chat, and never implies either user
is safe. Phase 8 adds one-to-one text chat behind an explicit
ask-and-accept, but still sends no notifications, opens no group chats,
and never claims anyone is safe. Authentication
here is a **local prototype** — it needs real security work (HTTPS, rate
limiting, token revocation) before any production claim. Account/safety
workflow endpoints (trusted contacts, check-ins, SOS, account profile,
travel profile & plans) stay reachable while
**unverified** — incomplete verification must never lock anyone out of
safety tools.

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

### The fifteen tables

| Table | Purpose | Key columns |
| --- | --- | --- |
| `users` | App account / profile | `id` (UUID PK), `firebase_uid` (optional, unique), `display_name`, `email` (optional, unique), `verification_status` (unverified/pending/verified/rejected), `role` (user/owner) |
| `trusted_contacts` | People to notify in an SOS | `user_id` (FK→users), `name`, `phone`, `email` |
| `check_ins` | "Ping me by time T" promises | `user_id` (FK), `status`, `due_at`, `completed_at` |
| `sos_events` | **Simulated** emergency incidents | `user_id` (FK), `status`, `latitude`/`longitude`, `resolved_at` |
| `community_reports` | Crowd-sourced safety notes | `user_id` (FK), `category` (6-value set, Phase 6), `description`, `latitude`/`longitude`, `status` |
| `identity_verifications` | One row per verification **request** (history) | `user_id` (FK), `status` (pending/approved/rejected), `applicant_note`, `review_note`, `reviewed_at`, `reviewed_by` (FK) |
| `app_settings` | Runtime configuration (one key today: `social_requires_verification`) | `key` (unique), `value`, `updated_by` (FK) |
| `setting_changes` | Append-only audit of policy changes | `setting_key`, `old_value`, `new_value`, `changed_by` (FK) |
| `travel_profiles` | One travel identity per account (Phase 7) | `user_id` (FK, **unique**), `travel_nickname`, `languages`/`travel_styles`/`interests` (JSON lists), `group_size_pref` (CHECK 2–12), `discoverable` |
| `travel_plans` | One trip intention per row (Phase 7) | `user_id` (FK), `destination` + `destination_normalized`, `region` + `region_normalized`, `start_date`/`end_date` (CHECK end ≥ start), `flexible_dates`, `status` (active/paused/completed), `visibility` (private/discoverable) |
| `travel_partner_requests` | "A wants to travel with B" (Phase 7) | `requester_id`/`recipient_id` (FKs, CHECK ≠), `plan_id` (FK→travel_plans, nullable, RESTRICT), `status` (pending/accepted/rejected/cancelled), per-direction partial UNIQUE pending indexes + Phase 8 canonical-pair pending UNIQUE index |
| `user_blocks` | "Blocker wants nothing from blocked" (Phase 8) | `blocker_id`/`blocked_id` (FKs, CHECK ≠, UNIQUE pair) |
| `conversations` | One messaging relationship per unordered user pair (Phase 8) | `user_low_id`/`user_high_id` (canonical, UNIQUE pair, CHECK ≠), `status` (pending/accepted/rejected/cancelled), `requested_by` (FK), `responded_at` |
| `messages` | One text message (Phase 8) | `conversation_id` (FK), `sender_id` (FK), `body` (text), `is_deleted` + `deleted_at` (soft delete) |
| `auth_sessions` | One login session per login (Phase 8) | `user_id` (FK), `label` (optional), `revoked_at` (NULL = active) |

All children use **`ON DELETE RESTRICT`**: deleting a user who still has safety
records is blocked at the database level, so safety history can never vanish by
accident. Status columns are protected by CHECK constraints, report `category`
is a closed 6-value set enforced by a CHECK constraint (Phase 6), and lat/long
are range-guarded (−90..90 / −180..180). The two `users` verification columns
are NOT NULL with CHECK-protected value sets and secure server-side defaults
(`unverified`, `user`). Travel status/visibility/request columns are CHECK-
protected sets (Phase 7); deleting a plan referenced by a partner request is
blocked (RESTRICT) so request history keeps pointing at a real trip.
`users.token_version` (Phase 8) is a NOT NULL integer defaulting to 0 for
revocation; conversation/block/message columns carry the same CHECK +
RESTRICT + uniqueness discipline as the travel tables.

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
strict — `role` and `verification_status` are protected too; only the
server-side CLI and owner review can ever change them). Emails are
normalized (trimmed + lowercased), so `Asha@Example.COM` and
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

## Community safety reports (Phase 6)

One traveller's observation about a **place** — "dark street behind the
station" — filed by an authenticated user and searchable by the community.

| Method & path | Purpose | Auth | Success |
| --- | --- | --- | --- |
| `POST /api/v1/reports` | File a report (created as `pending`) | Bearer | `201` |
| `GET /api/v1/reports` | List visible reports, newest first (filters + pagination) | Bearer | `200` |
| `GET /api/v1/reports/nearby` | Reports within `radius_m` meters of a position, nearest first | Bearer | `200` |
| `GET /api/v1/reports/{report_id}` | One visible report | Bearer | `200` / `404` |

**Create** — only these four fields are accepted (`422` on anything else):

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/reports `
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" `
  -d '{"category":"poor_lighting","description":"dark street behind the station",
       "latitude":28.6139,"longitude":77.2090}'
```

```json
{
  "id": "3f6a…", "category": "poor_lighting", "status": "pending",
  "description": "dark street behind the station",
  "latitude": 28.6139, "longitude": 77.2090,
  "created_at": "2026-10-12T14:03:11Z", "updated_at": "2026-10-12T14:03:11Z"
}
```

- **Categories (closed set):** `unsafe_area`, `harassment`,
  `suspicious_activity`, `road_hazard`, `poor_lighting`, `other`.
  Unknown values → `422` at the API **and** a database CHECK constraint.
- **Coordinates are required** (the feature is location-based): lat
  −90…90, lon −180…180, both or neither (both are always sent).
- **Description** required, trimmed, 1–500 chars; blank → `422`.
- **No `user_id` in responses.** The submitter is stored in the table for
  accountability, but reports are about places, not people — no email,
  phone, or identity field can appear in any report response.
- `user_id`, `status`, `id`, `created_at`, `updated_at` are
  server-controlled — sending any of them → `422`.

**Status & visibility (read this before trusting a report):**

- Every report is created **`pending`** — an **unverified submission**
  (the *content* is not verified truth, regardless of whether the
  author's *account* has since passed identity verification). Filing one
  proves nothing about the place.
- **No moderation exists yet**: nothing can set `approved` or `rejected`,
  and no endpoint accepts a status — not even the owner (the Phase 6
  second assignment added roles, but **no report-moderation endpoint**).
  `approved`/`rejected` are reserved for a future moderation phase.
- Public reads return everything **except** `status='rejected'` (hidden);
  a rejected report's ID returns the same `404` as one that never
  existed. Because `status` travels in every response, clients can always
  distinguish `pending` (unverified) from `approved` (moderated).
- Reports have **no owner lifecycle actions**: no `PATCH`, no `DELETE`,
  no status transitions — the status column belongs to the future
  moderation system, not the submitter.

**List filters & pagination** (first paginated endpoint in this API):

- `?category=<one of the six>` and `?status=pending|approved` (optional;
  `status=rejected` → `422` — rejected is hidden, not filterable).
- `?offset=` (≥ 0, default 0), `?limit=` (1–100, default 20); stable order
  `created_at DESC, id DESC`. Responses are plain JSON arrays, like every
  other list endpoint.

**Nearby search** — `GET /api/v1/reports/nearby`:

- Required: `latitude` (−90…90), `longitude` (−180…180), `radius_m`
  (**meters**, `0 < radius_m ≤ 50000` i.e. max 50 km). Optional:
  `category`, `offset`, `limit` (same bounds as the list).
- **Method: a plain SQL haversine distance query** (Earth radius
  6,371,000 m), **not** PostGIS and **not** a geospatial index — adding
  that infrastructure was not justified for a hackathon prototype. The
  formula uses trig of the half-differences, so it wraps correctly across
  the antimeridian and stays accurate at high latitudes (no flat-map
  approximation). Practical limitations: it **scans the whole table**
  (O(n), fine for thousands of rows, revisit before real traffic), has no
  index support, is accurate to well under 1% at city scale (spherical
  vs. ellipsoidal Earth), and rows with `NULL` coordinates are skipped.
- Rejected reports are excluded, ordering is nearest-first (stable ties
  by `created_at DESC, id DESC`), results are paginated and capped at 100.

```powershell
# Reports within 2 km of a map position (radius unit is METERS)
curl "http://127.0.0.1:8000/api/v1/reports/nearby?latitude=28.61&longitude=77.20&radius_m=2000" `
  -H "Authorization: Bearer <token>"
```

> **Safety boundary:** a report is an **opinion**, not verified truth —
> the API never claims a place is dangerous or safe. Filing one sends
> nothing to anyone: no notifications, no emergency services, no
> nearby-user alerts, no moderation. Reports are read-only public content
> for authenticated users in this phase.

## Identity verification & social gate (Phase 6 second assignment)

This phase adds a **manual-review identity-verification workflow**, an
**owner role**, and a **server-side gate** that blocks unverified accounts
from social features. It deliberately collects **no identity documents** —
no Aadhaar, no ID numbers, no scans — only an optional short note for the
reviewer.

### Account states and who may change them

| From | To | Who / what triggers it |
| --- | --- | --- |
| `unverified` | `pending` | the account holder submits `POST /verification/requests` |
| `rejected` | `pending` | the account holder submits again (always allowed) |
| `pending` | `verified` | an **owner** approves the request |
| `pending` | `rejected` | an **owner** rejects the request |

There is **no other transition**: no request body, profile field, header,
registration value, or policy change can set any of these states
(injected `role`/`verification_status` values → `422`). Approving your own
request is refused even for the owner (`409`).

### Endpoints

| Method + path | Purpose | Success / errors |
| --- | --- | --- |
| `GET /api/v1/verification/status` | The caller's OWN status + role + live policy + latest request | `200` · `401` |
| `POST /api/v1/verification/requests` | Submit a request (optional `{"note": "≤200 chars"}`) | `201` · `401` · `409` already pending/verified · `422` |
| `GET /api/v1/admin/verification-requests` | Review queue, oldest first; `?status=`, `?offset=`, `?limit=` | `200` · `401` · `403` not owner · `422` |
| `POST /api/v1/admin/verification-requests/{id}/approve` | Approve → applicant `verified` (optional `{"review_note": "≤200 chars"}`) | `200` · `401` · `403` · `404` · `409` not pending / own request · `422` |
| `POST /api/v1/admin/verification-requests/{id}/reject` | Reject → applicant `rejected` (same errors) | `200` · `401` · `403` · `404` · `409` · `422` |
| `GET /api/v1/admin/policy/social-verification` | Read the effective policy | `200` · `401` · `403` |
| `PATCH /api/v1/admin/policy/social-verification` | Change it (`{"requires_verification": true\|false}`) | `200` · `401` · `403` · `422` · `429` rate limit |
| `GET /api/v1/social/discovery` | Broad verified-user feed (real since Phase 7 — see the "Travel buddies" section) | `200` · `401` · `403` |

Typical flow:

```text
POST /api/v1/verification/requests     (applicant, no body or {"note": "..."})
→ 201 { "id": "…", "status": "pending", "applicant_note": "…",
        "review_note": null, "reviewed_at": null,
        "created_at": "2026-10-12T17:40:02Z" }

GET  /api/v1/admin/verification-requests?status=pending   (owner)
→ 200 [ { …, "user_id": "…", "display_name": "Live Applicant",
          "status": "pending", … } ]

POST /api/v1/admin/verification-requests/{id}/approve     (owner)
→ 200 { …, "status": "approved", "reviewed_by": "<owner user id>", … }
   (the applicant's account is now verification_status="verified")

GET  /api/v1/social/discovery           (applicant)
→ 200 { "profiles": [ …limited public travel profiles, at most 10… ],
        "message": "Compatibility scores are a deterministic ranking …
        not a guarantee that anyone is safe …" }
```

### The gate (fail-closed by design)

`GET /social/discovery` is protected by `require_verified_user`:

1. No/invalid token → `401`.
2. The **policy is read live from the database on every request** — if the
   setting row is missing, corrupt, or unreadable, the answer is treated as
   `true` ("verification required"). A broken read can never open the gate.
3. Policy `true` and status ≠ `verified` → `403` with a status-specific,
   actionable message (e.g. *"Your status is 'pending': your request is
   under review."*).
4. Policy `false` (owner opened it during development) → any authenticated
   account passes.

**Kept open on purpose while unverified:** profile (`/users/me`),
trusted contacts, check-ins, SOS, reports, and the verification routes
themselves — incomplete verification must never lock anyone out of safety
tools. `require_owner` (admin routes) demands an exact `owner` role match;
an unknown/corrupt role is denied, never elevated.

### Owner provisioning (the only path)

```powershell
# run on the server, from backend/ — grants `owner` to an existing account
.venv\Scripts\python -m app.cli make-owner someone@example.com
# → OK: someone@example.com now has role=owner.   (exit code 0)
# → FAILED: no account with that email            (exit code 1)
```

Registration always creates `role="user"`; no API field, header, or body can
change a role. The command prints only the email + result — never the
database URL, passwords, or tokens.

### Policy management (owner only)

- `GET` reports the effective value (`requires_verification`) plus
  `updated_at`/`updated_by`.
- `PATCH {"requires_verification": false}` flips the gate off immediately
  (no restart, no token change). Every accepted change appends an audit row
  to `setting_changes`: **who, when, old value, new value**; a no-op write
  appends nothing; a change never alters anyone's verification status or
  past review history.
- At most **5 policy changes per hour per owner** (in-process counter) —
  the 6th returns `429`.

> **Boundaries:** verification is *manual review only* (no identity
> provider, no documents, no email notifications — none are claimed to
> work). With a single owner, the owner's own account can never be
> API-approved (self-review is refused), so the owner stays `unverified`
> through the API unless a second reviewer exists or the server operator
> changes the row deliberately. The gate itself now guards the real
> travel-buddy surface (Phase 7, next section) in addition to
> `/social/discovery`.

## Travel buddies & discovery (Phase 7)

Two users can describe how they travel, publish trip plans, find compatible
travellers, and exchange travel-partner requests — with **no AI, no external
matching service, and no messaging**: everything is arithmetic over data the
backend already stores, and every rule is written down below and in
`app/core/matching.py`.

### The two data layers

- **Travel profile** (`/travel-profile/me`) — one row per account: optional
  nickname, short bio, home region, and three preference lists
  (`languages`, `travel_styles`, `interests` — closed sets for styles and
  interests, free-form but length-limited languages), an optional group-size
  preference (2–12), and a `discoverable` switch that **defaults to
  hidden**. No identity documents, no precise location, nothing sensitive.
- **Travel plan** (`/travel-plans`) — one row per trip intention:
  destination (free text, normalized server-side for matching), optional
  region, start/end dates (end ≥ start enforced), `flexible_dates`,
  `status` (active/paused/completed), and `visibility`
  (private/discoverable, defaults to private). Plans whose `end_date` is
  in the past are excluded from discovery **at read time** (there is no
  background job).

### Endpoints

| Method + path | Purpose | Success / errors |
| --- | --- | --- |
| `GET /api/v1/travel-profile/me` | Your travel profile (+ `completion` hints) | `200` · `401` · `404` no profile yet (actionable message) |
| `POST /api/v1/travel-profile/me` | Create it (`discoverable` defaults to `false`) | `201` · `401` · `409` already exists · `422` |
| `PATCH /api/v1/travel-profile/me` | Partial update (explicit `null` clears, `[]` empties) | `200` · `401` · `404` · `422` |
| `DELETE /api/v1/travel-profile/me` | Remove your profile (your plans are NOT touched) | `204` · `401` · `404` |
| `POST /api/v1/travel-plans/` | Publish a plan (`private` by default) | `201` · `401` · `422` |
| `GET /api/v1/travel-plans/` | Your plans (active first, newest first) | `200` · `401` |
| `GET /api/v1/travel-plans/{plan_id}` | Read one plan (404 if missing **or** not yours) | `200` · `401` · `404` |
| `PATCH /api/v1/travel-plans/{plan_id}` | Edit a plan (date edits are re-validated together) | `200` · `401` · `404` · `409` · `422` |
| `DELETE /api/v1/travel-plans/{plan_id}` | Delete a plan | `204` · `401` · `404` · `409` still referenced by a request |
| `GET /api/v1/travel-buddies/discover` | Eligible, scored candidates (`?destination=`, `?region=`, `?start_date=`, `?end_date=`, `?interests=`, `?travel_style=`, `?language=`, `?min_score=`, `?offset=`, `?limit=` 1–100) | `200` · `401` · `403` · `422` |
| `GET /api/v1/travel-buddies/{user_id}` | Limited public travel profile of one user | `200` · `401` · `403` · `404` not discoverable/doesn't exist |
| `POST /api/v1/travel-buddies/requests` | Ask a discovered user to travel together (`{"recipient_id": "…", "plan_id": "…"}` — `plan_id` optional, must be the RECIPIENT's public plan) | `201` · `401` · `403` · `404` recipient not eligible · `409` duplicate · `422` self/invalid · `429` rate limit |
| `GET /api/v1/travel-buddies/requests?direction=incoming\|outgoing` | Your request history (`?status=` filter, offset/limit) | `200` · `401` · `422` |
| `GET /api/v1/travel-buddies/requests/{request_id}` | Read one request (404 unless you are a party) | `200` · `401` · `404` |
| `POST /api/v1/travel-buddies/requests/{request_id}/accept` | Recipient accepts (`pending → accepted`) | `200` · `401` · `403` · `404` · `409` |
| `POST /api/v1/travel-buddies/requests/{request_id}/reject` | Recipient declines (`pending → rejected`) | `200` · `401` · `403` · `404` · `409` |
| `POST /api/v1/travel-buddies/requests/{request_id}/cancel` | Requester withdraws (`pending → cancelled`) | `200` · `401` · `404` · `409` |
| `GET /api/v1/social/discovery` | Broad feed of discoverable verified-user profiles (at most 10), same honesty message | `200` · `401` · `403` |

### Who may do what (the gate is layered, on purpose)

- **Plain login (any verification state):** everything under
  `/travel-profile/me`, `/travel-plans`, and reading/cancelling **your own**
  requests. Managing your own travel data — including retracting a request
  you sent — is never blocked by the social policy.
- **Social gate (`require_verified_user`, the same dependency
  `/social/discovery` has used since Phase 6):** discovery, sending a
  request, accepting/rejecting, and viewing someone's public profile. While
  the owner's policy requires verification, an unverified account gets
  `403` with a status-specific message.

### Discovery: who can appear, and how they are ranked

A candidate appears only if **all** of these hold: they have a travel
profile marked `discoverable`; the plan is `active` and `discoverable` and
has not ended; they are not you; they are not already an accepted partner
or the counterparty of a pending request in either direction; and — while
the policy requires verification — their account is `verified`.

Ranking is a **documented heuristic**, capped at 100:

| Signal | Points |
| --- | --- |
| Destination matches your `?destination=` filter (normalized: casefold + whitespace-collapse) | +40 |
| Region matches your `?region=` filter instead | +20 |
| Plan overlaps your `?start_date=`/`?end_date=` window | +30 (strict) / +15 (overlap only via the ±7-day flexible grace) |
| Shared declared interests | +5 each (max +15) |
| Shared travel styles | +5 each (max +10) |
| Shared language | +5 |

The destination/region/date weights score **what you filtered for**; an
unfiltered browse therefore ranks by shared preferences only. Normalization
is exact after casefold/whitespace-collapse — punctuation variants ("Goa,
India" vs "Goa India") are treated as different destinations (documented
limitation). Every discovery response carries a `note` repeating the
honesty boundary:

> Compatibility scores are a deterministic ranking of travel logistics and
> stated preferences — **not a guarantee that anyone is safe** or that two
> people will get along. Always meet in public and tell a trusted contact
> your plans.

### Request lifecycle

```text
A: POST /travel-buddies/requests {"recipient_id": B, "plan_id": <B's plan>}
→ 201 { "id": "…", "status": "pending", … }

B: GET  /travel-buddies/requests?direction=incoming   → sees the request
B: POST /travel-buddies/requests/{id}/accept          → 200 "accepted"
   (or /reject → "rejected"; A may /cancel while pending → "cancelled")
```

Accepted is a **social connection only**: it grants no verification bypass,
no chat, no notifications, and no access either user did not already have.
Duplicates are refused before they are written: a second pending request in
the same direction hits the database's partial UNIQUE index (concurrent
duplicates lose there, not in application code), and since Phase 8 the
cross-direction duplicate ("B asks A while A's request to B is pending")
is refused by the database too, via the canonical-pair pending UNIQUE
index (`pair_low_id`, `pair_high_id`) — the endpoint's either-direction
pre-check remains as the friendly first layer. Sending is rate limited
to 30 requests/hour/user (`429` beyond that — in-process counter, same
documented caveat as the owner policy limiter).

## Stranger chat (Phase 8)

One-to-one text messaging behind an explicit ask-and-accept. Accepting a
**travel**-partner request does NOT open chat — this surface needs its
own message request and its own accept (enforced by never reading travel
tables in the chat code).

`No conversation → pending ask → accepted conversation → messages`
(reject/cancel are terminal for that ask; an explicit NEW ask may reopen
the pair's single row — nothing reopens silently, and one row per
unordered pair means duplicate pending asks are structurally impossible,
even racing, even in opposite directions).

| Method + path | Purpose | Success / errors |
| --- | --- | --- |
| `POST /api/v1/chat/requests` | Ask a user to chat (`{"recipient_id": "…"}`) | `201` · `401` · `403` · `404` unknown/ineligible/blocked · `409` duplicate · `422` self · `429` 30/hour |
| `GET /api/v1/chat/requests?direction=incoming\|outgoing` | My asks (`?status=`, `?offset=`/`?limit=`) | `200` · `401` · `422` |
| `GET /api/v1/chat/requests/{id}` | One ask I am part of (404 otherwise) | `200` · `401` · `404` |
| `POST /api/v1/chat/requests/{id}/accept` | Recipient accepts (asker's eligibility rechecked live) | `200` · `401` · `403` · `404` · `409` |
| `POST /api/v1/chat/requests/{id}/reject` | Recipient declines | `200` · `401` · `403` · `404` · `409` |
| `POST /api/v1/chat/requests/{id}/cancel` | Asker withdraws | `200` · `401` · `404` · `409` |
| `GET /api/v1/chat/conversations` | My conversations, recent first (`?offset=`/`?limit=`) | `200` · `401` |
| `GET /api/v1/chat/conversations/{id}` | One conversation I am in (history stays readable after blocks) | `200` · `401` · `404` |
| `GET /api/v1/chat/conversations/{id}/messages` | History, stable `(created_at, id)` order (`?offset=`/`?limit=` 1–100) | `200` · `401` · `403` · `404` |
| `POST /api/v1/chat/conversations/{id}/messages` | Send one text message (1–2000 chars; sender always = you) | `201` · `401` · `403` blocked/ineligible · `404` · `409` not accepted · `422` · `429` 60/hour |
| `DELETE /api/v1/chat/messages/{id}` | Delete MY message (soft: row kept, body hidden) | `200` · `401` · `404` not mine/missing |

Sending rechecks everything live on every call: participant, `accepted`
status, blocks in either direction, and the counterparty's verification
eligibility (a lapsed counterparty cannot be messaged — old accepted
relationships bypass nothing). A block and a lapsed counterparty produce
the same neutral `403` ("Messaging is not available with this user right
now"), so neither fact leaks through the error.

## Blocking (Phase 8)

One directed row ("I want nothing from them") that stops BOTH
directions: once A blocks B, neither A→B nor B→A messaging, message
requests, travel-buddy discovery results, public profiles, or new
travel-partner requests are possible, and accepting an older ask fails
instead of bypassing the block. Existing conversation history stays
readable to both participants (nothing is silently deleted); sending
stops until unblock. Blocking is independent of discoverability switches
and verification, and — like cancelling your own request — it stays on
**plain authentication** so a harassed user can block while unverified.

| Method + path | Purpose | Success / errors |
| --- | --- | --- |
| `POST /api/v1/blocks` | Block a user (`{"blocked_id": "…"}`) | `201` · `401` · `404` unknown user · `409` duplicate · `422` self |
| `GET /api/v1/blocks` | MY block list only (newest first) | `200` · `401` |
| `DELETE /api/v1/blocks/{id}` | Remove MY block (204; only the blocker) | `204` · `401` · `404` |

## Session security (Phase 8)

Stateless JWTs cannot be "taken back" by themselves, so every
login/register now mints a server-side session row and the token carries
its id (`sid`) plus a revocation version (`tv`). **Every authenticated
request re-checks both**: a revoked or missing session row, or a version
older than the account's, makes the token stop working immediately — not
at expiry. Pre-Phase-8 legacy tokens (no `sid`) are governed by the
version check alone, so "revoke all" kills them too.

| Method + path | Purpose | Success / errors |
| --- | --- | --- |
| `GET /api/v1/auth/sessions` | MY sessions, newest first (with `current` flag) | `200` · `401` |
| `POST /api/v1/auth/logout` | Revoke THIS session (calling token dies on next use) | `200` · `401` · `404` legacy token · `410` already revoked |
| `POST /api/v1/auth/sessions/{id}/revoke` | Revoke one of MY sessions (404 for anyone else's) | `200` · `401` · `404` |
| `POST /api/v1/auth/sessions/revoke-others` | Keep exactly this session, kill the rest | `200` · `401` · `404` legacy token |
| `POST /api/v1/auth/revoke-all` | Kill ALL my sessions + bump the version (current token dies too) | `200` · `401` |

Revocation kills **tokens, not passwords**: logging in again after
revoke-all works (there are no refresh tokens to reject — none ever
existed). No device fingerprinting, IP tracking, or user-agent
collection exists: the optional `device_label` on register/login is a
free-form display aid the user supplies (`"my phone"`), never collected
automatically. Raw tokens are never stored or logged — only session-row
ids the tokens already carried.

> **Remaining limitation:** the 30/hour chat-request and 60/hour message
> limiters are in-process (reset on restart, per-process) — the same
> documented caveat as the owner-policy and travel-request limiters. No
> shared rate-limit store exists; none was added (no new infrastructure
> per the brief).

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
- `ab32047c8481` — Phase 6: turns `community_reports.category` from a
  loose string into a closed 6-value set by adding the
  `ck_community_reports_category_valid` CHECK constraint
  (`unsafe_area`, `harassment`, `suspicious_activity`, `road_hazard`,
  `poor_lighting`, `other`). The **upgrade** checks existing rows first:
  if any report carries an out-of-set category, it deliberately
  **refuses** with an actionable error before touching anything (an
  explicit data-handling decision is needed first — see Common
  problems). The **downgrade** only drops the constraint, which cannot
  lose or alter data, so it always proceeds and every stored category
  value survives. Round-trip verified (`upgrade` → `downgrade` →
  `upgrade`) on SQLite and PostgreSQL. `alembic current` →
  `ab32047c8481 (head)`.
- `3e285edb0896` — Phase 6 second assignment: adds the NOT NULL
  `users.verification_status` (default `unverified`) and `users.role`
  (default `user`) columns with CHECK constraints, plus three new tables
  (`identity_verifications`, `app_settings`, `setting_changes`). The
  **upgrade** needs no guard: the new columns are backfilled to the secure
  defaults in the same statement that adds them, so no existing row can
  violate the new CHECKs. The **downgrade** is guarded: if any
  verification request, policy, or audit row exists — or any user has a
  non-default state/role — it deliberately **refuses** with an actionable
  census of the blocking rows *before* touching the schema (data-safety
  guard — see Common problems). Round-trip verified (`upgrade` →
  `downgrade` → `upgrade`) on SQLite and PostgreSQL, plus live on
  `roamlary_dev`. `alembic current` → `3e285edb0896 (head)`.
- `426dcef31e27` — Phase 7: adds the three travel tables
  (`travel_profiles` with a UNIQUE `user_id` index and a 2–12 group-size
  CHECK, `travel_plans` with end ≥ start / status / visibility CHECK
  constraints and discovery-shaped indexes, `travel_partner_requests`
  with a no-self-request CHECK, a status CHECK, RESTRICT foreign keys to
  `users` and to the optional context `travel_plans` row, and two
  partial UNIQUE indexes that keep at most one PENDING row per direction
  of a user pair). The **upgrade** needs no guard (new tables — nothing
  existing can violate them). The **downgrade** is guarded the same way
  as Phases 4–6: while any travel profile, plan, or partner request
  exists it **refuses** with an actionable error before touching the
  schema. Round-trip verified (`upgrade` → `downgrade` → `upgrade`) on
  SQLite and PostgreSQL, plus live on `roamlary_dev`. `alembic current`
  → `426dcef31e27 (head)`.
- `7f3a9c1e5b42` — Phase 8: adds the four chat/block/session tables
  (`user_blocks` with a UNIQUE blocker/blocked pair and a no-self
  CHECK, `conversations` with one row per canonical unordered pair
  (UNIQUE) plus a pending/accepted/rejected/cancelled CHECK,
  `messages` text-only with soft-delete flags, `auth_sessions` one row
  per login), the NOT NULL `users.token_version` column (server default
  0), and the travel canonical-pair columns (`pair_low_id`/
  `pair_high_id`, backfilled from the directed columns with a
  dialect-aware UPDATE) with a pending-only UNIQUE index that closes
  the Phase 7 cross-direction race. The **upgrade** needs no guard for
  the new tables; the **downgrade** is guarded the same way as Phases
  4–7: while any block, conversation, message, or session row exists it
  **refuses** before touching the schema. Round-trip verified on SQLite
  and PostgreSQL, plus live on `roamlary_dev`. `alembic current` →
  `7f3a9c1e5b42 (head)`.

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

- **Offline unit tests** (221) — use an in-memory SQLite database and the
  FastAPI `TestClient`. No PostgreSQL, no network. They prove model
  behaviour, auth flows (register/login/JWT/profile), contact & check-in
  endpoint contracts (ownership, transitions, timestamps), SOS endpoint
  contracts (activation validation, ownership, lifecycle), community-report
  endpoint contracts (strict creation, privacy, visibility, filters,
  pagination bounds, nearby radius/antimeridian/high-latitude behaviour),
  verification & admin/policy endpoint contracts (state machine, no
  self-verify/self-review, fail-closed policy, audit, rate limit, strict
  schemas), fail-closed behaviour, route contracts, and the migration chain
  (including the Phase 4 downgrade guard, the Phase 5 downgrade guard, the
  Phase 6 **upgrade** guard, and the Phase 6 second assignment **downgrade**
  guard). They always run with a fixed TEST-ONLY
  JWT secret (never the real `.env` value).
- **PostgreSQL integration tests** (24) — run against a **disposable**
  database and prove real PostgreSQL behaviour (native `uuid` columns, CHECK
  constraint enforcement — including the Phase 4/5 `cancelled` values,
  Phase 6 category constraint, Phase 6 second assignment role/verification
  CHECKs, and new columns — timezone-aware
  timestamps, the `password_hash` column, downgrade guards: refused
  with `cancelled` rows, allowed without them, the Phase 6 upgrade
  guard: refused with out-of-set categories, and the Phase 6 second
  assignment downgrade guard: refused with verification/policy/audit data,
  allowed without). They are **skipped** unless
  you point them at a throwaway database.

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
| `422` on `POST /reports` | Unknown `category`, missing coordinates, out-of-range lat/lon, blank/overlong `description`, or an injected server-controlled field (`user_id`, `status`, `id`, timestamps) | Send exactly `category` (one of the six: `unsafe_area`, `harassment`, `suspicious_activity`, `road_hazard`, `poor_lighting`, `other`), `description` (1–500 non-blank chars), `latitude`, `longitude` |
| `422` on `GET /reports/nearby` | Missing/invalid `latitude`/`longitude`, missing `radius_m`, `radius_m` ≤ 0 or > 50000, or `limit`/`offset` out of bounds | Send `latitude` (−90…90), `longitude` (−180…180), `radius_m` in **meters** (1–50000), plus optional `limit` (1–100) / `offset` (≥ 0) |
| `404` on `GET /reports/{id}` | The report is missing **or** `rejected` (both return the identical `404` by design — hidden reports can't be probed) | Rejected reports are invisible to the public API; check with an admin/DBA if moderation ever lands |
| `RuntimeError: Refusing to upgrade migration ab32047c8481 …` | At least one `community_reports` row carries a category outside the Phase 6 closed set (any string was legal in the Phase 2 schema) | Intentional data-safety guard: nothing was changed. Decide what to do with those rows (map each to an allowed category such as `other`, or delete them), then re-run `alembic upgrade head` |
| `RuntimeError: Refusing to downgrade migration 3e285edb0896 …` | Verification requests, policy/audit rows, or a non-default user state/role would be orphaned by the downgrade | Intentional data-safety guard: nothing was changed (the error lists exact counts). Decide what to do with those rows first, then re-run — or keep the Phase 6 second-assignment schema |
| `403` "Identity verification is required for social features…" on `/social/discovery` | The account is `unverified`/`pending`/`rejected` while the policy requires verification | Expected gate. `POST /verification/requests` (or re-submit after a rejection), wait for an owner decision; `GET /verification/status` shows where you stand |
| `403` "Owner privileges required for this action." | The account's `role` is not `owner` (admin routes only) | Expected: run the server-side CLI `.venv\Scripts\python -m app.cli make-owner <email>` on the server — no API path grants roles |
| `409` "You cannot review your own verification request." | The owner tried to approve/reject their OWN request | Expected no-self-elevation rule; with a single owner, that account stays `unverified` through the API (documented limitation) |
| `409` "A verification request is already under review." / "already verified" | Submitting while `pending`, or while `verified` | Only `unverified`/`rejected` accounts may submit; read `GET /verification/status` first |
| `429` on `PATCH /admin/policy/social-verification` | More than 5 policy changes from one owner within an hour (in-process limit) | Expected throttle; wait for the window to pass, or restart the dev server (the counter is in-memory) |
| `422` on register/`PATCH /users/me` mentioning `role` or `verification_status` | Injecting a field only the server may set | Send only the documented fields — roles/verification states are changed by the CLI and owner review, never by clients |
| `404` on `GET /travel-profile/me` | No travel profile exists for the account yet | Expected: the message tells you to `POST /travel-profile/me` with `{}` (or fields) to create one |
| `403` on `/travel-buddies/discover` or `/travel-buddies/{user_id}` | The account is not `verified` while the policy requires verification (same gate as `/social/discovery`) | Expected gate. Complete verification, or ask an owner to flip the policy during development |
| `404` "Recipient not found." on `POST /travel-buddies/requests` | The recipient is hidden (`discoverable=false`), has no travel profile, or failed the live verification policy — all collapse to the same `404` so eligibility can't be probed | Only send to users you actually saw in discovery; if they just hid themselves, the `404` is the honest answer |
| `409` on `POST /travel-buddies/requests` | A `pending` or `accepted` request already exists between the two users in either direction | Check `GET /travel-buddies/requests?direction=outgoing` first; a rejected/cancelled request may be re-sent |
| `429` on `POST /travel-buddies/requests` | More than 30 sends from one user within an hour (in-process limit) | Expected throttle; wait for the window to pass, or restart the dev server (the counter is in-memory) |
| `409` on `DELETE /travel-plans/{plan_id}` | A travel-partner request still references the plan (`ON DELETE RESTRICT`) | Cancel/close the request (or accept it — accepted requests keep their context plan), then delete |
| `422` on `POST /travel-buddies/requests` with your own `recipient_id` | Self-requests are structurally impossible (schema + database CHECK) | Pick a recipient from discovery — never yourself |
| `RuntimeError: Refusing to downgrade migration 426dcef31e27 …` | Travel profiles, plans, or partner requests exist that the older schema cannot hold | Intentional data-safety guard: nothing was changed. Export or delete those rows first, then re-run — or keep the Phase 7 schema |
| `RuntimeError: Refusing to downgrade migration 7f3a9c1e5b42 …` | Block, conversation, message, or session rows exist that the older schema cannot hold | Intentional data-safety guard: nothing was changed (the error lists exact counts). Export or delete those rows first, then re-run — or keep the Phase 8 schema |
| `401` "Session has been revoked. Please log in again." | The token's session was logged out/revoked, or "revoke all" bumped the account version (legacy tokens included) | Expected: log in again for a fresh session. To end just one device, use `POST /auth/sessions/{id}/revoke` instead of revoke-all |
| `404` "User not found." on `POST /chat/requests` | The recipient is unknown, fails the live verification policy, or is blocked in either direction (all collapse to one 404 so blocks and eligibility cannot be probed) | Only ask users you can actually reach; if they just blocked you or hid, the `404` is the honest answer |
| `403` "Messaging is not available with this user right now." on send | A block stands in either direction, or the counterparty fails the live verification policy (one neutral message for both causes) | Nothing to fix client-side beyond unblocking (your own block) or waiting for eligibility; history stays readable either way |
| `409` on `POST /chat/requests` | A pending ask already exists between you two (either direction — one row per pair) or you already chat | Answer the pending ask instead (`/accept`/`/reject`), or open the existing conversation |
| `429` on chat send/request | More than 60 messages or 30 requests from one user within an hour (in-process limits) | Expected throttle; wait for the window to pass, or restart the dev server (counters are in-memory) |
| `404` on `DELETE /blocks/{id}` | No block by YOU of that user exists (includes trying to remove someone else's block of you) | Only the blocker removes their own block; check `GET /blocks` first |

## Development log

Every task, file-by-file explanations, actual test outputs, and decisions live
in [`report.md`](report.md).
