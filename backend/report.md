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

## 2. Current environment and baseline (verified 2026-10-13)

| Item | Verified status |
|---|---|
| Repository | `C:\Projects\Roamlary` (Git, remote `origin` → github.com/Tanishq0822/Roamlary.git) |
| Branch | `backend` (all work pushed to `origin/backend`: Phases 1–3 + audit as `5ea9b59`/`eb8e709`/`3d728ac`/`f26536e`; Phases 4+5 as `f602505`; Phase 6 as `9029047`; **Phase 6 second assignment committed and pushed, 2026-10-12 23:47, as `30977c0`** — see `git log`). HEAD **`30977c0`** = `origin/backend`; the working tree carries the **uncommitted Phase 7 change set** (owner rule: no commits during a phase). **Owner also decided (2026-10-12) to fast-forward `main` to this branch and add `docs/README.md`** — both done, see §16 |
| History | `4761b41` initial setup (includes the Flutter template `frontend/`) → `c06d092` scaffolding → `11f2d7e` report → `5ea9b59` Phase 1 → `eb8e709` Phase 2 → `3d728ac` Phase 3 → `f26536e` Phase 3 audit → `f602505` Phases 4+5 → `9029047` Phase 6 (+ docs placeholder commit) → **`main` fast-forwarded to match** (2026-10-12, owner-instructed) |
| Python | 3.13.2 in project venv (system also has 3.11.3) |
| pip | 26.2.1 inside `.venv` |
| PostgreSQL | **Running locally** — server 16.15 in the Docker container `roamlary-postgres-dev` (databases: `roamlary_dev`, `roamlary_test`). No system-wide install | 
| Docker | Engine started for Phase 2 (image `postgres:16-alpine`). Stop it when not needed: `docker stop roamlary-postgres-dev` |
| Flutter | 3.47.7 stable (frontend untouched by backend work) |
| Secrets in repo | **None found** — only `.env.example` templates exist (the real `JWT_SECRET_KEY` lives only in the gitignored `.env`) |
| Auth libraries | `argon2-cffi==25.1.0` (Argon2id password hashing) + `PyJWT==2.15.1` (HS256 JWTs), added in Phase 3 |
| Frontend project | `frontend/roamlary_app` — default Flutter template, no app logic, no HTTP package |

## 3. Development phases and status

Roadmap assigned by the project owner (Phases 0–7 complete; Phases 8+ are NOT
started — the backend lead waits for each phase assignment):

| Phase | Name | Status |
|---|---|---|
| 0 | Repository inspection & planning | ✅ Complete (approved by owner: "ok you can do that") |
| 1 | FastAPI foundation | ✅ **Complete — implemented & verified** (this report §7) |
| 2 | PostgreSQL connection, models, migrations | ✅ **Complete — implemented & verified** (this report §8) |
| 3 | Authentication & user profiles | ✅ **Complete** — committed `3d728ac`, pushed; owner-assigned audit & fix round (§9.14) later committed as `f26536e` and pushed after the owner said "commit and push it" |
| 4 | Trusted contacts & safety check-ins | ✅ **Complete — implemented & verified** (this report §10); owner's rules forbid commits during the phase, so it stayed uncommitted through the owner-assigned migration-safety fix round (§10.15) — later **committed and pushed together with Phase 5** after owner approval (see `git log`) |
| 5 | SOS & emergency workflow (simulated) | ✅ **Complete — implemented & verified** (this report §11); uncommitted during the phase per the same rule; **committed and pushed together with Phase 4** after owner approval (see `git log`) |
| 6 | Community safety reports & location data | ✅ **Complete — implemented & verified** (this report §12); stayed uncommitted during the phase per the owner's rule, then the owner instructed commit & push (2026-10-12) — **committed and pushed to `origin/backend`** (see `git log`) |
| 6 (second assignment) | Identity verification & social access foundation | ✅ **Complete — implemented & verified** (this report §13); committed and pushed after the phase as `30977c0` (owner-authorized, 2026-10-12 23:47 — the report's earlier "awaiting review" note predates that commit) |
| 7 | Travel buddies & social discovery (owner's brief; the original roadmap proposal was "AI companion & safety signals" — replaced by the owner's actual assignment) | ✅ **Complete — implemented & verified** (this report §14); uncommitted working-tree changes awaiting owner review (owner rule: no commits during the phase) |
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
| 2026-10-12 | **Phase 3 audit & fix** | Owner assigned Phase 3 verification round → audited all 4 endpoints, config, migration, and tests; fixed strict request schemas (422 on injected fields), login timing equalization, fail-closed-before-DB-write ordering, no-op PATCH `updated_at`, stale `config.py` docstring; added 12 new tests (fail-closed, required claims, race condition, impersonation, hermetic secret); corrected report/README contradictions | *was* uncommitted at the time; owner later said "commit and push it" → committed as `f26536e`, pushed to `origin/backend` |
| 2026-10-12 | **Phase 4** | Owner assigned Phase 4 → trusted-contact CRUD (5 routes) + check-in lifecycle (5 routes incl. `/complete`), added `TrustedContact.relationship` + `CheckIn.note` columns and the `cancelled` status, migration `ccd362671e07` (applied to `roamlary_dev`), 40 new tests (37 endpoint + 3 PostgreSQL integration), README + this report + `PHASE4_CHANGES.md` | **uncommitted working-tree changes** (owner rule: no commits during this phase) → owner later approved → **committed and pushed together with Phase 5** (see `git log`) |
| 2026-10-12 | **Phase 4 migration-safety fix** | Owner assigned a targeted fix round (§10.15): the Phase 4 migration's `downgrade()` now detects `cancelled` check-ins **before** any schema change and refuses with an actionable error instead of failing mid-migration; 4 new regression tests (2 SQLite + 2 real-PostgreSQL), live refusal + normal path proven on `roamlary_dev`, docs corrected (the earlier "reversible" wording implied it always succeeds regardless of data) | **uncommitted working-tree changes** (no commits/pushes/branch changes) → owner later approved → **committed and pushed together with Phases 4 and 5** (see `git log`) |
| 2026-10-12 | **Phase 5** | Owner assigned Phase 5 → extended the Phase 2 `sos_events` table (`description`, `location_recorded_at`, `cancelled_at`, `cancelled` status; migration `0dd8995649b4` with the same downgrade data-safety guard), 5 SOS endpoints (activate/list/get/cancel/resolve) with strict schemas, owner-only queries, identical-404s and server-only timestamps; 30 new tests (24 endpoint + 2 SQLite migration + 4 PostgreSQL), live E2E 35/35 + live migration-guard demo on `roamlary_dev`, README + this report + `PHASE5_CHANGES.md` | **uncommitted working-tree changes** (no commits/pushes/branch changes) → owner later approved → **committed and pushed together with Phase 4** (see `git log`) |
| 2026-10-12 | **Phase 6** | Owner assigned Phase 6 → reused the Phase 2 `community_reports` table; added a closed 6-value `ReportCategory` set (+ DB CHECK, migration `ab32047c8481` with an **upgrade-side** data guard), 4 report endpoints (create/list with filters+pagination/nearby haversine search/get-by-id) with `ReportRead` (identity-free, UTC); 35 new tests (28 endpoint + 2 SQLite migration + 3 PostgreSQL + 2 model-contract), live E2E 51/51 + live migration-guard demo on `roamlary_dev`, README + this report + `PHASE6_CHANGES.md` | **uncommitted working-tree changes** during the phase → owner instructed commit & push (2026-10-12) → **committed and pushed to `origin/backend`** (see `git log`) |
| 2026-10-12 | **Phase 6 (second assignment)** | Owner assigned a second Phase 6 brief (identity verification & social access foundation) → `users.verification_status` + `users.role` columns, `identity_verifications` request history, `app_settings` policy row + append-only `setting_changes` audit (fail-closed `get_policy`), `require_owner` / `require_verified_user` server-side gates, 7 new routes (verification status/submit, owner queue approve/reject, owner policy read/patch with 5/hour rate limit, gated social discovery placeholder), server CLI `python -m app.cli make-owner <email>`, migration `3e285edb0896` (downgrade guarded by data), 52 new tests; live E2E 54/54 + live guard-refusal + live downgrade/upgrade roundtrip on `roamlary_dev`, README + this report + `PHASE6_IDENTITY_CHANGES.md` | **uncommitted working-tree changes** (owner rule: no commits during the phase) → awaiting owner review |
| 2026-10-13 | **Phase 7** | Owner assigned Phase 7 (travel buddies & social discovery) → audit-first (§14.1, recorded before any code); 3 new tables (`travel_profiles`, `travel_plans`, `travel_partner_requests`) + 3 new VARCHAR-backed CHECK enums + migration `426dcef31e27` (downgrade data-guarded); pure-function matching engine (`app/core/matching.py`, documented weights summing to 100, honesty note in every response) + discovery service (`app/services/discovery.py`: indexed SQL prefilter, self/partner/pending exclusion, verification join, grace-widened date window as a documented superset, Python precise overlap classification, dedupe, deterministic ranking, offset/limit pagination, `MAX_CANDIDATE_ROWS=500`); 12 new routes (travel-profile CRUD, travel-plan CRUD, `/travel-buddies/discover`, `/travel-buddies/{user_id}`, request send/list/get/accept/reject/cancel) reusing the Phase 6b `require_verified_user` gate unchanged for outward-facing actions; `/social/discovery` reimplemented over `broad_feed()` keeping the `{profiles, message}` contract; in-process 30/hour send rate limit; 94 new tests (88 offline: 79 in four new files + 6 model-contract + 3 SQLite migration; + 6 real-PostgreSQL integration); live E2E 24/24 on `roamlary_dev` + live `alembic upgrade head`; README + this report + `PHASE7_TRAVEL_BUDDIES.md` | **uncommitted working-tree changes** (owner rule: no commits during the phase) → awaiting owner review |

## 5. Proposed API contract — only what is IMPLEMENTED is a contract

**Implemented and verified (Phase 1 + Phase 3 + Phase 4 + Phase 5 + Phase 6 + Phase 6 second assignment + Phase 7):**

| Method + Path | Purpose | Auth | Response |
|---|---|---|---|
| `GET /api/v1/health` | Liveness check (process is running). Does NOT check database/AI/notifications | none | see below |
| `POST /api/v1/auth/register` | Create a local account; returns a bearer token (auto-login) | none | `{access_token, token_type}` (HTTP 201) |
| `POST /api/v1/auth/login` | Authenticate with email + password; returns a bearer token | none | `{access_token, token_type}` (HTTP 200) |
| `GET /api/v1/users/me` | Return the authenticated user's public profile | Bearer JWT | `UserProfile` (see §9.6) |
| `PATCH /api/v1/users/me` | Update the authenticated user's `display_name` | Bearer JWT | `UserProfile` |
| `GET /api/v1/verification/status` | The caller's OWN verification picture: `verification_status`, `role`, live `social_access_required`, latest request | Bearer JWT | `VerificationStatusResponse` |
| `POST /api/v1/verification/requests` | Submit a manual-review verification request (`pending`, server-chosen; optional `note` ≤200 chars; only from `unverified`/`rejected`) | Bearer JWT | `VerificationRequestSummary` (HTTP 201) |
| `GET /api/v1/admin/verification-requests` | Review queue, oldest first (`?status=pending\|approved\|rejected`, `?offset=`/`?limit=` 1–100) | Bearer JWT + **owner role** | `[VerificationRequestReview]` |
| `POST /api/v1/admin/verification-requests/{id}/approve` | Approve a `pending` request → applicant becomes `verified` (optional `review_note` ≤200) | Bearer JWT + **owner role** | `VerificationRequestReview` |
| `POST /api/v1/admin/verification-requests/{id}/reject` | Reject a `pending` request → applicant becomes `rejected` (optional `review_note` ≤200) | Bearer JWT + **owner role** | `VerificationRequestReview` |
| `GET /api/v1/admin/policy/social-verification` | Read the effective policy (fail-closed reporting) | Bearer JWT + **owner role** | `PolicyResponse` |
| `PATCH /api/v1/admin/policy/social-verification` | Change `requires_verification` (validated boolean; rate limited 5/hour/owner; audited who/when/old/new) | Bearer JWT + **owner role** | `PolicyResponse` |
| `GET /api/v1/social/discovery` | Broad travel-buddy feed — **real since Phase 7**: up to 10 discoverable verified-user profiles + honesty message (same wire contract as the placeholder it replaced) | Bearer JWT + verified while policy requires it | `DiscoveryResponse` |
| `POST /api/v1/trusted-contacts/` | Save a contact for the token's user | Bearer JWT | `TrustedContactRead` (HTTP 201) |
| `GET /api/v1/trusted-contacts/` | List the token user's contacts (oldest first) | Bearer JWT | `[TrustedContactRead]` |
| `GET /api/v1/trusted-contacts/{contact_id}` | Read one contact (404 if missing **or** not yours) | Bearer JWT | `TrustedContactRead` |
| `PATCH /api/v1/trusted-contacts/{contact_id}` | Edit name/phone/relationship/email | Bearer JWT | `TrustedContactRead` |
| `DELETE /api/v1/trusted-contacts/{contact_id}` | Delete one contact | Bearer JWT | HTTP 204, no body |
| `POST /api/v1/check-ins/` | Create a check-in (`pending`, server-chosen) | Bearer JWT | `CheckInRead` (HTTP 201) |
| `GET /api/v1/check-ins/` | List the token user's check-ins (newest first, `?status=` filter) | Bearer JWT | `[CheckInRead]` |
| `GET /api/v1/check-ins/{checkin_id}` | Read one check-in (404 if missing **or** not yours) | Bearer JWT | `CheckInRead` |
| `PATCH /api/v1/check-ins/{checkin_id}` | Edit note/deadline, or transition status | Bearer JWT | `CheckInRead` |
| `POST /api/v1/check-ins/{checkin_id}/complete` | Mark an eligible check-in `safe` (server clock) | Bearer JWT | `CheckInRead` |
| `POST /api/v1/sos` | Activate an SOS incident (`active`, server-chosen; optional description + coordinates) | Bearer JWT | `SosEventRead` (HTTP 201) |
| `GET /api/v1/sos` | List the token user's incidents (newest first) | Bearer JWT | `[SosEventRead]` |
| `GET /api/v1/sos/{sos_id}` | Read one incident (404 if missing **or** not yours) | Bearer JWT | `SosEventRead` |
| `POST /api/v1/sos/{sos_id}/cancel` | Retract an `active` incident (`cancelled_at`, server clock; no body) | Bearer JWT | `SosEventRead` |
| `POST /api/v1/sos/{sos_id}/resolve` | Close an `active` incident (`resolved_at`, server clock; no body) | Bearer JWT | `SosEventRead` |
| `POST /api/v1/reports` | File a community safety report (`pending`, server-chosen; category + description + coordinates required) | Bearer JWT | `ReportRead` (HTTP 201) |
| `GET /api/v1/reports` | List **visible** reports, newest first (optional `?category=`/`?status=` filters, `?offset=`/`?limit=` pagination) | Bearer JWT | `[ReportRead]` |
| `GET /api/v1/reports/nearby` | Visible reports within `radius_m` **meters** of a position (haversine; nearest first) | Bearer JWT | `[ReportRead]` |
| `GET /api/v1/reports/{report_id}` | Read one visible report (404 if missing **or** `rejected`) | Bearer JWT | `ReportRead` |
| `GET /api/v1/travel-profile/me` | The caller's own travel profile + `completion` hints (404 with actionable guidance when absent) | Bearer JWT | `TravelProfileRead` |
| `POST /api/v1/travel-profile/me` | Create it (one per account; `discoverable` defaults to `false`) | Bearer JWT | `TravelProfileRead` (HTTP 201) |
| `PATCH /api/v1/travel-profile/me` | Partial update (explicit `null` clears; `[]` empties a list) | Bearer JWT | `TravelProfileRead` |
| `DELETE /api/v1/travel-profile/me` | Remove the profile (plans are NOT touched) | Bearer JWT | HTTP 204, no body |
| `POST /api/v1/travel-plans/` | Publish a plan (`private` by default; dates re-validated together) | Bearer JWT | `TravelPlanRead` (HTTP 201) |
| `GET /api/v1/travel-plans/` | The token user's plans (active first, newest first) | Bearer JWT | `[TravelPlanRead]` |
| `GET /api/v1/travel-plans/{plan_id}` | Read one plan (404 if missing **or** not yours) | Bearer JWT | `TravelPlanRead` |
| `PATCH /api/v1/travel-plans/{plan_id}` | Edit a plan (full re-validation against stored values) | Bearer JWT | `TravelPlanRead` |
| `DELETE /api/v1/travel-plans/{plan_id}` | Delete a plan (409 if a partner request still references it) | Bearer JWT | HTTP 204, no body |
| `GET /api/v1/travel-buddies/discover` | Eligible, scored, paginated candidates (`?destination=`/`?region=`/`?start_date=`/`?end_date=`/`?interests=`/`?travel_style=`/`?language=`/`?min_score=`/`?offset=`/`?limit=`) | Bearer JWT + verified while policy requires it | `DiscoveryPage` (results + total + honesty `note`) |
| `GET /api/v1/travel-buddies/{user_id}` | Limited public travel profile of one discoverable user (404 if missing **or** not discoverable) | Bearer JWT + verified while policy requires it | `PublicTravelProfileRead` |
| `POST /api/v1/travel-buddies/requests` | Ask a discovered user to travel together (`recipient_id` required; `plan_id` optional = the RECIPIENT's public plan as context) | Bearer JWT + verified while policy requires it | `BuddyRequestRead` (HTTP 201) |
| `GET /api/v1/travel-buddies/requests` | Own request history (`?direction=incoming\|outgoing`, `?status=`, `?offset=`/`?limit=`) | Bearer JWT | `BuddyRequestList` |
| `GET /api/v1/travel-buddies/requests/{request_id}` | Read one request (404 unless the caller is a party) | Bearer JWT | `BuddyRequestRead` |
| `POST /api/v1/travel-buddies/requests/{request_id}/accept` | Recipient accepts (`pending → accepted`) | Bearer JWT + verified while policy requires it | `BuddyRequestRead` |
| `POST /api/v1/travel-buddies/requests/{request_id}/reject` | Recipient declines (`pending → rejected`) | Bearer JWT + verified while policy requires it | `BuddyRequestRead` |
| `POST /api/v1/travel-buddies/requests/{request_id}/cancel` | Requester withdraws (`pending → cancelled`) | Bearer JWT | `BuddyRequestRead` |

Phase 4 request/response examples, field rules, status transitions, and
timestamp policy: **§10.6** (details) and `README.md` (client-facing).
Phase 5 (SOS) equivalents: **§11.6** and the README's "SOS incidents"
section. Phase 6 (reports): **§12.6** and the README's "Community safety
reports" section. Phase 6 second assignment (verification/social):
**§13.6** and the README's "Identity verification & social gate" section.
Phase 7 (travel buddies): **§14.6** and the README's "Travel buddies &
discovery" section.
Note the SOS and report paths have no trailing slash
(`/sos`, `/reports`, per their specs) while the Phase 4 collections use
one (`/check-ins/`); Phase 7 collections follow the Phase 4 style
(`/travel-plans/`, trailing slash) except `/travel-buddies/*`, which was
specified without one.

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

Phase 4 error behaviour: every contact/check-in route without a valid bearer
token → **401**; a contact or check-in that does not exist **or** belongs to
another user → the **same 404** (no ownership enumeration); an invalid status
transition, a `PATCH` on an already-answered check-in, or `/complete` on a
`needs_help`/`cancelled` record → **409**; any unknown/injected field, a
malformed UUID, a naive timestamp, or a `due_at` already in the past →
**422**.

Phase 5 (SOS) error behaviour: every SOS route without a valid bearer
token → **401**; an incident that does not exist **or** belongs to another
user → the **same 404**; any transition except `active → cancelled/resolved`
(including repeats and crossing between terminal states) → **409** with a
plain-language message and an unchanged record; a missing coordinate pair,
an out-of-range latitude/longitude, a blank or >500-char `description`, or
any injected server-controlled field (`user_id`, `status`, `id`,
`created_at`, `cancelled_at`, `resolved_at`, `location_recorded_at`) →
**422**.

Phase 6 (reports) error behaviour: every report route without a valid
bearer token → **401**; a report that does not exist **or** is
`rejected`/hidden → the **same 404** (no way to probe hidden reports); an
unknown `category`, a blank/overlong `description`, a missing or
out-of-range coordinate, an injected server-controlled field (`user_id`,
`status`, `id`, timestamps), `status=rejected` as a filter, `limit` outside
1–100, `offset` < 0, or a `radius_m` outside 1–50000 (meters) → **422**;
an integrity failure while saving → **409**.

Phase 6 second assignment (verification/social) error behaviour: any
verification/admin/social route without a valid bearer token → **401**; a
non-owner (or an owner reviewing their OWN request) → **403**/**409**
respectively; a nonexistent or already-decided verification request →
**404**/**409**; submitting while `pending` or `verified`, or re-approving
a decided request → **409**; an injected server-controlled field on any
strict body (`status`, `role`, `verification_status`, `user_id`, an
unknown policy field, a non-boolean `requires_verification`, a >200-char
note, a bad queue `?status=` filter, `limit` outside 1–100, `offset` < 0)
→ **422**; unverified/pending/rejected accounts on a gated social route
while the policy requires verification → **403** with a status-specific
message; a 6th policy change within an hour → **429**.

Phase 7 (travel buddies) error behaviour: every travel route without a
valid bearer token → **401**; discovery/public-profile/send/accept/reject
without passing the same social gate → **403**; a nonexistent plan, a plan
that is not yours, a recipient that is hidden/has no profile/failed the
live policy, or a request you are not a party to → privacy-preserving
**404** (identical to "does not exist"); creating a second profile,
sending a duplicate `pending`/`accepted` request in either direction,
moving a non-`pending` request, patching a plan's dates into an inverted
range, or deleting a plan a request references → **409**; a self-request,
an injected server-controlled field (`user_id`, `status`, `score`,
timestamps), an unknown closed-set value, malformed dates, `min_score`
outside 0–100, `limit` outside 1–100, or `offset` < 0 → **422**; more
than 30 request sends per user per hour → **429** (in-process limiter,
same caveat as the owner policy limiter).

**Proposed for future phases — NOT IMPLEMENTED, do not call these:**
`POST /ai/companion/messages`.
*(A report workflow now exists at `/api/v1/reports` — §12 — but it only
stores and searches rows; every report is an unverified user submission,
nothing is moderated, and filing one notifies no one. An SOS workflow
exists at `/api/v1/sos` — §11 — but it too only stores rows; nothing about
it notifies anyone.)*
Refresh tokens, password reset, and email verification are also **not**
implemented. (To be formalized with the owner during Phase 9 frontend
alignment.)

## 6. Database design — IMPLEMENTED (Phase 2)

Schema is real and now spans Phase 2 + Phase 3 + Phase 4 + Phase 5 +
Phase 6 + Phase 6 second assignment + Phase 7 migrations, all applied to
`roamlary_dev`:

- `cc78d54068bb` — "initial schema" (Phase 2): the five tables below.
- `d9841015aec7` — "add password_hash to users" (Phase 3): adds a nullable
  `password_hash` (varchar 255) to `users`. Full rationale in §9.10.
- `ccd362671e07` — "add contact relationship, checkin note, cancelled status"
  (Phase 4): adds nullable `trusted_contacts.relationship` (varchar 50) and
  `check_ins.note` (varchar 500), and relaxes the `check_ins` status CHECK
  constraint to allow `cancelled`. Full rationale in §10.4.
- `0dd8995649b4` — "add sos description, location timestamp, cancelled
  status" (Phase 5): adds nullable `sos_events.description` (varchar 500),
  `sos_events.location_recorded_at`, and `sos_events.cancelled_at`
  (timezone-aware), and relaxes the `sos_events` status CHECK constraint to
  allow `cancelled`. Full rationale in §11.4.
- `ab32047c8481` — "add community report category check" (Phase 6): adds
  the `ck_community_reports_category_valid` CHECK constraint so
  `community_reports.category` becomes a closed 6-value set
  (`unsafe_area`, `harassment`, `suspicious_activity`, `road_hazard`,
  `poor_lighting`, `other`). The **upgrade** is guarded (refuses while any
  out-of-set category exists); the **downgrade** just drops the constraint
  (always data-safe). Full rationale in §12.4.
- `3e285edb0896` — "add identity verification foundation" (Phase 6 second
  assignment): adds two NOT NULL `users` columns with one-time server
  defaults (`verification_status` default `unverified`, `role` default
  `user`, each with a CHECK constraint) plus three new tables
  (`identity_verifications` request history with `user_id`/`reviewed_by`
  RESTRICT FKs, `app_settings` keyed runtime config with a unique index,
  `setting_changes` append-only audit). The **upgrade** needs no data
  guard (new columns are backfilled to the secure defaults; no existing
  value can violate the new CHECKs); the **downgrade** is guarded and
  refuses while any verification/setting/audit row or any non-default
  user state/role exists. Full rationale in §13.4.
- `426dcef31e27` — "add travel profiles, travel plans and travel-partner
  requests" (Phase 7): adds the three tables below. `travel_plans` and
  `travel_partner_requests` carry named CHECK constraints mirroring their
  Python enums, RESTRICT foreign keys (requests reference `users` twice
  plus the optional context `travel_plans` row), and two **partial UNIQUE
  indexes** that keep at most one PENDING request per direction of a user
  pair (racing identical sends lose at the database). The **upgrade**
  needs no data guard (new tables; nothing existing can violate them); the
  **downgrade** is data-guarded like Phases 4–6 and refuses while any
  travel profile, plan, or partner request exists. Full rationale in
  §14.4.

| Table | Purpose | Owner / deletion rule |
|---|---|---|
| `users` | Account profile (UUID PK, `firebase_uid` nullable+unique, `display_name`, `email` nullable+unique, `password_hash` nullable, `verification_status` ∈ unverified/pending/verified/rejected, `role` ∈ user/owner, timestamps) | — |
| `trusted_contacts` | Nominated safety contact (`name`, `phone`, `relationship` nullable, `email` nullable) | `users` · `ON DELETE RESTRICT` |
| `check_ins` | "Ping me by time T" (`status` ∈ pending/safe/needs_help/expired/**cancelled**, `due_at`, `note` nullable, `completed_at`) | `users` · `ON DELETE RESTRICT` |
| `sos_events` | **Simulated** incident (`status` ∈ active/acknowledged/resolved/false_alarm/**cancelled**, lat/lon, `description` nullable, `location_recorded_at`, `resolved_at`, `cancelled_at`) | `users` · `ON DELETE RESTRICT` |
| `community_reports` | Crowd-sourced note (`category` ∈ 6-value Phase 6 set, `description`, lat/lon, `status` ∈ pending/approved/rejected) | `users` · `ON DELETE RESTRICT` |
| `identity_verifications` | One row per verification **request** (`status` ∈ pending/approved/rejected, `applicant_note` nullable, `review_note` nullable, `reviewed_at`/`reviewed_by` nullable) — history, never edited by clients | `users` (applicant + reviewer) · `ON DELETE RESTRICT` |
| `app_settings` | Runtime configuration (currently the single key `social_requires_verification`; unique index on `key`) | `users` (`updated_by` nullable) · `ON DELETE RESTRICT` |
| `setting_changes` | Append-only audit of policy changes (`setting_key`, `old_value` nullable, `new_value`, `changed_by`) | `users` · `ON DELETE RESTRICT` |
| `travel_profiles` | One travel identity per account (Phase 7): optional `travel_nickname`/`bio`/`home_region`, JSON preference lists (`languages`, `travel_styles`, `interests`), `group_size_pref` (CHECK 2–12), `discoverable` (default hidden) | `users` · `ON DELETE RESTRICT` · **UNIQUE `user_id`** |
| `travel_plans` | One trip intention per row (Phase 7): `destination` + `destination_normalized`, optional `region` + `region_normalized`, `start_date`/`end_date` (CHECK end ≥ start), `flexible_dates`, `status` ∈ active/paused/completed, `visibility` ∈ private/discoverable | `users` · `ON DELETE RESTRICT` |
| `travel_partner_requests` | "A wants to travel with B" (Phase 7): `status` ∈ pending/accepted/rejected/cancelled, optional `plan_id` context (the RECIPIENT's plan), `responded_at` nullable; CHECK no self-request + status set; 2 partial UNIQUE pending-pair indexes (per direction) | `users` (requester + recipient) + `travel_plans` (optional context) · `ON DELETE RESTRICT` |

All Phase 4 and Phase 5 schema changes were additive and nullable — no
existing row was altered or dropped (verified by downgrade→re-upgrade on
`roamlary_dev`, §10.5 and §11.5). The reverse direction is **guarded, not
assumed**: a downgrade now refuses while any `cancelled` check-in (Phase 4,
§10.15) or `cancelled` SOS incident (Phase 5, §11.4) exists rather than
alter data. Phase 6's change is one **added CHECK constraint** whose
*upgrade* carries the same discipline: it refuses (before any schema
change) while any pre-existing out-of-set category exists rather than
convert or delete those rows (§12.4); its downgrade only drops the
constraint and therefore cannot lose data. Phase 7 adds **three new
tables** (nothing existing is altered or dropped); its downgrade follows
the same discipline — it refuses (before any schema change) while any
travel profile, plan, or partner request exists (§14.4).

Status values are enforced by CHECK constraints; lat/lon are range-guarded;
`community_reports.category` is a closed set enforced by a CHECK
constraint (Phase 6).
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
*(Post-approval update: the owner later reviewed the audit round and said
"commit and push it" — it became commit `f26536e`, pushed to `origin/backend`.)*

### 9.14 Phase 3 audit & fix round (owner-assigned verification)

The owner assigned a fix-and-verify pass over Phase 3 *after* it was
committed (`3d728ac`). This section records what the audit found, what was
changed, and the actual results. Everything below was written while it sat
in the **uncommitted working tree** on top of `3d728ac`.
*(Post-approval update: committed as `f26536e` after the owner's sign-off —
see §9.14.6.)*

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
| 6 | `report.md` contradictions: Phase 3 still labeled "in progress"/"uncommitted" although committed as `3d728ac` and pushed; Phase 1/2 records lacked post-approval commit annotations; stale "Phase 1 scope" docstring in `config.py`. | Doc | Corrected in this round (§2, §3, §4, §7.8, §8.13, §9.13, §9.14, §10, §11 + `config.py` docstring). Historical commits were **annotated, never rewritten**. *(Note: "§10, §11" here means Known limitations / Pending tasks **as numbered at that time**; inserting the Phase 4 record as §10 shifted them to §11/§12 in the Phase 4 round, and inserting the Phase 5 record as §11 shifted them again — §10 is the Phase 4 record, §11 the Phase 5 record. Inserting the Phase 6 record as §12 shifted them once more: **Known limitations is now §13, Pending tasks §14**. Inserting the **Phase 6 (second assignment)** record as §13 (2026-10-12) shifted them a final time: **Known limitations is §14, Pending tasks §15**. Inserting the **Phase 7** record as §14 (2026-10-13) shifted them once more: **Known limitations is §15, Pending tasks §16**.)* |

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

- At the time of writing, HEAD was still `3d728ac` (Phase 3 commit) — **no
  commits, pushes, merges, resets, or branch changes were made during this
  audit round**, per the owner's rule. All audit changes sat in the working
  tree for review (`git diff`).
  *(Post-approval update: the owner reviewed the delta and said "commit and
  push it" — it was committed as `f26536e` ("Phase 3 audit: strict auth
  schemas, timing equalization, fail-closed precheck") and pushed to
  `origin/backend`. Verified during the Phase 4 preflight: branch `backend`,
  HEAD `f26536e`, clean tree.)*
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

## 10. Phase 4 record — Trusted contacts & safety check-ins ✅

### 10.1 Phase information

| Item | Value |
|---|---|
| Assigned by | Project owner (Phase 4 brief: trusted contacts + safety check-ins) |
| Branch | `backend` (verified in preflight; never changed) |
| Base commit | `f26536e` (Phase 3 audit) |
| Git state after the phase | **Uncommitted working-tree changes only** — the owner's Phase 4 rules forbid commits/pushes during the phase (confirmed with `git status` / `git diff`, §10.14) |
| Migrations | one new: `ccd362671e07` — applied to `roamlary_dev`, verified `alembic current` → `ccd362671e07 (head)` |
| Phase 3 dependency gate | **PASS** — before any Phase 4 code was written, the full 84-test suite was re-run green against SQLite + real PostgreSQL, and register/login/JWT/profile behaviour was verified against actual code (§10.8) |
| Tests added | 40 (37 endpoint tests + 3 PostgreSQL integration tests) |
| Full suite after the phase | **124 passed**, 0 failed, 0 skipped |
| Status | **COMPLETE (implemented + tested)**; SOS/notification/AI workflows remain **planned** for their own phases |

### 10.2 What was built, in plain language

Two capabilities were added on top of the existing architecture (same DB
session, same `get_current_user` dependency, same error format, same
`/api/v1` versioning — no new framework, no changes to Phases 1–3 behaviour):

1. **Trusted contacts** — a user can save, list, read, edit, and delete the
   people they'd want reachable in an emergency. Saving stores data only:
   **nothing is sent, no one is notified, and no number is verified.**
2. **Safety check-ins** — a user can create a promise ("I'll be back by
   `<due_at>`"), attach an optional note, and later mark it answered. The
   backend **stores and manages records only**: an overdue check-in triggers
   no alert, no notification, and no SOS — by design (§10.13).

The owner's open design question from Phase 3 ("what happens when a
check-in deadline passes?") was answered by the Phase 4 brief itself:
**nothing happens automatically in Phase 4.** Deadlines are stored; expiry
handling belongs to a later, explicitly designed phase.

### 10.3 Design decisions (agreed against the brief's "suggested" options)

| Question | Decision | Why |
|---|---|---|
| Status lifecycle | Kept the Phase 2 enum `pending`/`safe`/`needs_help`/`expired` and **added `cancelled`** instead of renaming to the brief's suggested `active`/`completed`/`cancelled` | Brief says "use existing model conventions… do not introduce arbitrary states". `pending`≈active, `safe`≈completed; `needs_help` carries real safety meaning that a rename would destroy; a user also needed a way to abandon a check-in |
| Transitions | Only `pending → safe` / `pending → needs_help` / `pending → cancelled`. Every other value — including re-setting the same status — → **409** | "Do not allow completed or cancelled check-ins to be silently reactivated": terminal states are fully locked; there is deliberately **no** reactivate transition |
| `completed_at` | Server clock, set when a check-in first reaches `safe` or `needs_help`; **stays NULL for `pending` and `cancelled`** | `completed_at` = "when the user answered"; cancelling is an abandonment, not an answer. Clients can never supply it |
| `/complete` idempotency | **Idempotent**: already-`safe` → 200 with the record unchanged (`completed_at` preserved from the *first* call); `needs_help`/`cancelled` → **409** | Safe for mobile network retries; `safe` must never overwrite a `needs_help` answer |
| `due_at` ("planned return time") | Field name kept as the Phase 2 `due_at` (no rename migration); must be **timezone-aware and in the future** or → **422**, at create *and* update | Renaming would churn the Phase 2 contract for nothing; a past deadline is a promise broken before it started — rejected loudly, never silently accepted |
| Timestamp format | Input: ISO 8601 **with** `Z` or an offset (`+05:30`); naive timestamps → **422**. Output: always UTC (normalized in the response schema, so the contract holds on both SQLite and PostgreSQL) | Guessing a timezone for a safety deadline could be off by hours |
| Phone normalization | Strip spaces/dashes/parentheses/dots, keep a leading `+`; must then be 7–15 digits. **No country code is assumed or added** | Brief: "do not assume all users have Indian phone numbers"; stored form is exactly what the user wrote, minus separators |
| Cross-user access | Every query filters by the token's user; missing **and** not-owned return the **identical 404** | Avoids leaking which IDs exist (ownership enumeration) |
| `relationship` field | New nullable `String(50)` column; in the model class it is declared **after** the `owner = relationship(...)` line with an explanatory comment | One name for one concept (Python/DB/API all say `relationship`); class-body ordering prevents shadowing SQLAlchemy's `relationship()` |
| Pagination | None — plain arrays, contacts oldest-first, check-ins newest-first (both with `id` tie-break for determinism) | The current API has no pagination convention; adding one here would be unnecessary complexity (documented limitation, §10.11) |
| `note` vs `message` | Column named `note` | Phase 4 sends nothing to anyone, so "note" (a remark) is honest where "message" (implying delivery) is not |

### 10.4 File-by-file change log (Phase 4)

Full standalone review copy: [`PHASE4_CHANGES.md`](PHASE4_CHANGES.md).

**New files (7 + 1 doc):**

| Path | Purpose |
|---|---|
| `app/api/v1/endpoints/trusted_contacts.py` | The 5 contact routes + the shared `_get_owned_contact` 404-or-return helper |
| `app/api/v1/endpoints/check_ins.py` | The 5 check-in routes, the `ALLOWED_TRANSITIONS` state machine, `_get_owned_checkin` |
| `app/api/v1/schemas/trusted_contact.py` | `TrustedContactCreate`/`Update` (strict, `extra="forbid"`, phone/email normalization) + `TrustedContactRead` (approved fields only) |
| `app/api/v1/schemas/check_in.py` | `CheckInCreate`/`Update` (strict, tz-aware + future `due_at` validation) + `CheckInRead` (UTC serializer) |
| `alembic/versions/ccd362671e07_add_contact_relationship_checkin_note_.py` | New migration: 2 columns + status CHECK constraint (cross-dialect `batch_alter_table`) |
| `tests/test_trusted_contacts.py` | 20 contact tests |
| `tests/test_check_ins.py` | 17 check-in tests |
| `PHASE4_CHANGES.md` | Standalone file-by-file change review document |

**Modified files (7):**

| Path | Change | Why |
|---|---|---|
| `app/models/enums.py` | Added `CANCELLED = "cancelled"` (+ mapping docstring) | Required lifecycle state for abandoning a check-in |
| `app/models/trusted_contact.py` | Added nullable `relationship` (String 50) | The brief's optional contact field |
| `app/models/check_in.py` | Added nullable `note` (String 500); CHECK constraint now includes `cancelled` | Optional note + new status |
| `app/api/v1/router.py` | Registered the two new routers | Route exposure (10 new routes) |
| `tests/conftest.py` | Added shared `api_client` fixture + `register_user` helper (SQLite-backed, registers real accounts) | Both new test files need authenticated clients; avoids duplicating the override boilerplate |
| `tests/test_models.py` | Enum assertion now expects `cancelled` too | Legitimate contract update caused by the enum addition |
| `tests/test_postgres_integration.py` | +3 tests: new columns exist & are nullable, values round-trip, `cancelled` passes the CHECK constraint | SQLite-only tests don't prove PostgreSQL compatibility |
| `README.md`, `report.md` | Phase 4 documentation | Mandatory |

**Untouched:** everything under `frontend/`, all Phase 1–3 endpoint behaviour,
`alembic/versions/cc78d54068bb` and `d9841015aec7` (historical migrations were
never edited), `.env`.

### 10.5 Models, schema changes, and migration status

Schema delta (all **additive + nullable**, no data rewritten):

| Object | Change |
|---|---|
| `trusted_contacts.relationship` | new `VARCHAR(50) NULL` |
| `check_ins.note` | new `VARCHAR(500) NULL` |
| `ck_check_ins_status_valid` | dropped + recreated to allow `'cancelled'` (4 → 5 values) |

Migration `ccd362671e07` ("add contact relationship, checkin note, cancelled
status") was generated with `alembic revision --autogenerate`, then hand-
adjusted because autogenerate does **not** compare CHECK constraints:

- Constraint work uses `op.batch_alter_table(...)` so the migration runs on
  **both** PostgreSQL (real `ALTER TABLE`) and SQLite (table rebuild) — plain
  `op.drop_constraint` broke the existing SQLite migration tests.
- Constraint names use the **short logical name** `status_valid`; the project
  naming convention expands it to `ck_check_ins_status_valid`. Passing the
  already-expanded name caused a doubled-prefix failure on first attempt.
- The file was corrected after first being applied, so it was **re-run to
  prove the committed file reproduces the live schema**: `downgrade` to
  `d9841015aec7` (columns confirmed gone) → `upgrade head` (columns +
  5-value constraint confirmed back). Final: `alembic current` →
  **`ccd362671e07 (head)`** on `roamlary_dev`.
- The file is self-contained: the naming convention is copied into it rather
  than imported, so it can never break when app code changes later.
- **Downgrade data-safety (added in the §10.15 fix round):** `downgrade()`
  counts `cancelled` check-ins **before** any schema change and refuses
  (clear error, nothing modified) while any exist — the round-trip above is
  valid exactly because the dev database had **0** check-ins at the time.

Verified on the real database with `\d` / `information_schema` queries —
never by assuming the migration output. Integration tests use the disposable
`roamlary_test` database only; `roamlary_dev` was left with **0 users, 0
contacts, 0 check-ins, 0 SOS events** after verification (§10.8).

### 10.6 Endpoints, validation rules, and examples

All routes: **Bearer token required** (missing/invalid/expired → 401) and
`user_id` is always taken from the token — request bodies are strict
(`extra="forbid"`), so an injected `user_id`, `id`, `status` (on create), or
`completed_at` is a **422**, never an override.

**Trusted contacts** — `POST/GET /api/v1/trusted-contacts/`,
`GET/PATCH/DELETE /api/v1/trusted-contacts/{contact_id}`

```json
POST /api/v1/trusted-contacts/          → 201
{ "name": "Asha", "phone": "+91 98765 43210",
  "relationship": "mother", "email": "asha@example.com" }

200 response (approved fields only):
{ "id": "…", "user_id": "…", "name": "Asha", "phone": "+919876543210",
  "relationship": "mother", "email": "asha@example.com",
  "created_at": "…", "updated_at": "…" }
DELETE → 204 (no body); deleting never touches the user, other contacts,
         or check-ins (test-proven)
```

Field rules: `name` 1–80 chars, non-blank after trim (**required**);
`phone` **required**, normalized per §10.3; `email` optional (`EmailStr`,
trimmed+lowercased); `relationship` optional ≤50 chars (blank → `NULL`).
Missing name/phone → 422. Listing returns only the caller's contacts,
oldest first.

**Check-ins** — `POST/GET /api/v1/check-ins/`, `GET/PATCH
/api/v1/check-ins/{checkin_id}`, `POST /api/v1/check-ins/{checkin_id}/complete`

```json
POST /api/v1/check-ins/                 → 201
{ "note": "north trail hike", "due_at": "2026-10-12T18:30:00Z" }

200 response (approved fields only):
{ "id": "…", "user_id": "…", "status": "pending", "note": "north trail hike",
  "due_at": "2026-10-12T18:30:00Z", "completed_at": null,
  "created_at": "…", "updated_at": "…" }
```

- `status` starts `pending` (server-chosen); `GET /check-ins?status=pending`
  filters (unknown value → 422); ordering newest-first.
- `PATCH` may change `note`, `due_at` (still future/tz-aware), and `status`
  (transition rules §10.3). `note`/`due_at` edits are refused **409** once the
  check-in is answered; `id`, `user_id`, `created_at`, `completed_at` cannot
  be sent (422).
- `POST …/complete`: `pending` → `safe` + `completed_at = server now`;
  repeat while `safe` → 200 unchanged (idempotent); `needs_help`/`cancelled`
  → 409. No SOS, no notification, no claim that anyone was told.
- An empty `PATCH {}` is a valid no-op (200, `updated_at` untouched).

### 10.7 Commands executed (Windows PowerShell, from `backend/`)

```powershell
# Preflight: branch, HEAD, tree, container, migration head
git branch --show-current; git log --oneline -4; git status --short
docker ps --filter name=roamlary-postgres-dev
.venv\Scripts\python -m alembic current

# Phase 3 dependency gate (84 tests before any Phase 4 code)
$env:ROAMLARY_TEST_DATABASE_URL = "<roamlary_test URL, value never printed>"
.venv\Scripts\python -m pytest tests/ -q

# Migration (autogenerate → hand-fix CHECK constraint → apply → verify)
.venv\Scripts\python -m alembic revision --autogenerate -m "add contact relationship, checkin note, cancelled status"
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic downgrade d9841015aec7   # proves reversible with 0 check-ins (guard added in §10.15)
.venv\Scripts\python -m alembic upgrade head             # re-apply committed file
docker exec roamlary-postgres-dev psql -U roamlary -d roamlary_dev -c "\d check_ins"

# Tests + lint (final)
.venv\Scripts\python -m pytest tests/ -q
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format .

# Live end-to-end against roamlary_dev (script in the system temp dir,
# deleted after use): 28/28 checks, then removed its own rows
.venv\Scripts\python -u <temp>\phase4_e2e.py
```

### 10.8 Actual test results (2026-10-12, real output)

| Run | Result |
|---|---|
| **Full suite** (offline + PostgreSQL integration enabled) | **124 passed** in 22.4 s — 0 failed, 0 skipped *(at Phase 4 close; the §10.15 fix round later raised this to **128**)* |
| Phase 4 new tests only | 37 passed (20 contacts + 17 check-ins) |
| New PostgreSQL integration tests | included in the 10 PG tests above (7 from Phase 3 + 3 new) |
| Regression Phases 1–3 | all green inside the same 124 — health, models, migrations, DB ops, auth (36), profiles (13), PG integration |
| `ruff check .` | *All checks passed!* |
| `ruff format --check .` | *42 files already formatted* |
| **Live E2E (real PostgreSQL, full app stack)** | **28/28 checks passed**: health contract unchanged, contact CRUD + phone normalization (`+91 98765 43210` → `+919876543210`), cross-user GET/PATCH/DELETE all 404, injected `user_id` → 422, check-in create/complete/idempotency, past & naive `due_at` → 422, `cancelled` lifecycle, 0 SOS rows, cleanup verified |
| Migration on SQLite | `tests/test_migrations.py` → **3 passed** (upgrade *and* downgrade cross-dialect) *(grew to **5** with the §10.15 fix round)* |

Blocked tests: **none** — every test in the suite ran.

Known in-phase failures that were **fixed** (recorded honestly): first
migration attempt failed on a doubled constraint-name prefix (rolled back,
then fixed); SQLite migration tests failed on plain `drop_constraint`
(fixed with `batch_alter_table`); a duplicated `drop_column` block broke
downgrade until removed; 4 endpoint-test failures on first run (2 were real
API gaps — UTC response normalization and same-value status lock — 2 were
test bugs). Final state is the all-green table above.

### 10.9 Security & ownership verification

| Check | Result |
|---|---|
| Every contact/check-in route requires a valid JWT | ✅ unauthenticated → 401 (tested per route) |
| `user_id` server-assigned from the token; client-supplied `user_id`/`id`/`status`/`completed_at` rejected | ✅ 422 (tested) |
| Per-query ownership filtering + identical 404 for missing vs foreign | ✅ tested, bodies byte-identical |
| Strict request schemas (`extra="forbid"`) on all 4 new request models | ✅ |
| Malformed UUID path params | ✅ 422 (FastAPI validation) |
| No cross-user leakage in list endpoints | ✅ tested with two accounts |
| Response schemas list only approved fields | ✅ exact-key-set assertions in tests |
| Timestamps never client-controlled for `completed_at` | ✅ server clock; no schema field for it |
| No secrets/SQL/stack traces exposed; no sensitive contact data logged | ✅ error bodies are fixed `detail` strings; `git diff` scanned |
| No SOS/notification side effects | ✅ tests + E2E assert `sos_events` stays empty |

Passing tests are **not** a security audit; this remains a local prototype.

### 10.10 Regression results (Phases 1–3)

All previously passing tests still pass — no behaviour was changed: health
contract byte-identical (asserted in tests **and** live E2E), 36 auth tests,
13 profile tests, model/migration/DB-op tests, and the 7 Phase 3 PostgreSQL
integration tests. The only pre-existing test edited was
`test_status_enums_match_the_contract` (§10.4), which encodes the enum
contract that Phase 4 intentionally extended.

### 10.11 Known limitations & remaining work

**Implemented + tested:** the 10 routes, schema, lifecycle rules above.
**Planned (later phases, deliberately absent):** expiry jobs for overdue
check-ins, any notification/SMS/email, SOS workflows, contact
verification/notification, roles/admin, Firebase, pagination, rate limiting.
Also: no pagination (unbounded lists are fine at prototype scale), `expired`
is unreachable in Phase 4 (only a future job sets it), and overdue check-ins
are stored without any reaction — an overdue check-in is **not** proof of
danger. The Phase 4 migration's `downgrade()` is **data-dependent**: it
refuses while any `cancelled` check-in exists and requires an explicit
data-handling decision first (§10.15); a permitted downgrade also reverts
the `note`/`relationship` column values.

### 10.12 Phase completion checklist (Phase 4 brief)

| Requirement | Status |
|---|---|
| Phase 3 dependency gate verified against code + tests first | ✅ PASS (84 tests green before starting) |
| 5 trusted-contact endpoints, ownership from token | ✅ |
| 5 check-in endpoints incl. `/complete` with documented idempotency | ✅ |
| Input validation, phone normalization, field limits | ✅ |
| Past-time + timezone policies defined, documented, enforced | ✅ (§10.3) |
| Status transitions validated; no silent reactivation | ✅ (409, tested) |
| Migration for the 3 schema changes, applied & verified, history preserved | ✅ `ccd362671e07` |
| 40 required tests written and passing | ✅ 40 + regression |
| README updated (endpoints, examples, rules, timestamps, migration, commands) | ✅ |
| report.md Phase 4 section added; history annotated not rewritten | ✅ this §10 |
| No SOS/notifications/Firebase/AI/frontend work | ✅ (§10.13) |
| No commits/pushes/branch changes during the phase | ✅ (§10.14) |
| Owner-assigned migration-safety fix round (downgrade guard + 4 tests) | ✅ §10.15 |

### 10.13 Scope confirmation

**Not implemented (belongs to later phases):** SOS workflows or emergency
escalation; automated alerts for overdue check-ins; SMS/WhatsApp/email/push
notifications or background jobs; Firebase Authentication; live location
tracking/sharing; community safety reports; AI features; Flutter/frontend
changes; payments; roles/admin. Saving a contact does **not** mean that
contact was notified or verified, and no identity or location was verified.

### 10.14 Git state after Phase 4

- Branch **`backend`** throughout; HEAD still **`f26536e`** (= `origin/backend`);
  **no commits, pushes, merges, resets, or branch switches were made.**
- All Phase 4 work sits in the working tree for review: `git status` /
  `git diff` (7 modified + 8 new files, §10.4; **10 modified** after the
  §10.15 fix round added `tests/test_migrations.py` to the modified set).
- `backend/.env` remains gitignored (never printed/committed); diff scanned —
  no secrets, no unrelated files; `frontend/` untouched.

> **Later (2026-10-12):** after the owner's explicit approval ("commit and
> push"), these Phase 4 files were **committed and pushed to
> `origin/backend` together with Phase 5** — see `git log`. This section
> preserves the review-time state as it stood.

### 10.15 Migration-safety fix round (owner-assigned verification)

Assigned and completed on 2026-10-12, after the owner reviewed Phase 4.
Scope was deliberately narrow: **only** the Phase 4 migration's
`downgrade()`, its tests, and the documentation claims that implied
downgrades always succeed.

**The concern (valid):** `downgrade()` restored the old 4-value CHECK
constraint without checking for existing `cancelled` rows. With such rows
present, PostgreSQL would reject the ALTER mid-migration, and the earlier
"proven reversible" wording (§10.5, §10.7, README) did not establish that
this data-dependent case was handled.

**The fix** — in `ccd362671e07` only (the frozen migrations `cc78d54068bb`
and `d9841015aec7` were not touched; `upgrade()` is unchanged, so the live
schema is unchanged):

1. `downgrade()` first runs `SELECT count(*) FROM check_ins WHERE status =
   'cancelled'` — **before any schema change**.
2. Count > 0 → raise a clear error naming the count, why the old constraint
   cannot accept those rows, the fact that **nothing** was modified, and the
   explicit data-handling decisions available (delete, remap, or keep the
   Phase 4 schema). No records are deleted or converted to force a downgrade.
3. Count = 0 → the original reverse steps run unchanged.

Because the check precedes any DDL, a refusal leaves schema, constraint,
`alembic_version`, and all rows exactly as they were.

**Behaviour proven both ways** (SQLite via the migration-test conventions,
real PostgreSQL via gated integration tests, and live on `roamlary_dev`):

| Situation | Downgrade result | After-state |
|---|---|---|
| ≥1 `cancelled` check-in | **Refused** (exit 1, "Refusing to downgrade migration ccd362671e07 …") | Unchanged: still `ccd362671e07 (head)`, `note`+`relationship` present, 5-value constraint active, the `cancelled` row untouched |
| No `cancelled` check-ins | **Succeeds** | Version `d9841015aec7`, columns dropped; the rows survive (the dropped columns' values do not — reverting a feature reverts its columns) |
| Either case → `upgrade head` | **Succeeds** | Exact Phase 4 schema restored |

**New tests (4):** `test_phase4_downgrade_refuses_when_cancelled_checkins_exist`
and `test_phase4_downgrade_upgrade_roundtrip_without_cancelled_records` in
`tests/test_migrations.py` (SQLite); the same two scenarios as
`test_pg_phase4_downgrade_*` in `tests/test_postgres_integration.py`, where
alembic itself runs against the disposable `roamlary_test` database. A shared
raw-SQL helper (`insert_raw_user_and_checkin` in `tests/conftest.py`) inserts
probe rows bypassing the ORM — the same situation a downgrade faces with
pre-existing data. The existing `test_alembic_downgrade_base_removes_tables`
still passes: a fresh database has no `cancelled` rows, so the guard lets the
downgrade through.

**Actual results (real output, 2026-10-12):**

| Run | Result |
|---|---|
| `pytest tests/test_migrations.py -v` | **5 passed** (3 pre-existing + 2 new) |
| **Full suite** (offline + PostgreSQL) | **128 passed**, 0 failed, 0 skipped (116 offline + 12 PG) |
| `ruff check .` / `ruff format` | clean |
| Live refusal on `roamlary_dev` | probe `cancelled` row inserted → downgrade **exit 1** with the refusal message → verified version still `ccd362671e07 (head)`, columns present, constraint 5-value, probe row still `cancelled` |
| Live normal path on `roamlary_dev` | probe rows deleted → downgrade **exit 0** (columns confirmed gone) → `upgrade head` **exit 0** → `alembic current` = `ccd362671e07 (head)`, columns + constraint back; DB left with **0 users, 0 contacts, 0 check-ins, 0 SOS events** |

**Doc corrections** (the claims that implied unconditional reversibility):
`PHASE4_CHANGES.md` §2.1/data-safety/applied-and-proven/evidence tables,
README's migration bullet (now documents the refusal) + a new Common-problems
row + test counts (124 → 128, 114 → 116, 10 → 12), and this report's §6, §10.5,
§10.7, §10.8 annotations, §10.11 limitation, §10.14 counts. Phase-close
numbers were annotated, not rewritten.

**Git:** no commits, pushes, merges, resets, or branch switches; HEAD still
**`f26536e`**. Working tree now 10 modified + 8 new files (18 total), no
secrets, `frontend/` untouched.

> **Later (2026-10-12):** owner approved commit & push → these 18 files were
> **committed and pushed together with Phase 5** (see `git log`).

## 11. Phase 5 record — SOS & emergency workflow (simulated) ✅

**Assigned by the project owner** with a detailed brief (Sections 1–11),
including a mandatory preflight, an explicit scope list, required tests, and
a hard stop after Phase 5. Same standing rule as Phase 4: **no commits,
pushes, branch changes, resets, or rewrites of history** until review.

**Safety boundary of this phase:** it only *records* SOS incidents
locally. Activating an SOS does **not** contact police, ambulance, or any
emergency number, does **not** notify trusted contacts or nearby users,
and shares no location with anyone. This is not an emergency-response
system.

### 11.1 Mandatory preflight (all gates cleared before any code)

| Gate | Result |
|---|---|
| Branch & path | `C:\Projects\Roamlary`, branch **`backend`** ✓ |
| Existing work preserved | `git status` showed the 18 uncommitted Phase 4/fix-round files → all kept and built on, nothing overwritten ✓ |
| Phase 4 downgrade fix really present | guard read in the actual migration (before any DDL) **and** the SQLite + PostgreSQL tests that assert it — not just docs ✓ |
| Phase 3 auth working | green baseline: **128 passed** (116 offline + 12 PG), 0 failed ✓ |
| Database target identified | `roamlary_dev` at `ccd362671e07 (head)` via the gitignored `.env` (URL never printed); integration tests use the disposable `roamlary_test` ✓ |
| Stop-conditions | none triggered → Phase 5 proceeded |

Also confirmed *before coding* (per the brief's §3): the Phase 2 schema
**already had an `sos_events` table** with `status`, range-guarded lat/lon
and `resolved_at` — so Phase 5 extends it instead of creating a second
SOS model.

### 11.2 Design decisions (documented choices)

| # | Decision | Why |
|---|---|---|
| D1 | Keep the Phase 2 `SosStatus` values; add only `cancelled` | Same precedent as Phase 4's `CheckInStatus`: frozen Phase 2 design is annotated, not rewritten. `acknowledged`/`false_alarm` stay in the enum/CHECK but are **unreachable** (like `expired` for check-ins) — no responder system exists to acknowledge anything |
| D2 | Lifecycle `active → cancelled` / `active → resolved`; both terminal; every other move (repeats, crossings) → **409** | The brief mandates it. SOS transitions are deliberately **not** idempotent, unlike Phase 4's `/complete` — a closed incident's first timestamp is never rewritten |
| D3 | Three new **nullable** columns: `description`, `location_recorded_at`, `cancelled_at` | The Phase 2 table had none of them; all additive, no existing row touched |
| D4 | Exact brief paths `/api/v1/sos` (no trailing slash), unlike Phase 4's `/check-ins/` | Owner-specified paths win; FastAPI redirects the slash variant and the difference is documented in the README |
| D5 | `cancel`/`resolve` accept **no request body** | A client-supplied timestamp cannot even be expressed; both stamps come from the server clock |
| D6 | Transitions use a conditional `UPDATE … WHERE id=… AND status='active'` (compare-and-set) | Race safety: if two requests race, exactly one applies and the loser sees `rowcount == 0` → 409, instead of both overwriting each other |

### 11.3 Model, enum & schema changes

`app/models/sos_event.py` gained:

| Column | Type | Rule |
|---|---|---|
| `description` | VARCHAR(500) NULL | optional; trimmed; blank/whitespace-only rejected with 422 |
| `location_recorded_at` | timestamptz NULL | **server** clock at activation, only when coordinates were sent |
| `cancelled_at` | timestamptz NULL | **server** clock when the user retracted the SOS |

The status CHECK became 5 values (`active`, `acknowledged`, `resolved`,
`false_alarm`, `cancelled`); `app/models/enums.py` gained
`SosStatus.CANCELLED`. Request schema (`SosEventCreate`) is
`extra="forbid"` with both-or-neither coordinates (lat −90…90,
lon −180…180); response schema exposes exactly 11 fields, all timestamps
normalized to UTC (the `_to_utc` serializer pattern from Phase 4).

**One pre-existing assertion changed** (mirrors Phase 4's documented
change): `test_models.py`'s enum contract now expects `cancelled` in
`SosStatus` — no assertion was deleted or weakened.

### 11.4 Migration `0dd8995649b4` & downgrade safety

*upgrade():* adds the three columns, then — hand-written, because
autogenerate does **not** compare CHECK constraints — drops/recreates the
status CHECK to include `cancelled`, via `batch_alter_table` with the
self-contained naming convention and short logical name `status_valid`
(the exact Phase 4 pattern).

*downgrade():* **data-safety guard first** — counts
`sos_events WHERE status='cancelled'` *before any schema change*; if any
exist it raises an actionable `RuntimeError` (same wording shape as the
Phase 4 guard) and **nothing** is deleted, converted, or altered. Only
with zero such rows does it restore the 4-value CHECK and drop the three
columns (a *permitted* downgrade drops those columns' values; the rows
survive — documented).

**Migration-test bookkeeping (annotated, not rewritten):** the Phase 4
migration tests in `test_migrations.py` and `test_postgres_integration.py`
previously upgraded to `"head"`; since `head` now means the Phase 5
revision, they were **pinned to `ccd362671e07`** — their intent is the
Phase 4 migration's behaviour and every assertion is unchanged. Phase 5's
own migration tests are pinned to `0dd8995649b4` for the same reason.

### 11.5 Live verification on `roamlary_dev` (real output, 2026-10-12)

| Step | Result |
|---|---|
| `alembic upgrade head` | `0dd8995649b4 (head)`; all 3 columns present & nullable (checked via `information_schema`) |
| Constraint check | `pg_get_constraintdef` shows all 5 status values incl. `cancelled` |
| Live refusal demo | probe `cancelled` row inserted → downgrade **exit 1** with "Refusing to downgrade migration 0dd8995649b4…" → verified unchanged: still `0dd8995649b4 (head)`, columns present, 5-value constraint active, probe row still `cancelled` |
| Live normal path | probe rows deleted → downgrade **exit 0** → `upgrade head` **exit 0** → `alembic current` = `0dd8995649b4 (head)`; DB left with **0 users, 0 SOS events** (and 0 contacts/check-ins/reports) |
| Live E2E (full app stack vs `roamlary_dev`, temp script deleted after use) | **35/35 functional checks passed**: activation variants & validation (10), ownership/identical-404s (6), lifecycle & 409s (7), 401s on all five routes + invalid token (6), UTC timestamps, health contract. Its 2 users + 2 SOS rows were deleted afterwards; the database was re-verified empty |

Honest note: the E2E script's own two *cleanup-verification* checks first
reported FAIL because the script's `LIKE` pattern still held an old email
domain after a rename — the data itself was correct; an explicit follow-up
`DELETE` removed both rows and the empty database was verified above.

### 11.6 Endpoints, examples, lifecycle & field rules

| Method + Path | Behaviour |
|---|---|
| `POST /api/v1/sos` | 201; owner from the token; `status='active'` server-chosen; optional description/coordinates; `location_recorded_at` stamped only when coordinates were sent |
| `GET /api/v1/sos` | own incidents only (filter **in the query**), newest first (`created_at desc, id desc`) |
| `GET /api/v1/sos/{sos_id}` | own only — missing and foreign IDs return the **byte-identical 404** |
| `POST /api/v1/sos/{sos_id}/cancel` | `active → cancelled` + `cancelled_at`=server clock; no body; anything else → 409 |
| `POST /api/v1/sos/{sos_id}/resolve` | `active → resolved` + `resolved_at`=server clock; no body; anything else → 409 |

```json
POST /api/v1/sos
{ "description": "flat tyre on highway 7", "latitude": 28.6139, "longitude": 77.2090 }

201 — only fields ever returned:
{ "id": "a41c…", "user_id": "9c1d…", "status": "active",
  "description": "flat tyre on highway 7", "latitude": 28.6139,
  "longitude": 77.2090, "location_recorded_at": "2026-10-12T11:05:12Z",
  "created_at": "…", "updated_at": "…", "cancelled_at": null, "resolved_at": null }
```

Field rules: coordinates must be sent **together** (one alone → 422) and
in range; blank/over-500-char description → 422; `user_id`, `status`,
`id`, `created_at`, `updated_at`, `cancelled_at`, `resolved_at`,
`location_recorded_at` are server-controlled — sending any → 422. A failed
transition changes **nothing** (status and both timestamps proven
byte-identical by test). Full client-facing docs: README "SOS incidents".

### 11.7 Tests & actual results (real output, nothing fabricated)

| Run | Result |
|---|---|
| `pytest tests/test_sos_events.py -q` | **24 passed** (auth, activation/validation, ownership/privacy, lifecycle, persistence, safety boundary) |
| `pytest tests/test_migrations.py tests/test_models.py -q` | **15 passed** (7 migrations incl. both Phase 5 downgrade tests + 8 models) |
| **Full suite** (offline + PostgreSQL) | **158 passed**, 0 failed, 0 skipped (**142 offline + 16 PG**) |
| `ruff check .` / `ruff format` | clean, 46 files |
| PostgreSQL integration (disposable `roamlary_test`) | +4 real-PG tests: Phase 5 columns exist & nullable, CHECK accepts `cancelled`, downgrade **refuses** with a cancelled row (schema + record verified unchanged), downgrade→upgrade **roundtrip** without one — plus the 12 pre-existing PG tests |
| Blocked/weakened tests | **none** — no test was deleted or skipped; the two Phase 4 migration tests were re-pinned to their revision (§11.4) and one enum assertion extended (§11.3) |

Fixed during the phase and recorded honestly: the first `test_sos_events.py`
run had **1 failure** — a *test bug* (a state snapshot was taken before the
transition it should have guarded); the API itself was correct, and after
the fix the file passes 24/24.

### 11.8 Documentation, scope exclusions & git state

**Docs updated:** README (scope block → Phase 5, new "SOS incidents"
section with endpoint/coordinate/lifecycle tables and examples, migration
bullet for `0dd8995649b4`, test counts 158/142/16, three new Common-problems
rows), this report (§2, §3, §4, §5, §6 + this §11; Known limitations and
Pending tasks **renumbered to §12/§13** with the reference at §9.14's
finding annotated), and the new **`PHASE5_CHANGES.md`** standalone review
file (14-row inventory, migration proof, test results, git state).

**NOT implemented (per the brief's scope list):** SMS/WhatsApp/email/push
notifications (Twilio, AiSensy), calls to emergency numbers, real dispatch,
trusted-contact notification, community reports/nearby-user alerts, AI risk
analysis, background location tracking, camera/microphone monitoring,
Flutter/frontend changes, Phase 6+.

**Git:** no commits, pushes, merges, resets, stashes, or branch switches;
HEAD still **`f26536e`** (= `origin/backend`). Working tree now
**11 modified + 13 new = 24 files** (Phase 4's 18 + Phase 5's 6), no
secrets, `frontend/` untouched.

> **Later (2026-10-12):** owner reviewed and approved ("Commit and push
> Phases 4+5") → all 24 files were **committed as one commit and pushed to
> `origin/backend`**; working tree clean afterwards. See `git log`.
> *(Numbering note: inserting the Phase 6 record as §12 later shifted
> Known limitations / Pending tasks to §13 / §14.)*

## 12. Phase 6 record — Community safety reports & location search ✅

### 12.1 Mandatory preflight (all gates cleared before any code)

| Gate | Result |
|---|---|
| Branch / HEAD / tree | `backend` · `f602505` (= `origin/backend`) · clean before Phase 6 ✓ |
| One anomaly found first | `PHASE5_CHANGES.md` had a stray keyboard-mash fragment on line 250 (accidental input, not content) → restored to the committed state and reported to the owner; tree clean again ✓ |
| Migration baseline | `alembic current` → `0dd8995649b4 (head)` ✓ |
| Green baseline | full suite **158 passed** (142 offline + 16 PG), ruff clean ✓ |
| Existing report artifacts | table `community_reports` exists since Phase 2 (`cc78d54068bb`); `ReportStatus` enum exists; **no** schemas, endpoints, or router entries exist → nothing to duplicate ✓ |
| Phase 0–5 architecture read | conventions re-verified against actual code: strict `extra="forbid"` schemas, token-only identity, identical-404 helper pattern, `Annotated[..., Query(alias=...)]` filters, UTC serializer, `batch_alter_table` migrations, PG-gated integration tests ✓ |
| Known conflict points | none destructive: Phase 2's model comment explicitly said *"categories are a Phase 6 product decision"* — the deferred decision is this phase's to make ✓ |

### 12.2 Summary of the implementation & design decisions

Travelers can now file location-based safety reports and search reports
for an area. Everything reuses the Phase 2 `community_reports` table —
**no new tables, no duplicate models** — and adds exactly one CHECK
constraint. Decisions (brief-compatible options chosen and documented):

| # | Decision | Rationale |
|---|---|---|
| D1 | **Closed category set** — new `ReportCategory` StrEnum with 6 values + DB CHECK (two-layer validation like status/lat-lon) | The Phase 2 model explicitly deferred this product decision to Phase 6; loose strings would let `theft`/typos through the DB layer |
| D2 | **No moderation exists → no owner lifecycle endpoints**; `status` is server-set `pending`; visibility = `status != 'rejected'` everywhere | The brief allows only actions the existing design permits, and that design reserves `status` for a future moderation system with roles (adding roles here was explicitly out of scope). Hiding-by-`rejected` is implemented *and tested* now, so the day moderation lands nothing else must change |
| D3 | **Privacy: `user_id` stored, never returned** — public read schema is a closed 8-field set | Accountability/abuse follow-up needs the submitter in the table; public responses must not expose who filed a report (reports are about places, not people) |
| D4 | **Coordinates required on create** (range-checked at schema 422 *and* DB CHECK) | A location-based report without a location is useless; Phase 2 left the columns nullable for other reasons, so the API layer enforces presence |
| D5 | **Paths `/api/v1/reports`** (no trailing slash, `/nearby` declared before `/{report_id}`); **plain-array responses**; **offset/limit pagination** (0≤offset, 1–100 limit, default 20, stable `created_at desc, id desc`) | Follows the most recent path convention (Phase 5), route order prevents `nearby` being parsed as a UUID, arrays match every other list response in this API, pagination is new but bounded per the brief |
| D6 | **Nearby = plain SQL haversine in meters** (Earth radius 6,371,000 m; radius 1–50000 m), **no PostGIS** | The container has no PostGIS and adding a major infra dependency for a hackathon is unjustified; haversine is wrap-safe at the antimeridian, accurate at high latitudes, and correct for city-scale radii |
| D7 | `status` filter accepts only `pending`/`approved`; `?status=rejected` → 422 | "Hidden" must not be a queryable filter value |

### 12.3 File-by-file change log (files created and modified)

**Created (5):**

| File | What it contains |
|---|---|
| `alembic/versions/ab32047c8481_add_community_report_category_check.py` | the one Phase 6 migration (upgrade-side data guard + CHECK) |
| `app/api/v1/schemas/community_report.py` | `ReportCreate` (strict, 4 required fields) + `ReportRead` (8-field, identity-free, UTC) |
| `app/api/v1/endpoints/community_reports.py` | 4 routes: create, list (filters+pagination), nearby (haversine), get-by-id |
| `tests/test_reports.py` | 28 endpoint tests |
| `PHASE6_CHANGES.md` | standalone review inventory (owner-facing) |

**Modified (10):**

| File | Change |
|---|---|
| `app/models/enums.py` | `+ ReportCategory` (6 values); `ReportStatus` docstring documents the no-moderation reality |
| `app/models/community_report.py` | `+ category_valid` CHECK constraint; Phase 6 docstring (visibility + privacy) |
| `app/api/v1/router.py` | register the reports router (+1 import, +1 include) |
| `tests/conftest.py` | `+ insert_raw_user_and_report` raw-SQL probe helper |
| `tests/test_migrations.py` | `+2` SQLite tests (upgrade guard refusal, upgrade/downgrade/upgrade roundtrip) |
| `tests/test_postgres_integration.py` | `+3` real-PostgreSQL tests (constraint enforcement, upgrade guard, roundtrip) |
| `tests/test_models.py` | `+2` tests (`ReportCategory` contract, category CHECK exists in metadata) |
| `tests/test_db_operations.py` | sample category `lighting` → `poor_lighting` (same assertion strength; the old sample is now rejected by the DB — see §12.9) |
| `README.md` | Phase 6 scope block, new "Community safety reports" section, migration bullet, counts 193/174/19, 4 new troubleshooting rows |
| `report.md` | this §12 + PART 1 status updates |

**Deliberately untouched:** `frontend/`, all other endpoint/schema files,
`app/core/*`, older migrations (historical — never edited), `.env`
(gitignored, never printed).

### 12.4 Database & migration details

Migration **`ab32047c8481`** ("add community report category check",
revises `0dd8995649b4`) — hand-written, because Alembic autogenerate does
not compare CHECK constraints:

- **`upgrade()` guard first (the Phase 4/5 discipline, mirrored to the
  upgrade direction):** counts rows whose `category` is outside the 6
  values *before any schema change*. The Phase 2 schema allowed **any**
  string, so legacy rows may exist; creating the CHECK against them would
  fail mid-migration (or tempt a silent convert/delete). Instead it
  raises `RuntimeError: Refusing to upgrade migration ab32047c8481: …
  data-handling decision …` — nothing is altered, the database stays at
  `0dd8995649b4`. Only when all rows are in-set does
  `batch_alter_table` add `ck_community_reports_category_valid`
  (cross-dialect, short logical name expanded by the naming convention).
- **`downgrade()`** drops the constraint — dropping a CHECK can neither
  lose nor alter stored data (every category value survives; the loose
  Phase 2 rules return), so this direction is unconditionally safe and
  deliberately carries **no** guard.
- **Reversibility reviewed:** upgrade = refuse-or-add (data-protected);
  downgrade = always-safe drop; roundtrip proven on SQLite **and** real
  PostgreSQL (§12.9), and live on `roamlary_dev` (§12.10).
- No rows, columns, or tables were deleted anywhere; no production
  database was touched (only `roamlary_dev` + disposable `roamlary_test`).
- `alembic current` on `roamlary_dev` → **`ab32047c8481 (head)`**.

### 12.5 API endpoints and request/response examples

| Method + path | Purpose | Success / errors |
|---|---|---|
| `POST /api/v1/reports` | File a report (identity from token; `pending` server-chosen) | `201` · `401` no/invalid token · `422` validation/injection · `409` integrity |
| `GET /api/v1/reports` | Visible reports, newest first; `?category=`, `?status=pending\|approved`, `?offset=`, `?limit=` | `200 [ReportRead]` · `401` · `422` |
| `GET /api/v1/reports/nearby` | Required `latitude`, `longitude`, `radius_m` (meters); optional `category`, `offset`, `limit`; nearest first | `200 [ReportRead]` · `401` · `422` |
| `GET /api/v1/reports/{report_id}` | One visible report | `200` · `404` missing **or** rejected (identical) · `401` |

Create request → response (the only 4 accepted request fields; the
response is the closed 8-field public shape — note **no `user_id`**):

```json
POST /api/v1/reports  →  HTTP 201
{ "category": "poor_lighting", "description": "dark street behind the station",
  "latitude": 28.6139, "longitude": 77.2090 }

{ "id": "3f6a1c2e-…", "category": "poor_lighting", "status": "pending",
  "description": "dark street behind the station",
  "latitude": 28.6139, "longitude": 77.2090,
  "created_at": "2026-10-12T14:03:11Z", "updated_at": "2026-10-12T14:03:11Z" }
```

Nearby search (radius unit is **meters**, bounded 1–50000):

```
GET /api/v1/reports/nearby?latitude=28.61&longitude=77.20&radius_m=2000
Authorization: Bearer <token>
→ 200 [ReportRead, …]  nearest first
```

Field rules: `category` ∈ the 6 values; `description` required, trimmed,
1–500 chars (blank → 422); both coordinates required (lat −90…90, lon
−180…180); `user_id`/`status`/`id`/timestamps injected → 422; timestamps
always UTC. Filters: `status=rejected` or unknown → 422; `limit` 1–100
(default 20), `offset` ≥ 0. Full client-facing docs: README's
"Community safety reports (Phase 6)".

### 12.6 Location-search method and limitations

**Method: a basic latitude/longitude distance query — the haversine
formula computed in SQL** (parameterized; Earth radius 6,371,000 m),
**not** a geospatial index and **not** PostGIS:

```
distance = 2·R·asin( √( sin²(Δlat/2) + cos(lat₁)·cos(lat₂)·sin²(Δlon/2) ) )
```

- **Unit & bounds:** `radius_m` in **meters**, required, `0 < r ≤ 50000`
  (50 km max — beyond that "nearby" stops being about the traveler).
- **Antimeridian:** the formula uses trig of the half-difference, and
  trig is 360°-periodic — reports at lon `179.9` and a center at
  `-179.9` compute as ~22 km apart, not ~39,980 km (proven by test and
  live check).
- **High latitudes:** no flat-map/equirectangular approximation is used,
  so accuracy holds at 78°N (proven by test and live check).
- **Rounding safety:** `a` is clamped to ≤1 before `asin()` so rounding
  at antipodal points can never push the query into a domain error.
- **NULL coordinates:** rows without coordinates can't match a distance
  expression and are skipped cleanly (test-covered).
- **Practical limitations (documented, not hidden):** scans the whole
  table (**O(n)**, no index — fine for thousands of rows, revisit before
  real traffic), spherical-vs-ellipsoidal Earth error is **<1%** at city
  scale, results are capped/paginated (limit ≤ 100), and ordering ties
  break by `created_at DESC, id DESC`.
- **Why no PostGIS:** not present in the `postgres:16-alpine` container,
  and a major infrastructure dependency is not justified for this
  prototype — documented rather than silently assumed.

### 12.7 Authentication, ownership, privacy and moderation behavior

- **Auth:** all 4 routes require a valid bearer token (401 without one or
  with a garbage token — tested on every route).
- **No impersonation:** the submitter comes only from the verified JWT;
  `user_id` in a body/query is structurally impossible (`extra="forbid"`
  → 422, injection-tested).
- **Ownership:** reports have **no owner actions to authorize** — reads
  are community-wide by design, and no `PATCH`/`DELETE`/status endpoint
  exists, so there is no mutation surface to guard (scope-faithful: the
  brief permits only lifecycle actions the existing design allows, and it
  reserves `status` for moderation). Ownership is still stored server-side
  for accountability (test asserts `user_id` in the table).
- **No self-verified reports:** `status` is absent from the create schema
  (422 on injection) and set to `pending` in server code; nothing in the
  API can produce `approved`.
- **Honest trust framing:** every response carries `status`, so clients
  (and users) can always distinguish an unverified `pending` submission
  from an `approved` one — the API never claims a place is dangerous or
  safe. `rejected` rows are hidden from list/nearby/get with an
  identical-404, and hidden is not filterable.
- **Privacy:** the read schema has exactly 8 fields — no `user_id`, no
  email, no phone, no auth data (exact-field-set assertions + a
  two-account identical-view test).
- Parameterized ORM statements only; query bounds on radius/limit/offset;
  no logging added (no tokens, coordinates, or secrets logged); **no rate
  limiting yet** (documented limitation).

### 12.8 Commands executed (Windows PowerShell, from `backend/`)

```powershell
# Preflight: branch, HEAD, tree, migration head
git branch --show-current; git log --oneline -3; git status --porcelain
.venv\Scripts\python -m alembic current

# Lint + format (run after every file change)
.venv\Scripts\python -m ruff format . ; .venv\Scripts\python -m ruff check .

# New tests first, then migration/model tests, then the FULL suite
# (ROAMLARY_TEST_DATABASE_URL derived from .env — value never printed)
.venv\Scripts\python -m pytest tests/test_reports.py -q
.venv\Scripts\python -m pytest tests/test_migrations.py tests/test_models.py -q
.venv\Scripts\python -m pytest tests/ -q

# Migration applied to roamlary_dev + constraint verified via psql
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current

# Live E2E (temp script in the system temp dir, deleted after run) and the
# live migration-guard demo: downgrade → seed out-of-set row → upgrade
# (refused, exit 1) → verify unchanged → delete seed → upgrade (exit 0)
```

### 12.9 Tests & actual results (real output, nothing fabricated)

| Run | Output |
|---|---|
| `pytest tests/test_reports.py -q` | **28 passed** |
| `pytest tests/test_migrations.py tests/test_models.py -q` | **19 passed** |
| Full suite (SQLite + PostgreSQL, 2026-10-12) | **193 passed**, 0 failed, 0 skipped (174 offline + 19 PG) |
| `ruff format .` + `ruff check .` | no changes needed · **All checks passed!** |
| Coverage of the brief's test list | creation+retrieval, missing/invalid auth, invalid category/description/coordinates/radius/pagination, owner-vs-non-owner (public reads + no-mutation surface), category & status filters, nearby inside/outside radius, antimeridian + high-latitude boundaries, pagination & max limits, public-response privacy, Phases 1–5 regression (full suite), migration safety on SQLite **and** PG — all present ✓ |
| Blocked / skipped tests | **none** (the 19 PG tests ran against the disposable `roamlary_test` database; skipped ≠ passed, and nothing was skipped) |
| Pre-existing test adjusted | `test_db_operations.test_community_report_created_pending` used the loose sample category `lighting`, which the new DB CHECK now rejects → sample updated to `poor_lighting` with the assertion kept at exact-match strength; documented in `PHASE6_CHANGES.md` §6.5 (no assertion deleted or weakened) |
| Honest failure record | first live E2E run: **49/51** — both failures were *script-expectation bugs* (an offset page computed past the end of the data; a nearest-first assertion that forgot a closer report existed). The API behaved correctly; after fixing the script's expectations: **51/51** |

### 12.10 Live verification on `roamlary_dev` (real output, 2026-10-12)

- **E2E via the full app stack** (temp script, deleted after use):
  **51/51 checks passed** — health contract, registration, creation of all
  6 categories, validation rejections (unknown/blank/overlong/coords/
  injections), exact-field privacy (no identity key anywhere), two-account
  identical views, newest-first ordering, category/status filters,
  pagination bounds + default cap, rejected-hidden semantics with
  byte-identical 404s, nearby inside/outside/antimeridian/high-latitude +
  Python haversine cross-check of distances & ordering, radius bounds,
  401s on all routes; its own rows/users deleted afterwards and the
  database **verified empty** (0 users / 0 reports / 0 SOS rows).
- **Live migration-guard demo** (transcript summarized): `downgrade` to
  `0dd8995649b4` (exit 0) → raw `'theft'` row inserted → `upgrade head`
  **refused** (exit 1, `Refusing to upgrade migration ab32047c8481: …
  data-handling decision …`) → verified unchanged: version
  `0dd8995649b4`, `category-constraint-count=0`, probe row intact →
  demo row deleted (explicit data-handling decision) → `upgrade head`
  exit 0 → `ab32047c8481 (head)`, constraint present, DB empty.

### 12.11 Known limitations & follow-up work

- **No moderation:** every report stays `pending` forever;
  `approved`/`rejected` are unreachable via the API (roles/dashboard are a
  later, owner-assigned phase). `rejected`-hiding works but can only be
  triggered from the database today.
- **No owner lifecycle:** submitters cannot edit/delete their own reports
  (no `PATCH`/`DELETE` by this phase's scope).
- Nearby search scans the table (no index/PostGIS), radius ≤ 50 km,
  spherical Earth (<1% error at city scale).
- Pagination exists **only** on reports; contact/check-in/SOS lists remain
  unbounded; no `total` count in report responses (arrays only).
- No rate limiting/abuse controls on report creation yet.
- Passing tests are **not** a security audit or a production claim — this
  remains a local hackathon prototype.

### 12.12 Scope confirmation — no real alerts or external notifications

**Confirmation: Phase 6 implemented NO real emergency alerts and NO
external notifications of any kind.** Explicitly **not** built: SMS /
WhatsApp / email / push notifications (Twilio, AiSensy), calls to
emergency numbers, real dispatch, trusted-contact notification,
nearby-user alerts, community alerting, any AI (Phase 7), background
tracking, camera/microphone, moderation/roles/dashboard, PostGIS or other
new infrastructure, Flutter/frontend changes (`frontend/` untouched), and
no commits/pushes/branch switches (HEAD still `f602505`). Filing a report
**only writes a row**; searching reports **only reads rows**.

### 12.13 Documentation updated & git state

**Docs:** README (Phase 6 scope block, new "Community safety reports"
section with endpoint/category/visibility/nearby tables, migration bullet
for `ab32047c8481`, counts 193/174/19, four new Common-problems rows),
this report (§2, §3, §4, §5, §6 + this §12; Known limitations and Pending
tasks **renumbered to §13/§14** with the §9.14 note annotated), and the
new **`PHASE6_CHANGES.md`** standalone review (15-row inventory, migration
proof, test results, scope list, git state).

**Git:** no commits, pushes, merges, resets, stashes, or branch switches
**during the phase**; HEAD stayed **`f602505`** (= `origin/backend`).
Working tree: **10 modified + 5 new = 15 files** (all Phase 6), no
secrets, `frontend/` untouched.

> **Later (2026-10-12):** the owner instructed "commit and push" → the
> 15-file Phase 6 change set was **committed and pushed to
> `origin/backend`** (see `git log`); the working tree is clean. Note for
> the record: every push of this branch has always carried the **whole
> repository tree** — `backend/`, `frontend/` (27 tracked Flutter files
> since the initial commit `4761b41`), and `.gitignore`. The on-disk
> `docs/` folder is **empty**, and git cannot track or push an empty
> directory (nothing was lost — it never had contents).

## 13. Phase 6 (second assignment) record — Identity verification & social access foundation ✅

### 13.1 Mandatory preflight (audit + gaps/plan before any code)

Audited the whole repository before writing anything:

- **Zero pre-existing infrastructure** for verification, roles, policy, or
  gates: no such columns, tables, enums, endpoints, schemas, CLI, or
  tests anywhere (`users` had neither `verification_status` nor `role`;
  no `identity_verifications`/`app_settings`/`setting_changes` tables).
- **Baseline test suite: 193 passed** (the exact Phase 6 number) before
  the first edit.
- Identified gaps and planned the file set (models → migration →
  policy/rate-limit core → schemas → gates → endpoints → CLI → router →
  tests → docs), then asked the owner the two design questions this
  brief left open.

**Owner answered before any code was written:**

1. *Gated surface* → **one placeholder route**
   (`GET /api/v1/social/discovery`: empty `profiles` + honest "Phase 7"
   message) instead of pretending discovery exists.
2. *Owner provisioning* → **`users.role` column + server-side CLI**
   (`python -m app.cli make-owner <email>`), the only path that grants
   `owner` — no API surface for privilege changes.

### 13.2 Summary of the implementation & design decisions

- **Two kinds of state, kept apart on purpose.** *Account state* lives on
  the user (`users.verification_status`, `users.role`) — what you ARE
  right now. *Request history* lives in `identity_verifications` — what
  you ASKED and what the owner DECIDED. Conflating them would let a
  client "edit history"; keeping them apart means history rows are
  append-only facts.
- **Exactly four account states** — `unverified / pending / verified /
  rejected` — and three request states — `pending / approved / rejected`.
  Two separate enums (not one shared "status") because an account being
  `verified` and its request being `approved` are different words for a
  reason; one shared enum would allow nonsense combinations to compile.
- **Every write is server-chosen.** Submitting sets `pending`; only the
  owner's approve/reject sets `verified`/`rejected` (request →
  `approved`/`rejected`), always in the **same transaction** as
  `reviewed_at`/`reviewed_by`. Any client-supplied
  `status`/`role`/`verification_status`/`user_id` is **422** (strict
  schemas, `extra="forbid"`), with the DB CHECKs as a second layer.
- **No self-service elevation anywhere:** no route, body, profile field,
  or header can set a state or role; a reviewer (even the owner) cannot
  decide their own request (**409**); registration always creates
  `role="user"`.
- **Owner role via CLI only** (behind shell access to the database
  machine — the strongest boundary the project has). No email-list, no
  registration-order, no hardcoded credentials, no secret answers.
- **The gate is a reusable server-side dependency** (`require_verified_user`
  in `deps.py`), applied to a real (placeholder) endpoint — not
  copy-pasted per route. `require_owner` similarly gates all four admin
  routes with an exact role match (unknown/corrupt role → denied, never
  elevated).
- **Policy is runtime configuration in the database** (`app_settings`
  row), because it must be changeable without a restart and audited.
  `get_policy()` **fails closed**: missing/corrupt/unreadable → "verification
  required". Read live on every gated request (no stale JWT claim).
- **Policy changes are owner-only, validated, rate-limited (5/hour/owner,
  in-process), and audited** (`setting_changes`: who/when/old→new, same
  transaction; first write audits `old_value=NULL`; no-op writes touch
  nothing). A policy change **never** verifies anyone or rewrites
  history.
- **Safety/account workflows stay open while unverified** — the gate is
  applied ONLY to the social placeholder; a dedicated test proves
  contacts/check-ins/SOS/profile/verification routes all still work.
- **No identity data, anywhere.** The submit body accepts at most an
  optional ≤200-char note; no schema, column, fixture, log line, or doc
  contains Aadhaar/ID numbers or document fields (a live check asserts no
  identity-document columns exist).
- **`UserProfile` (Phase 3) untouched** — verification state is exposed
  only via `GET /verification/status`, so existing clients are unaffected;
  **auth/JWT untouched** — role and status are read live from the
  database on each request, so a token never carries stale privileges.
- **`server_default`s on both new columns** (`unverified`, `user`) so the
  ORM, raw-SQL inserts, and Alembic backfill all agree — a Python-only
  default leaves raw SQL failing on NOT NULL (caught during testing).
- Statuses `expired` / `requires_review` were **deliberately deferred**
  (the brief fixes the state set; adding states later is a migration).

### 13.3 File-by-file change log (files created and modified)

**Created (15):**

| File | What it contains |
|---|---|
| `alembic/versions/3e285edb0896_add_identity_verification_foundation.py` | the one migration (2 columns + 3 tables; downgrade data guard) |
| `app/models/identity_verification.py` | request-history model (`identity_verifications`) |
| `app/models/app_setting.py` | runtime-config model (`app_settings`, unique key) |
| `app/models/setting_change.py` | append-only audit model (`setting_changes`) |
| `app/core/policy.py` | `get_policy()` (fail-closed) + `set_policy()` (audited, transactional) |
| `app/core/rate_limit.py` | in-process fixed-window limiter (policy PATCH 5/hour/owner) |
| `app/api/v1/schemas/verification.py` | 7 strict schemas (submit, summaries, status, review, policy) |
| `app/api/v1/schemas/social.py` | `DiscoveryResponse` (empty list + honest message) |
| `app/api/v1/endpoints/verification.py` | 2 routes: status (own only), submit request |
| `app/api/v1/endpoints/admin.py` | 4 owner routes: queue, approve, reject, policy read/patch |
| `app/api/v1/endpoints/social.py` | 1 gated placeholder: discovery |
| `app/cli.py` | `python -m app.cli make-owner <email>` (exit 0/1, no secrets printed) |
| `tests/test_verification.py` | 20 endpoint tests (states, gate, no self-verify, workflows stay open) |
| `tests/test_admin.py` | 19 endpoint tests (queue, review, policy, audit, rate limit, fail-closed) |
| `PHASE6_IDENTITY_CHANGES.md` | standalone review inventory (owner-facing) |

**Modified (11):**

| File | Change |
|---|---|
| `app/models/enums.py` | + `VerificationStatus` (4), `VerificationRequestStatus` (3), `UserRole` (2) |
| `app/models/user.py` | + `verification_status`/`role` columns (NOT NULL, CHECKs, secure `server_default`s) + request-history relationship |
| `app/models/__init__.py` | + 3 model imports/registrations |
| `app/api/v1/deps.py` | + `require_owner`, `require_verified_user` (status-specific 403s), `OwnerUser`/`SocialUser` aliases |
| `app/api/v1/router.py` | + 3 router registrations (7 new routes; OpenAPI verified) |
| `tests/conftest.py` | + `insert_raw_user_and_verification` raw-SQL probe helper |
| `tests/test_migrations.py` | +4 tests (columns/CHECKs, downgrade guard refusal, roundtrip) + expected-tables +3 |
| `tests/test_models.py` | +4 tests (enum contracts, user CHECKs in metadata) + expected-tables +3 |
| `tests/test_postgres_integration.py` | +5 real-PostgreSQL tests (CHECK enforcement, guard refusal, roundtrip) |
| `README.md` | new "Identity verification & social gate" section, scope block, eight-tables list, migration bullet, counts 245/221/24, +8 troubleshooting rows |
| `report.md` | this §13 + PART 1 updates (§2/§3/§4/§5/§6/§9.14 note; old §13/§14 renumbered to §14/§15) |

**Deliberately untouched:** `frontend/`, `app/core/security.py` and the
whole auth/JWT flow, `UserProfile`, SOS/report/check-in/contact endpoints,
all older migrations (historical — never edited), `.env` (gitignored,
never printed).

### 13.4 Database & migration details

Migration **`3e285edb0896`** ("add identity verification foundation",
revises `ab32047c8481`) — hand-written:

- **`upgrade()` — deliberately unguarded (unlike Phase 4/5/6):** adds
  `users.verification_status VARCHAR(20) NOT NULL` (CHECK ∈ the 4 values,
  `server_default 'unverified'`) and `users.role VARCHAR(10) NOT NULL`
  (CHECK ∈ `user`/`owner`, `server_default 'user'`), then creates
  `identity_verifications`, `app_settings` (unique index on `key`), and
  `setting_changes`. No data guard is *needed*: the columns are new, so
  every existing row is backfilled to the secure defaults in the same
  statement that adds the column — no pre-existing value can violate the
  new CHECKs (the opposite situation from Phase 6's category CHECK, where
  legacy *data* could violate a *new constraint*).
- **`downgrade()` — guarded first (Phase 4/5 discipline):** counts
  verification requests, policy rows, audit rows, and users with a
  non-default state/role *before any schema change*; if anything exists it
  raises `RuntimeError: Refusing to downgrade migration 3e285edb0896: 4
  verification request(s), 1 setting row(s), 2 audit row(s) and 3 user(s)
  with a non-default verification state or role exist … no schema changes
  were made …` (the census is live, the numbers above are from the real
  run). Dropping the columns/tables underneath that data would orphan it,
  so the refusal forces an explicit data-handling decision instead.
- **Ownership/privacy at the schema layer:** both FKs on
  `identity_verifications` (`user_id`, `reviewed_by`) are `ON DELETE
  RESTRICT` (history and reviewer identity can never silently vanish);
  `user_id` is indexed; `app_settings.updated_by` and
  `setting_changes.changed_by` are RESTRICT FKs too.
- **Applied to `roamlary_dev`** (`alembic current` → `3e285edb0896
  (head)`), refused-downgrade + clean roundtrip demonstrated live
  (§13.10), roundtrip also proven on SQLite **and** real PostgreSQL
  (§13.9). No production database was touched (only `roamlary_dev` +
  disposable `roamlary_test`).

### 13.5 How verification, roles & policy work (plain language)

1. **You sign up** → `unverified`, `role=user` — chosen by the server,
   not you.
2. **You ask for verification** (`POST /verification/requests`, optional
   short note — nothing else is collected) → your account becomes
   `pending` and a history row appears, atomically.
3. **The owner reviews** (`GET /admin/verification-requests`, oldest
   first) and approves or rejects → your account becomes `verified` or
   `rejected`; the row remembers who decided, when, and their note.
   Rejected? You may submit again (that's a new row; the old one stays as
   history).
4. **Social features check a live switch:** `get_policy()` reads
   `app_settings` on every request. Switch on (the default) → only
   `verified` accounts pass; anyone else gets a 403 that says exactly
   where they stand and what to do. Switch off (owner's choice, audited
   and rate-limited) → everyone authenticated passes. Missing/corrupt
   switch → treated as ON (fail closed).
5. **Nothing else changes:** your trusted contacts, check-ins, SOS, and
   profile keep working the whole time — verification only guards social
   features.

### 13.6 API endpoints and request/response examples

| Method + path | Purpose | Success / errors |
|---|---|---|
| `GET /api/v1/verification/status` | Caller's OWN status + role + live policy + latest request | `200` · `401` |
| `POST /api/v1/verification/requests` | Submit (optional `{"note": "≤200 chars"}`) | `201` · `401` · `409` already pending/verified · `422` |
| `GET /api/v1/admin/verification-requests` | Queue, oldest first; `?status=pending\|approved\|rejected`, `?offset=`, `?limit=` | `200` · `401` · `403` not owner · `422` |
| `POST /api/v1/admin/verification-requests/{id}/approve` | Request → `approved`, account → `verified` (optional `review_note`) | `200` · `401` · `403` · `404` · `409` not-pending/own-request · `422` |
| `POST /api/v1/admin/verification-requests/{id}/reject` | Request → `rejected`, account → `rejected` (same errors) | `200` · `401` · `403` · `404` · `409` · `422` |
| `GET /api/v1/admin/policy/social-verification` | Effective policy + `updated_at`/`updated_by` | `200` · `401` · `403` |
| `PATCH /api/v1/admin/policy/social-verification` | `{"requires_verification": bool}` — audited, rate-limited | `200` · `401` · `403` · `422` · `429` |
| `GET /api/v1/social/discovery` | **Gated placeholder**: empty list + Phase 7 message | `200` · `401` · `403` (status-specific) |

The full happy path, exercised live (§13.10):

```text
POST /api/v1/verification/requests          (applicant, {"note": " trip organiser "})
→ 201 { "id": "…", "status": "pending", "applicant_note": "trip organiser",
        "review_note": null, "reviewed_at": null,
        "created_at": "2026-10-12T17:40:02Z" }

GET  /api/v1/admin/verification-requests?status=pending   (owner)
→ 200 [ { "id": "…", "user_id": "…", "display_name": "Live Applicant",
          "status": "pending", "applicant_note": "trip organiser",
          "reviewed_at": null, "reviewed_by": null, "review_note": null,
          "created_at": "…" } ]

POST /api/v1/admin/verification-requests/{id}/approve     (owner)
→ 200 { …, "status": "approved", "reviewed_by": "<owner user id>",
        "reviewed_at": "…" }
   (applicant's GET /verification/status now says "verified")

GET  /api/v1/social/discovery               (verified applicant)
→ 200 { "profiles": [],
        "message": "Travel-buddy discovery is not implemented yet
                    (planned for Phase 7+) …" }
```

Field rules: submit accepts **only** an optional `note` (≤200, trimmed,
blank collapses to none) — injected `status`/`user_id` → 422; register
with `role` → 422; profile PATCH with `role`/`verification_status` →
422; queue `?status=` outside the 3 values → 422, `limit` 1–100
(default 20), `offset` ≥ 0; policy body must be exactly one boolean →
otherwise 422; the 6th accepted-policy-attempt within an hour → 429.
Full client-facing docs: README's "Identity verification & social gate".

### 13.7 Authorization, privacy & audit behavior

- **401 everywhere** without a valid bearer token (all 7 routes).
- **403 owner gate:** all four `/admin/*` routes for any role ≠ `owner`
  (exact match — corrupt/unknown role is denied, never elevated).
- **403 social gate** with actionable, status-specific text (unverified →
  "submit a verification request first (POST /api/v1/verification/
  requests)"; pending → "under review"; rejected → "you may submit a new
  one"; corrupt status → generic fail-closed message).
- **Ownership/privacy on verification records:** the status route has no
  user-id parameter at all (structurally cannot read someone else);
  applicant-facing summaries expose 6 fields without `user_id`/`display_
  name`; `user_id`+`display_name`+`reviewed_by` appear **only** in
  owner-gated queue/review responses (exact-field-set asserted by tests);
  no email or password hash appears in any verification response.
- **Self-review refused for everyone** (409, owner included) — verified
  live: the owner's own submitted request stayed `pending` and
  unverified.
- **Compare-and-set review update** (re-assert `pending` in the WHERE
  clause) so two racing reviewers cannot double-decide.
- **Audit:** every accepted policy change appends `setting_changes`
  (who/when/old→new) in the same transaction; the first-ever change
  audits `old_value=NULL`; no-op changes append nothing; review outcomes
  record `reviewed_at`/`reviewed_by` alongside the decision.
- **No hardcoded credentials / no secrets in output:** the CLI prints only
  email + role result (live-checked: output contains no `DATABASE_URL`);
  no token, password, or secret appears in any new file (diff reviewed).

### 13.8 Commands executed (Windows PowerShell, from `backend/`)

```powershell
# Migrations (real roamlary_dev; DATABASE_URL only from gitignored .env)
.venv\Scripts\python -m alembic upgrade head            # -> 3e285edb0896 (head)
.venv\Scripts\python -m alembic current
.venv\Scripts\python -m alembic downgrade ab32047c8481  # guard demo (exit 1 with data); later exit 0 clean

# Server-side owner provisioning (the only owner-grant path)
.venv\Scripts\python -m app.cli make-owner <email>      # exit 0; unknown email -> exit 1

# Tests + lint (ROAMLARY_TEST_DATABASE_URL derived from .env, never printed)
.venv\Scripts\python -m pytest                          # 245 passed, 0 failed, 0 skipped
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .

# Live verification against the dev server on 127.0.0.1:8000
.venv\Scripts\python <temp E2E script>                  # 54/54; a second run in "cleanup" mode -> 1/1
```

### 13.9 Tests & actual results (real output, nothing fabricated)

| Run | Output |
|---|---|
| `pytest --collect-only -q` | **245 collected** (193 baseline + 52 new) |
| `pytest tests/test_verification.py -q` | **20 passed** |
| `pytest tests/test_admin.py -q` | **19 passed** |
| Full suite (SQLite + real PostgreSQL via `ROAMLARY_TEST_DATABASE_URL`) | **245 passed, 0 failed, 0 skipped** in 120.83s (221 offline + 24 PG) — final run after all documentation edits |
| `ruff check .` / `ruff format --check .` | All checks passed! / 64 files already formatted |
| Blocked/skipped tests | **none** — 0 skipped; no skipped test is ever counted as passed |

New tests by file (52 = 20 + 19 + 4 + 4 + 5):

| File | New | Covers |
|---|---|---|
| `tests/test_verification.py` | 20 | default state + gate on; status auth/shape; **no self-verify** via register/profile/submit (422); submit → pending (atomic), duplicate/verified 409, resubmit-after-rejection; per-status discovery 403s; **owner role does NOT bypass gate**; verified passes after real approval; **safety/account workflows stay open while unverified**; no cross-user leak via status |
| `tests/test_admin.py` | 19 | admin auth 401/403; queue oldest-first + exact shape + filter/pagination bounds; approve/reject recording reviewer identity; 404 unknown; 409 invalid transitions; **409 self-review (owner included)**; reject visible to applicant; **policy default on**; **audit who/when/old→new**; no-op writes nothing; 422 invalid bodies; **rate limit 429**; **no auto-verify/rewrite on policy change**; policy off/on flips the gate; **corrupt policy fails closed** |
| `tests/test_migrations.py` | +4 | columns exist with CHECKs + secure defaults; **downgrade guard refuses with data**; clean roundtrip; expected tables +3 |
| `tests/test_models.py` | +4 | three enums' exact values; both `users` CHECKs in metadata; expected tables +3 |
| `tests/test_postgres_integration.py` | +5 | role/status CHECK enforcement on real PG (bogus value → `IntegrityError`); downgrade guard refusal with data; clean downgrade→upgrade roundtrip |

Every requirement the brief listed is covered by named tests above —
including the fail-closed policy read, the audit-row content, the rate
limit, the no-self-verification paths (request/profile/client value), the
safety-workflow exemption, and the ownership/privacy checks; none of them
is skipped or xfailed.

**Fixed during the phase (recorded honestly):** one intermediate full-suite
run showed "221 passed, 24 errors" — all 24 errors were *setup* errors in
my one-off PowerShell command, which had left a stray `=` at the front of
`ROAMLARY_TEST_DATABASE_URL` (an off-by-one while parsing `.env`). The
tests themselves were fine; with the variable parsed correctly the final
run is the 245/0/0 above. No application code or test was changed to
obtain it.

**Checks NOT performed (honest difference):** no real identity provider
or external API of any kind; no email/SMS/push delivery (none claimed);
no multi-process rate-limit behaviour (single dev process only); no load
or penetration testing; no frontend integration; tests ran only against
SQLite (fast), disposable `roamlary_test` (integration), and the local
`roamlary_dev` server (live E2E).

### 13.10 Live verification on `roamlary_dev` (real output, 2026-10-12)

A `--reload` dev server was already running on `127.0.0.1:8000`
(`python -m uvicorn app.main:app --reload`, started earlier that day; it
had reloaded into the current code — its OpenAPI listed all 7 new routes
and unauthenticated calls returned 401 as designed). A second uvicorn I
launched to be independent exited immediately because the port was
already held, so **all live checks ran against that existing server**,
which serves the same code and the same `roamlary_dev` database.

- **Health contract exact:** `{"status": "ok", "service":
  "roamlary-backend", "version": "1.0.0"}`.
- **Live E2E (stdlib `urllib`, no extra dependencies): 54 passed, 0
  failed.** Highlights: three accounts registered (each new account
  `unverified`/`user`/gate-required); unverified denied discovery with
  status-specific guidance; anonymous discovery/admin → 401; submit →
  `pending` with trimmed note; duplicate submit 409; injected
  `status`/`role` on register/profile/submit → 422; ordinary user → 403
  on the whole admin surface; CLI `make-owner` exit 0 **without printing
  `DATABASE_URL`**, unknown email exit 1; owner role visible while
  verification stays `unverified`; owner role does NOT bypass the social
  gate; queue shape + "no email/password in queue"; approve records
  `reviewed_at`/`reviewed_by` and flips the account to `verified`;
  re-approve 409, unknown id 404; second applicant rejected → denied →
  allowed to resubmit; owner's own request stays `pending` (self-review
  impossible); bad queue filter/limit → 422; policy off opens the gate,
  policy on closes it again; invalid policy body → 422; **rate limit:
  exactly 5 allowed then 429 (attempt #8)**; unverified accounts can
  still trigger SOS, save a contact, and file a report; **no
  identity-document columns exist**.
- **First E2E attempt failed — a bug in my script, not the app:** the
  script passed a header dict where a raw token string was expected,
  sending `Authorization: Bearer {'Authorization': …}` (invalid JWT →
  401). A standalone probe proved register → `/users/me` → login →
  local decode with the `.env` secret all work; I fixed the script's
  `call()` helper (no application code changed) and the run was 54/54.
- **Live migration-guard demo (data present):** `alembic downgrade
  ab32047c8481` → **exit 1** with *"Refusing to downgrade migration
  3e285edb0896 (add identity verification foundation): 4 verification
  request(s), 1 setting row(s), 2 audit row(s) and 3 user(s) with a
  non-default verification state or role exist … no schema changes were
  made …"*. Verified unchanged immediately after: `alembic current` still
  `3e285edb0896 (head)`; counts identical (4/1/2/5).
- **Clean roundtrip:** my test data deleted (scoped to this run's own
  `live-*` accounts + their policy/audit rows) → `alembic downgrade
  ab32047c8481` **exit 0** → `alembic upgrade head` **exit 0**.
- **Final state:** `alembic current` → `3e285edb0896 (head)`; phase tables
  present and empty (requests 0, settings 0, audit 0); the one
  pre-existing dev row survived with backfilled defaults
  (`unverified`/`user`).
- **Data note (owner was asked):** a single account
  (`user@example.com`) appeared in `roamlary_dev` during setup at 22:22
  (origin unknown to me; zero dependent data, untouched since creation).
  The owner chose **"leave it, adapt the E2E"** — so all isolation and
  cleanup checks were scoped to this phase's own `live-*` data, that row
  was never touched, and it is honestly reflected in the final counts
  above.

### 13.11 Known limitations & follow-up work

- Manual review only — no real identity provider; "verified" = an owner
  read a short note. No ID data is (or may ever be, in this prototype)
  collected.
- Single-owner deployments cannot API-approve the owner's own account
  (self-review refused by rule) — needs a second reviewer or a deliberate
  server-side action.
- Rate limiter is in-process (resets on restart, per-process) — revisit
  before multi-process deployment.
- No `expired`/`requires_review` states; no client UI (Phase 9); no
  verification notifications (none claimed).
- Social surface is a gated placeholder until Phase 7; report moderation
  still untouched (reports stay `pending`-only).
- (Also listed in §15 - Known limitations, renumbered by the Phase 7
  record.)

### 13.12 Scope confirmation — no identity documents, no external services

- ❌ Aadhaar/ID numbers, document uploads, scans, or any sensitive
  identity data — in requests, tables, fixtures, logs, tests, or docs
- ❌ real identity-provider integration (or any external API call)
- ❌ discovery/chat/events/AI implementation — one gated **placeholder**
  route only, per the owner's explicit decision
- ❌ Flutter changes (`frontend/` untouched) · ❌ SOS lifecycle changes
- ❌ report-moderation changes · ❌ email/SMS/push notifications, and no
  claim that anything was delivered
- ❌ self-verification paths of any kind; email/registration-order
  privilege grants; hardcoded credentials
- ❌ commits, pushes, merges, resets, stashes, or branch switches during
  the phase (HEAD stayed `9939515`)

### 13.13 Documentation updated & git state

**Docs:** README (scope block, eight-tables list, new "Identity
verification & social gate" section with states/endpoints/gate/CLI/policy,
migration bullet for `3e285edb0896`, counts 245/221/24, +8 Common-problems
rows, report-moderation clarification), this report (§2, §3, §4, §5, §6 +
this §13; Known limitations and Pending tasks **renumbered to §14/§15**
with the §9.14 note annotated), and the new
**`PHASE6_IDENTITY_CHANGES.md`** standalone review (26-row inventory,
migration proof, test results, scope list, git state).

**Git:** no commits, pushes, merges, resets, stashes, or branch switches
**during the phase**; HEAD stayed **`9939515`** (= `origin/backend`).
Working tree: **11 modified + 15 new = 26 files** (all this phase), no
secrets, `frontend/` untouched. `git status` output recorded at review
time in §13.13's companion doc.

## 14. Phase 7 record — Travel buddies, travel plans & social discovery

### 14.1 Audit findings (recorded BEFORE any code, 2026-10-13)

**Starting state (verified by command):** branch `backend`, HEAD
**`30977c0`** = `origin/backend`, clean tree, no stash. `roamlary_dev` is
at migration head **`3e285edb0896`** (single linear chain of 6
migrations). The UI-integration `test` branch exists (frontend only) and
is **not** part of this phase; `frontend/` remains untouched.

**Confirmed repository facts:**

1. **8 tables exist:** `users`, `trusted_contacts`, `check_ins`,
   `sos_events`, `community_reports`, `identity_verifications`,
   `app_settings`, `setting_changes`. All use `UUIDPrimaryKeyMixin` +
   `TimestampMixin`, named CHECK constraints mirroring Python `StrEnum`s
   (no native PostgreSQL enums), and `ON DELETE RESTRICT` foreign keys.
2. **The dependency rule is satisfied: identity verification EXISTS**
   (Phase 6 second assignment, §13) — the brief's caution that it might
   be absent does not apply to this repository. Confirmed reusable:
   `users.verification_status` + `users.role` (NOT NULL, server
   defaults, CHECKs), the social gate **`require_verified_user`**
   (`deps.py`, live fail-closed policy read via `get_policy`), owner
   review routes, and CLI-only owner provisioning. Phase 7 **reuses this
   gate unchanged** and additionally filters candidate accounts by
   verification status while the policy is on.
3. **No travel/profile/preference/plan/discovery/relationship
   structures exist.** `/social/discovery` is the documented empty
   placeholder whose own docstring promises "Phase 7 replaces this …
   keeping the same gate"; its wire contract (`profiles: []` +
   `message`) must stay compatible for the existing UI.
4. **No blocking/restriction system exists anywhere** → "exclude blocked
   users" reduces to verification + discoverability exclusions
   (documented as a limitation, §14.11).
5. **No destination reference table** → destinations are normalized
   free text; no external verification is claimed.
6. **No background jobs** → expired plans are excluded at READ time
   (`end_date < today`), never by a sweeper.
7. **API conventions confirmed:** `Annotated` query params with
   descriptions; `offset ge=0` / `limit ge=1 le=100` default 20; UUID
   path params return privacy-preserving 404; `IntegrityError → 409`;
   `extra="forbid"` bodies; server-set statuses; identity only from the
   token's `sub`; public responses never include `user_id` of content
   owners.
8. **Testing conventions confirmed:** `api_client` fixture + `register_user`
   helper (offline SQLite), module-level `skipif` PostgreSQL suite with a
   disposable per-test engine, subprocess Alembic tests with
   `EXPECTED_TABLES` + data-guarded downgrade assertions ("Refusing to
   downgrade" / "data-handling decision"), and per-phase raw-insert
   helpers in `conftest.py`.
9. **SQLite compatibility constraint:** the offline suite runs
   `create_all` on SQLite, so list-valued fields must use generic `JSON`
   (JSONB would break it); list-based preference filtering therefore
   runs in the documented secondary-filter stage, not in SQL.
10. **Only abuse control available** is the in-process
    `check_rate_limit` (§13/§14 limitation) — reused for travel-partner
    request creation, with the same documented single-process caveat.

**Gaps and minimum prerequisites (no blockers):** real ID provider
(pre-existing §14 — reused as manual review, unchanged); no shared
rate-limit store (in-process reuse + documented); no blocking system
(out of scope, §12); no destination gazetteer (normalized text +
documented); no scheduler (read-time expiry). **Blockers: none** —
verified-user discovery is implementable now on the existing gate.

### 14.2 Summary of the implementation & design decisions

The owner's brief items map to the shipped surface as follows: travel
profiles → `/travel-profile/me` (one row per account, preference lists,
`discoverable` default **hidden**); travel plans → `/travel-plans` CRUD
with normalized destinations, date CHECKs, `active/paused/completed` and
`private/discoverable`; discovery/matching →
`GET /travel-buddies/discover` (eligibility-aware, scored, paginated)
plus `GET /travel-buddies/{user_id}` (limited public profile); travel
partner requests → send/list/get/accept/reject/cancel with a full state
machine; and `/social/discovery` reimplemented over the same data as a
broad verified-user feed, keeping its `{profiles, message}` contract.

Design decisions (agreed against the brief's "suggested" options):

1. **Reuse, don't rebuild, the verification gate.** Every outward-facing
   action (discovery, public profiles, send, accept, reject) sits behind
   the existing `require_verified_user` dependency with the live
   fail-closed policy read — unchanged since Phase 6 second assignment
   (§13). Managing your own data (profile, plans, reading/cancelling your
   own requests) stays on plain authentication: the social policy can
   never lock a user out of editing or retracting their own records.
2. **Three tables, no new account columns.** `travel_profiles` (1:1 with
   `users`, UNIQUE index), `travel_plans`, `travel_partner_requests`.
   Preference lists are generic `JSON` (not JSONB) so the offline SQLite
   suite's `create_all` keeps working (§14.1.9); list-based preference
   filtering therefore runs as the documented Python secondary-filter
   stage, never in SQL.
3. **Deterministic, explainable scoring — no AI.** `app/core/matching.py`
   is pure functions over stored data; weights are module constants that
   sum to exactly 100 and every response repeats the honesty note (score
   is a logistics ranking, never a safety guarantee).
4. **Read-time expiry.** Plans with `end_date` in the past (UTC) are
   excluded when read; there is no background job (§14.1.6).
5. **Two-layer duplicate protection.** Same-direction racing sends lose at
   the database (partial UNIQUE pending-pair indexes per direction);
   cross-direction duplicates are refused by the endpoint's
   either-direction pre-check (exact boundary documented in §14.4/§14.11).
6. **Privacy-preserving errors.** A recipient that is hidden, has no
   profile, or fails the live policy collapses into the **same 404** as a
   nonexistent account — eligibility can never be probed. Request
   transitions by a non-party also return the identical 404.
7. **One documented deviation from the §14.1.7 convention:** discovery and
   public-profile responses DO include the candidate's `user_id` — the
   brief requires addressing a request to a discovered user, so the id is
   functional data. Everything else stays hidden (email, role,
   verification status, account timestamps, private plans); `user_id` is
   only ever disclosed to callers who already passed the social gate and
   only for users who chose to be discoverable.
8. **Rate limiting where abuse is possible:** sending a request is
   limited to 30/hour/user via the same in-process limiter the owner
   policy uses (same documented single-process caveat).
9. **`/social/discovery` reimplemented, not duplicated:** it now serves
   `broad_feed()` (limit 10, no filters) through the identical gate and
   wire contract, so the Phase 6 UI integration keeps working while
   `/travel-buddies/discover` serves the full feature.

### 14.3 File-by-file change log (files created and modified)

**Created:**

- `app/models/travel_profile.py` — `TravelProfile` (1:1 `users`, JSON
  lists, `group_size_pref` CHECK 2–12, `discoverable` default false).
- `app/models/travel_plan.py` — `TravelPlan` (destination + normalized,
  region + normalized, dates with `end >= start` CHECK, status/visibility
  CHECKs, `ix_travel_plans_discovery` composite + `ix_travel_plans_dates`).
- `app/models/travel_partner_request.py` — `TravelPartnerRequest`
  (no-self-request + status CHECKs, RESTRICT FKs to `users` ×2 and the
  optional context `travel_plans` row, two partial UNIQUE pending-pair
  indexes, `ix_..._recipient_status`/`ix_..._requester_status`).
- `alembic/versions/426dcef31e27_add_travel_profiles_plans_buddy_requests.py`
  — creates the three tables; data-guarded `downgrade()` (§14.4).
- `app/core/matching.py` — pure matching rules: weight constants
  (sum = 100), `FLEXIBLE_DATE_GRACE_DAYS = 7`, closed sets
  (`ALLOWED_TRAVEL_STYLES`, `ALLOWED_INTERESTS`), `normalize_place()`,
  `plan_matches_window()` (strict/flexible/None), `ScoreBreakdown`,
  `score_candidate()`. No clock, no I/O — unit-testable directly.
- `app/services/discovery.py` — `discover()` (indexed SQL prefilter →
  secondary preference filters → precise date classification → scoring →
  per-user dedupe (best plan; ties → earliest start, then id) →
  deterministic sort `(-score, start-ordinal, user_id)` → offset/limit
  page; `MAX_CANDIDATE_ROWS = 500` hard ceiling), `public_profile_for()`,
  `broad_feed()`, and `_request_states()` (per-candidate
  none/pending_sent/pending_received/accepted).
- `app/api/v1/schemas/travel.py` — strict schemas (`extra="forbid"`
  everywhere): profile create/patch/read (with `completion` hints), plan
  create/patch/read (`TravelPlanRead` timestamps optional so discovery
  projections omit them), `DiscoveryCandidateRead`/`DiscoveryPage`
  (honesty `note`), `PublicTravelProfileRead`, request
  create/read/list (`BuddyRequestRead` carries both display names).
- `app/api/v1/endpoints/travel_profile.py` — GET (404 with actionable
  guidance when absent)/POST (409 duplicate)/PATCH/DELETE on
  `/travel-profile/me`.
- `app/api/v1/endpoints/travel_plans.py` — POST/GET list/GET one/PATCH
  (full re-validation of dates against stored values)/DELETE
  (409 via RESTRICT when referenced) on `/travel-plans`.
- `app/api/v1/endpoints/travel_buddies.py` — discover, public profile,
  request send (eligibility + duplicate pre-checks + rate limit),
  list (direction/status filters), get, accept/reject (recipient only,
  verification rechecked at accept), cancel (requester only). Routes are
  declared `/requests` before `/{user_id}` so the literal segment wins.
- `tests/test_matching.py` (14 pure unit tests), `tests/test_travel_plans.py`
  (21), `tests/test_discovery.py` (23), `tests/test_buddy_requests.py`
  (21).

**Modified:**

- `app/models/enums.py` — `TravelPlanStatus`, `PlanVisibility`,
  `BuddyRequestStatus` (VARCHAR-backed + CHECK, project convention).
- `app/models/user.py` — backrefs for the three relationships.
- `app/models/__init__.py` — exports for the three models.
- `app/api/v1/schemas/social.py` — rewritten over the real feed while
  keeping the `{profiles, message}` response contract.
- `app/api/v1/endpoints/social.py` — reimplemented over
  `broad_feed()`; `SocialUser` gate untouched.
- `app/api/v1/router.py` — three new routers registered (33 OpenAPI paths
  total, verified live).
- `tests/conftest.py` — `insert_raw_user_and_travel()` raw-SQL helper
  (dialect-aware boolean literal) for the downgrade-guard tests.
- `tests/test_models.py` — EXPECTED_TABLES +3 and six travel
  metadata/constraint/enum tests (20 total).
- `tests/test_migrations.py` — EXPECTED_TABLES +3 and three Phase 7
  tests (upgrade creates tables + partial indexes; downgrade refuses
  with data present; clean downgrade/upgrade roundtrip) (16 total).
- `tests/test_postgres_integration.py` — six Phase 7 tests (native uuid
  columns + RESTRICT FK census; partial pending-pair index enforced both
  directions with `IntegrityError`; no-self-request and inverted-date
  CHECKs; JSON list roundtrip; PG downgrade guard; PG roundtrip) (30
  total).
- `tests/test_verification.py` — one Phase 6b assertion updated: the
  test that pinned the placeholder message ("Phase 7 will replace…") now
  asserts the shipped honesty message; the gate assertions (403 → 200,
  `{profiles, message}` shape, no fabricated users) are unchanged.
- `README.md`, `report.md` — Phase 7 sections (this record, §2/§3/§4/§5/§6
  rows); new `PHASE7_TRAVEL_BUDDIES.md` review document.

`app/api/v1/deps.py`, auth, config, and the health contract were **not**
touched.

### 14.4 Database & migration details (migration `426dcef31e27`)

Applied to `roamlary_dev` (head = `426dcef31e27`, chain still single and
linear). Additive-only: three new tables, no existing table altered.

- `travel_profiles` — UUID PK, `user_id` FK→users RESTRICT + **UNIQUE
  index** (one profile per account at the database level), optional
  `travel_nickname` (40), `bio` (200), `home_region` (80), JSON
  `languages`/`travel_styles`/`interests`, `group_size_pref` with
  CHECK 2–12, `discoverable` BOOLEAN NOT NULL default false.
- `travel_plans` — UUID PK, `user_id` FK RESTRICT, `destination` (120)
  + `destination_normalized` (NOT NULL, indexed), `region` (80) nullable
  + `region_normalized`, `start_date`/`end_date` with CHECK
  `end_date >= start_date`, `flexible_dates` default false, `status`
  CHECK ∈ active/paused/completed (default active), `visibility` CHECK
  ∈ private/discoverable (default private), composite index
  `(destination_normalized, status, visibility)` matching the discovery
  query shape, plus `(start_date, end_date)`.
- `travel_partner_requests` — UUID PK, `requester_id`/`recipient_id`
  FK→users RESTRICT, CHECK `requester_id <> recipient_id`, `plan_id`
  nullable FK→travel_plans **RESTRICT** (history keeps pointing at a
  real plan; deleting a referenced plan → 409), `status` CHECK ∈
  pending/accepted/rejected/cancelled (default pending), `responded_at`
  nullable, per-direction status indexes, and the two partial UNIQUE
  indexes `(requester_id, recipient_id)` / `(recipient_id, requester_id)`
  WHERE `status='pending'`.

**Exact guarantee of the pending-pair indexes (§14.1 corrected):** each
index locks its own *ordered* pair, so two racing identical sends (A→B
twice, or B→A twice) lose at the database with `IntegrityError` — the
application's read-then-write pre-check is a convenience, not the
source of truth, for that case. The *cross-direction* duplicate (A→B and
B→A both pending) presents different keys to both indexes and is
therefore blocked one layer up by the endpoint's either-direction
pre-check; its residual window (two users clicking send within the same
instant) is documented in §14.11. The model docstring, migration
comment, and tests each state exactly this boundary — no overclaim.

`downgrade()` inspects all three tables first and, while any travel row
exists, raises "Refusing to downgrade … Export or delete this data first
— … a deliberate data-handling decision" **before** touching the schema.
Proven on SQLite (subprocess alembic) and real PostgreSQL, offline and
live.

### 14.5 How matching works (plain language) — and its honesty boundary

`app/core/matching.py` answers "how compatible is this plan with what the
searcher asked for?" using only arithmetic over stored data:

| Signal | Points |
|---|---|
| Destination matches the searcher's `?destination=` filter (normalized) | +40 |
| Region matches the searcher's `?region=` filter instead | +20 |
| Plan overlaps the searcher's date window | +30 strict / +15 via the ±7-day flexible grace |
| Shared declared interests | +5 each, cap 15 |
| Shared travel styles | +5 each, cap 10 |
| Shared language | +5 |

Weights sum to exactly `SCORE_MAX = 100`; `ScoreBreakdown.total` applies
`min(score, 100)` so any future weight change cannot overflow the scale.
The destination/region/date components score **the searcher's stated
intent (filters)** — an unfiltered browse therefore ranks by shared
preferences only (live-verified: unfiltered = 20/100 for a two-interest
fixture; the same fixture filtered by destination+window = 90/100).
Normalization = casefold + whitespace collapse; punctuation is **not**
stripped, so "Goa, India" ≠ "Goa India" as normalized keys (documented
limitation, §14.11). Flexible-date overlap is classified in Python after
a grace-widened SQL window (the SQL is a documented superset; genuine
non-overlaps are dropped precisely before scoring).

**Honesty boundary (unchanged from §14.1, repeated in every response
`note`):** the score is a deterministic convenience ranking of logistics
and stated preferences — it is **not**, and is never presented as, proof
that anyone is safe or that two people will get along. No AI, no external
API, no vector database, no provider is involved anywhere in this phase.

### 14.6 API endpoints and request/response examples

Full route table with gates and error codes: **§5**. Client-facing
version with examples: README "Travel buddies & discovery (Phase 7)".
Representative flow (as run live, §14.10):

```text
POST /api/v1/travel-profile/me   {"travel_nickname": "WandererB", "interests":
 ["hiking","food"], "travel_styles": ["slow_travel"], "languages": ["english"],
 "group_size_pref": 2, "discoverable": true}
→ 201 { "user_id": "…", …, "discoverable": true, "completion": [] }

POST /api/v1/travel-plans/       {"destination": "goa  india", "region": "North
 Goa", "start_date": "2027-01-08", "end_date": "2027-01-12", "visibility":
 "discoverable"}
→ 201 { "id": "…", "destination": "goa india", "status": "active", … }

GET  /api/v1/travel-buddies/discover?destination=goa%20india&start_date=2027-01-05
                                     &end_date=2027-01-15
→ 200 { "total": 1, "offset": 0, "limit": 20,
        "results": [ { "user_id": "…", "display_name": "WandererB",
          "plan": { …, "created_at": null, "updated_at": null },
          "compatibility_score": 90,
          "match_breakdown": { "destination": 40, "dates": 30,
            "interests": 10, "travel_style": 5, "language": 5 },
          "existing_request": "none" } ],
        "note": "Compatibility scores are a deterministic ranking of travel
        logistics and stated preferences - not a guarantee that anyone is
        safe or that two people will get along. Always meet in public and
        tell a trusted contact your plans." }

POST /api/v1/travel-buddies/requests  {"recipient_id": "…", "plan_id": "<B's
 plan id>"}                 → 201 { …, "status": "pending", … }
POST /api/v1/travel-buddies/requests  {"recipient_id": "…"}   → 409 duplicate
POST /api/v1/travel-buddies/requests  {"recipient_id": "<self>"}  → 422
POST /api/v1/travel-buddies/requests/{id}/accept   (recipient) → 200 "accepted"
GET  /api/v1/travel-buddies/discover                (requester) → B gone
GET  /api/v1/social/discovery                       → { "profiles": [ …≤10 ],
                                                       "message": "…" }
```

### 14.7 Eligibility, privacy, authorization & abuse-control behavior

- **Gate matrix:** plain-login = profile CRUD, plan CRUD, list/get/cancel
  own requests; social gate = discover, public profile, send, accept,
  reject. While the policy requires verification, the gated routes return
  403 with the status-specific message (fail-closed, live read — §13).
- **Who can appear in discovery:** discoverable profile + `active`
  `discoverable` plan not yet ended + not you + not an accepted partner +
  not a pending counterparty in either direction + verified while the
  policy requires it. Every condition is enforced in the SQL prefilter
  (indexed columns) or the documented Python stage.
- **Eligibility recheck at accept:** the recipient's verification is
  re-read live when accepting; if it lapsed, the accept returns 409
  ("no longer eligible") and the request stays `pending` — policy can
  never be bypassed by an old request. Discoverability is deliberately
  NOT rechecked at accept (a user who hid after being asked still gets to
  decide on the existing ask; documented).
- **Privacy of projections:** discovery/public profiles omit email, role,
  verification status, account timestamps, and private/inactive plans;
  plan timestamps are omitted there too (`created_at`/`updated_at` are
  optional in `TravelPlanRead` and populated only on owner endpoints).
  No sensitive identity data exists in any Phase 7 table — the brief's
  exclusion is structural, not policy-based.
- **State machine:** pending → accepted|rejected (recipient) or
  pending → cancelled (requester); accepted/rejected/cancelled are
  terminal (further moves → 409). Wrong party → 404 (existence privacy).
  Resending after rejection/cancellation is allowed; a duplicate
  pending/accepted request either direction → 409.
- **Race guarantees:** same-direction duplicates lose at the database
  (partial UNIQUE indexes; proven with raw inserts past the endpoint on
  SQLite **and** real PostgreSQL); self-requests cannot exist (schema 422
  + DB CHECK, both proven); the cross-direction instant-simultaneity
  window is endpoint-guarded and documented (§14.11).
- **Abuse control:** 30 request-sends/hour/user in-process limiter
  (429), the only lever available (§14.1.10). No blocking system exists
  in the product yet (§12) — exclusions are verification +
  discoverability + partner/pending state.

### 14.8 Commands executed (Windows PowerShell, from `backend/`)

```powershell
# Preflight (audit, before any code): branch/HEAD/tree, alembic head,
# table census, route census — recorded in §14.1.

# Lint + format (run after every change)
.venv\Scripts\python -m ruff format app tests
.venv\Scripts\python -m ruff check app tests

# New suites first, then models/migrations, then the FULL offline suite
.venv\Scripts\python -m pytest tests\test_matching.py tests\test_travel_plans.py `
  tests\test_discovery.py tests\test_buddy_requests.py -q
.venv\Scripts\python -m pytest tests -q --ignore=tests\test_postgres_integration.py

# PostgreSQL suite (ROAMLARY_TEST_DATABASE_URL derived from .env — never printed)
.venv\Scripts\python -m pytest tests\test_postgres_integration.py -q

# Migration applied to roamlary_dev + verified
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current

# Live E2E against the restarted dev server (temp script in the system temp
# dir): 24 checks, then removed its own rows and verified the cleanup
.venv\Scripts\python C:\Users\91812\AppData\Local\Temp\opencode\phase7_live_smoke.py
```

### 14.9 Tests & actual results (real output, nothing fabricated)

**94 new tests** (88 offline + 6 real-PostgreSQL), totals now **339**:

| Suite | Before | After | What Phase 7 added |
|---|---|---|---|
| `tests/test_matching.py` (new) | — | 14 | pure-function rules: normalization, window classification (strict/flexible/none), each weight, caps, total cap, closed sets |
| `tests/test_travel_plans.py` (new) | — | 21 | profile lifecycle + 404-guidance + duplicates, plan CRUD, ownership identical-404s, date revalidation, RESTRICT delete 409, auth/gate matrix, strict-schema 422s |
| `tests/test_discovery.py` (new) | — | 23 | gates, eligibility exclusions (hidden/unverified/partner/pending/self/expired/private), scoring + ranking, all filters, dedupe-per-user, pagination + bounds, privacy of projections, public profile, `/social/discovery` contract |
| `tests/test_buddy_requests.py` (new) | — | 21 | full lifecycle, identical-404 privacy, terminal-state 409s, DB-level race/self-request proofs (SQLite + PG), eligibility recheck at accept, rate limit 429, resend-after-reject |
| `tests/test_models.py` | 14 | 20 | EXPECTED_TABLES +3; travel FK/CHECK/UNIQUE/partial-index metadata; enum contracts |
| `tests/test_migrations.py` | 13 | 16 | EXPECTED_TABLES +3; Phase 7 upgrade creates tables + partial indexes; downgrade refuses with data; clean roundtrip |
| `tests/test_postgres_integration.py` | 24 | 30 | native uuid + RESTRICT FK census; partial pending-pair index both directions (`IntegrityError`); no-self-request + inverted-date CHECKs; JSON list roundtrip; PG downgrade guard; PG roundtrip |

Actual results (2026-10-13, real output):

```text
ruff format: 72 files left unchanged          ruff check: All checks passed!
pytest tests -q --ignore=tests\test_postgres_integration.py
→ 309 passed, 3 warnings in 110.64s           (baseline 221 → +88)
pytest tests\test_postgres_integration.py -q
→ 30 passed in 63.07s                         (baseline 24 → +6)
```

The three warnings are the pre-existing StarletteDeprecationWarning for
HTTP 422 (seen since Phase 3-era tests; unrelated to this phase).

One Phase 6b test changed: `test_verified_user_passes_gate_after_owner_approval`
pinned the placeholder message text ("Phase 7 will replace…"). Phase 7
shipped, so the assertion now pins the shipped honesty message ("not a
guarantee"); the gate behavior it actually protects (403 before
approval → 200 after, `{profiles, message}` shape, empty/non-fabricated
profiles) is unchanged and still asserted.

### 14.10 Live verification on `roamlary_dev` (real output, 2026-10-13)

`alembic upgrade head` → `Running upgrade 3e285edb0896 -> 426dcef31e27`;
`alembic current` → `426dcef31e27 (head)`. The dev server was restarted
(old PID killed, new uvicorn serving the Phase 7 code); `/api/v1/health`
returned the **byte-identical pre-Phase-7 contract**
(`{"status":"ok","service":"roamlary-backend","version":"1.0.0"}`) and
the OpenAPI census showed **33 paths** including all twelve Phase 7
routes.

A 24-check live script (two throwaway accounts, owner CLI, policy
toggle) then passed **24/24**:

1. health contract unchanged · 2. make-owner CLI ok · 3. policy normalized
   ON · 4. discover 403 while unverified · 5. absent profile → 404 with
   guidance · 6. owner flips policy OFF · 7–8. both profiles created ·
9–10. both plans created (normalization visible: "goa  india" stored
   lowercase+collapsed) · 11. unfiltered discovery 200 with honesty note ·
   12. preferences-only score 20 with the exact documented breakdown ·
   13. discovery omits timestamps/email · 14. filtered discovery scores
   the full **90** (40 destination + 30 strict + 20 preferences) ·
   15. request sent 201 pending · 16. duplicate → 409 · 17. self-request →
   422 · 18. recipient sees incoming · 19. accept → 200 accepted ·
   20. accepted partner leaves discovery · 21. `/social/discovery`
   contract kept · 22. public profile without email · 23. policy restored
   ON · 24. discover 403 again.

Cleanup removed every `live-*` row it created (profiles, plans,
requests, audit rows, users — verified: 0 `live-*` users remain,
`user@example.com` untouched as the only dev user, 0 travel rows,
policy ended `requires_verification=true`). The static UI at :3000
still serves the SPA (200, HTML) — `frontend/` untouched throughout.

### 14.11 Known limitations & follow-up work

- **No blocking/restriction system** (pre-existing §12 gap): "exclude
  blocked users" reduces to verification + discoverability + partner/
  pending exclusions. Blocking must land before real social deployment.
- **Cross-direction request race:** the DB indexes lock each *direction*;
  two users sending to each other within the same instant can both pass
  the endpoint pre-check and create one pending request per direction.
  The state machine stays consistent (each is accepted/rejected/cancelled
  independently), but a canonical-pair expression index
  (LEAST/GREATEST — not portable to SQLite's min/max without a
  dialect-aware migration) is the recommended fix if this ever matters.
- **Destination matching is exact after casefold/whitespace-collapse:**
  punctuation and spelling variants ("Goa, India" vs "Goa India" vs
  "Goa") are different keys. A gazetteer/alias table is future work; the
  limitation is visible in the README and the module docstring.
- **The in-process rate limiter** (30 sends/hour/user) resets on restart
  and is per-process — same caveat as the Phase 6b owner-policy limiter.
- **No messaging/chat/notifications:** an accepted request is a row; the
  two users are never connected by any channel, and nothing notifies
  anyone (out of scope by the brief; chat is a later phase).
- **Score is a heuristic, not a safety signal** — repeated in every
  response; the UI (Phase 9) must display the note verbatim.
- **`MAX_CANDIDATE_ROWS = 500`** caps the SQL prefilter; beyond 500
  matching rows the ranking operates on the first 500 by (start_date,
  id). Fine at prototype scale; revisit with real traffic (or add
  keyset pagination) later.
- **Preference filtering is a Python secondary stage** (SQLite-portable
  JSON columns): with huge candidate sets it is O(rows) in Python.
- **No client UI** for any Phase 7 route yet (Phase 9).

### 14.12 Scope confirmation & git state

**Built exactly the brief:** travel profiles, preferences, plans,
eligibility-aware discovery/matching, travel-partner requests — on the
existing verification mechanism, with tests, regression, docs.
**Deliberately absent:** chat/blocking/AI-matching/verification-provider
items, sensitive identity data (none stored, none displayed), and any
change to `frontend/` (zero files touched). Health contract unchanged
(live-verified). `DATABASE_URL`/`JWT_SECRET_KEY` were read only from the
gitignored `backend/.env`; the test PostgreSQL URL was derived without
ever being printed.

**Git state:** branch `backend`, HEAD `30977c0` = `origin/backend` (the
Phase 6 second assignment commit). Per the owner's standing rule there
are **no commits and no pushes** from this phase — the working tree
carries the Phase 7 change set as 13 modified + 14 untracked files
(§16 lists them exactly). Awaiting owner review; `main` untouched.

## 15. Known limitations (current)

- Served endpoints: health, register/login, `GET/PATCH /users/me`, the five
  **trusted-contact** routes, the five **check-in** routes (Phase 4, §10),
  the five **SOS** routes (Phase 5, §11), the four **community-report**
  routes (Phase 6, §12: create, list, nearby, get-by-id), the seven
  **identity-verification/social** routes (Phase 6 second assignment, §13:
  status, submit, owner queue list/approve/reject, owner policy read/patch,
  social discovery), and the seventeen **travel-buddy** routes (Phase 7,
  §14: travel-profile CRUD, travel-plan CRUD, discover, public profile,
  request send/list/get/accept/reject/cancel — `/social/discovery` is now
  the real broad feed). Nothing else exposes the database over HTTP.
- Authentication is a **local prototype**: Argon2id password hashing + HS256
  JWTs. No refresh tokens, password reset, email verification, rate limiting,
  or account recovery yet — all belong to later phases.
- Phase 4 stores contact/check-in data **only**: no notifications, no contact
  verification, no overdue-check-in handling — those belong to later
  phases. Saving a contact never messages anyone, and an overdue check-in
  changes nothing.
- Phase 5 records SOS incidents **only**: activating one writes a row and
  never contacts emergency services, trusted contacts, or nearby users.
  `acknowledged`/`false_alarm` exist in the schema but are unreachable (no
  responder system); SOS activation has no rate limiting yet; there is no
  emergency UI (Phase 10).
- Phase 6 stores and searches reports **only**: every report is an
  **unverified user submission** (always `pending` — no moderation/roles
  exist, so `approved`/`rejected` are unreachable via the API), filing one
  notifies no one, submitter identity is never exposed, reports have no
  owner edit/delete actions, and the nearby search is an O(n) SQL haversine
  (no index/PostGIS, radius ≤ 50 km, <1% error at city scale).
  *(Amended by Phase 6 second assignment (§13): `users.role`/verification
  now exist, but report moderation is still untouched — `community_reports`
  status remains `pending`-only, as scoped.)*
- Phase 6 second assignment (§13) verification is **manual review only**:
  no Aadhaar/ID documents or any sensitive identity data are accepted,
  stored, logged, or displayed anywhere; no real identity-provider
  integration; request statuses are exactly
  `unverified/pending/verified/rejected` (no `expired`/`requires_review`
  yet); there is exactly **one** owner role with a server-side CLI grant
  (`python -m app.cli make-owner <email>` — no self-service ownership, no
  email/registration-order privilege); a reviewer cannot decide their own
  request (409); the owner-only policy rate limiter is **in-process**
  (resets on restart, per-process — fine on one dev machine, revisit
  before multi-process deployment); the social surface it gated is **real
  since Phase 7** (§14 — travel buddies + the `/social/discovery` broad
  feed, on the same unchanged dependency); account/safety workflows
  (trusted contacts, check-ins, SOS, profile) stay reachable while
  unverified, by design.
- The identity-verification feature has **no client UI** yet (Phase 9) and
  no email/verification notifications (none are claimed to work).
- Pagination exists on the report endpoints and on the Phase 7 discovery/
  request-list endpoints (offset/limit, 1–100); contact/check-in/SOS
  lists and the travel-plan list remain unbounded arrays (fine at
  prototype scale, revisit before real traffic). Discovery additionally
  caps its SQL prefilter at 500 candidate rows (§14.11).
- Phase 7 ships matching and requests **only**: no chat/messaging, no
  notifications, no trip events, no blocking system (§14.11); the
  compatibility score is a documented heuristic and is presented with an
  explicit "not a safety guarantee" note in every response; destination
  matching is exact after casefold/whitespace normalization (punctuation
  variants do not match — §14.11); the send-rate limiter (30/hour/user)
  is in-process like the owner-policy limiter; the cross-direction
  request race window is endpoint-guarded, not index-guarded (§14.11).
- AI and notifications remain unimplemented entirely.
- Dev-grade CORS and configuration only; no HTTPS.
- Runs only on this laptop, local machine, port 8000.
- The `backend` branch is pushed to GitHub (`origin/backend`) through
  **Phases 6 + 6 second assignment**: Phases 1–3 + audit as `5ea9b59`/
  `eb8e709`/`3d728ac`/`f26536e`, Phases 4 + 5 as `f602505`, Phase 6 as
  `9029047`, and **Phase 6 second assignment committed and pushed
  (owner-authorized) as `30977c0`** (see `git log`, HEAD =
  `origin/backend`). The working tree now carries the **uncommitted
  Phase 7 change set** (owner rule: no commits during a phase); every
  push of this branch contains the full tree (`backend/`, `frontend/`,
  `.gitignore`, and — since the owner's decision of 2026-10-12 —
  `docs/README.md`, so the `docs/` folder now exists on GitHub). GitHub's
  **`main` branch was fast-forwarded to this branch** the same day (owner
  decision, §16), so the GitHub homepage shows Phases 1–6 as
  committed so far.
- Database lives in a Docker container; if that container's volume is removed,
  recreate the schema with `alembic upgrade head`.
- Frontend cannot integrate beyond the health + auth + Phase 4 + Phase 5
  contract until Phase 9 (the Phase 6 report contract and the Phase 6
  second assignment verification/social contract are committed; the
  Phase 7 travel-buddy contract is implemented and verified but still
  uncommitted, §16).

## 16. Pending tasks and next steps

1. ✅ **Settled (2026-10-12):** owner reviewed Phases 4 + 5 (§10/§11 +
   `PHASE4_CHANGES.md`/`PHASE5_CHANGES.md`) and approved commit & push.
   The Phase 3 audit was already settled (`f26536e`).
2. ✅ **Done (2026-10-12):** the combined Phase 4 + Phase 5 delta was
   committed (one commit) and pushed to `origin/backend` after explicit
   owner instruction (as `f602505`).
3. ✅ **Done (2026-10-12):** Phase 6 (§12 + `PHASE6_CHANGES.md`) was
   committed and pushed to `origin/backend` after the owner's instruction;
   working tree clean. Whole-tree contents on GitHub verified
   (`backend/` + `frontend/` + `.gitignore`; `docs/` is an empty on-disk
   folder git cannot push).
4. ✅ **Done (2026-10-12):** owner decided to bring GitHub's **`main`
   branch** up to date → `main` was fast-forwarded to the `backend`
   branch (no merge conflict possible: `main` had never diverged) and
   pushed; the GitHub homepage now shows all of Phases 1–6.
5. ✅ **Done (2026-10-12):** owner chose a placeholder for the empty
   **`docs/`** folder → `docs/README.md` explains the folder's purpose
   and lists the planned future contents (e.g. `docs/merge-report.md`
   from Phase 9); the folder now exists on GitHub.
6. ✅ **Settled (2026-10-12, after this report's earlier draft):** Phase 6
   (second assignment) §13 + `PHASE6_IDENTITY_CHANGES.md` was reviewed by
   the owner and **committed and pushed to `origin/backend` as `30977c0`**
   (26 files, `git log` verifies) — the phase-6-era note that called it
   "uncommitted" predates that commit.
7. ⏳ **Awaiting owner review (2026-10-13):** Phase 7 (§14 +
   `PHASE7_TRAVEL_BUDDIES.md` + test results: **339 passed, 0 skipped** —
   309 offline + 30 real-PostgreSQL; live E2E 24/24 on `roamlary_dev`)
   is ready for review; the change set stays **uncommitted** until the
   owner approves (owner rule: no commits during a phase). Exact
   `git status --porcelain` output (branch `backend`, HEAD `30977c0` =
   `origin/backend`):

   ```text
    M backend/README.md
    M backend/app/api/v1/endpoints/social.py
    M backend/app/api/v1/router.py
    M backend/app/api/v1/schemas/social.py
    M backend/app/models/__init__.py
    M backend/app/models/enums.py
    M backend/app/models/user.py
    M backend/report.md
    M backend/tests/conftest.py
    M backend/tests/test_migrations.py
    M backend/tests/test_models.py
    M backend/tests/test_postgres_integration.py
    M backend/tests/test_verification.py
   ?? backend/PHASE7_TRAVEL_BUDDIES.md
   ?? backend/alembic/versions/426dcef31e27_add_travel_profiles_plans_buddy_requests.py
   ?? backend/app/api/v1/endpoints/travel_buddies.py
   ?? backend/app/api/v1/endpoints/travel_plans.py
   ?? backend/app/api/v1/endpoints/travel_profile.py
   ?? backend/app/api/v1/schemas/travel.py
   ?? backend/app/core/matching.py
   ?? backend/app/models/travel_partner_request.py
   ?? backend/app/models/travel_plan.py
   ?? backend/app/models/travel_profile.py
   ?? backend/app/services/
   ?? backend/tests/test_buddy_requests.py
   ?? backend/tests/test_discovery.py
   ?? backend/tests/test_matching.py
   ?? backend/tests/test_travel_plans.py
   ```

   (`backend/app/services/` is the untracked directory containing
   `__init__.py` and `discovery.py`. `frontend/` has **zero** changes.)
8. After the Phase 7 review: owner decides whether Phase 7 is committed/
   pushed (and whether `main` is fast-forwarded again). No commit or push
   happens without that explicit instruction.
9. Owner assigns the next phase (per the roadmap: Phase 8 proposal,
   notifications & background-job interfaces — or a re-prioritized brief;
   the original Phase 7 "AI companion" proposal was replaced by this
   assignment).
10. Frontend `report.md` from Laptop 2 → enables Phase 9 contract-alignment
    planning and the `docs/merge-report.md` integration document.
11. Laptop 3 to publish the AI contract before any AI-companion work can be
    real (stub until then).

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
