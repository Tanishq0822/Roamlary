# Phase 5 — Complete Change Review (SOS & Emergency Workflow)

**Project:** Roamlary · **Workstream:** Backend · **Branch:** `backend`
**Base commit:** `f26536e` (Phase 3 audit) · **State:** all changes **uncommitted**
(owner rule: no commits during the phase — review with `git status` / `git diff`)

> **Post-close update (2026-10-12):** the owner reviewed and approved
> commit & push — all **24 files** (Phases 4+5) were committed as one
> commit and pushed to `origin/backend` (see `git log`); the working tree
> is clean. The review-time counts below describe the tree *before* that
> commit.

This file exists so the project owner can review **every Phase 5 change
individually**. It is the standalone companion to `report.md` §11 (the
mandatory dev log); nothing here replaces it.

> **Safety boundary reminder:** Phase 5 only *records* SOS incidents
> locally. Activating an SOS does **not** contact police, ambulance, or any
> emergency number, does **not** notify trusted contacts or nearby users, and
> shares no location with anyone. This is not an emergency-response system.

---

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend` (HEAD stays at f26536e):
git status            # 11 modified + 13 new files (Phase 4 + Phase 5 = 24)
git diff              # every changed line of the modified files
git diff --stat       # one-line summary per file
```

New files are untracked (`??`), so open them directly — their full content
is the change. Phase 5's own delta on top of the uncommitted Phase 4 work:
**1 more modified file** (`app/models/sos_event.py` — Phase 4's 10 modified
files were also touched by Phase 5 where shared: `enums.py`, `router.py`,
`conftest.py`, `test_models.py`, `test_migrations.py`,
`test_postgres_integration.py`, `README.md`, `report.md`) + **5 brand-new
files** (migration `0dd8995649b4`, SOS schema, SOS endpoints,
`test_sos_events.py`, this file). Net result: **11 modified + 13 new = 24**
(Phase 4's 18 + Phase 5's 6).

**Review order (bottom-up, each layer only uses the ones below it):**

1. Enums & model → 2. Migration → 3. Schema → 4. Endpoints → 5. Router
6. Tests → 7. Documentation

---

## Change inventory at a glance

Files **Phase 5 touched** — the full working tree also carries Phase 4's
changes (18 files at that point); see `PHASE4_CHANGES.md` for those.

| # | File | Action | One-line reason |
|---|---|---|---|
| 1 | `app/models/enums.py` | modified | add `CANCELLED` to `SosStatus` |
| 2 | `app/models/sos_event.py` | modified | add `description`, `location_recorded_at`, `cancelled_at` + allow `cancelled` in CHECK |
| 3 | `alembic/versions/0dd8995649b4_….py` | **new** | apply change #2 to the database (with downgrade guard) |
| 4 | `app/api/v1/schemas/sos_event.py` | **new** | strict SOS request/response shapes + coordinate rules |
| 5 | `app/api/v1/endpoints/sos_events.py` | **new** | 5 SOS routes + lifecycle enforcement |
| 6 | `app/api/v1/router.py` | modified | register the SOS router |
| 7 | `tests/conftest.py` | modified | add `insert_raw_user_and_sos` raw-SQL helper |
| 8 | `tests/test_sos_events.py` | **new** | 24 endpoint tests |
| 9 | `tests/test_migrations.py` | modified | +2 SQLite downgrade-guard tests; Phase 4 tests pinned to their revision |
| 10 | `tests/test_postgres_integration.py` | modified | +4 real-PostgreSQL tests; Phase 4 tests pinned to their revision |
| 11 | `tests/test_models.py` | modified | enum contract now includes SOS `cancelled` |
| 12 | `README.md` | modified | client-facing Phase 5 docs + counts + troubleshooting |
| 13 | `report.md` | modified | §11 Phase 5 record + status/history updates |
| 14 | `PHASE5_CHANGES.md` | **new (this file)** | this review document |

**Deliberately untouched:** `frontend/` (all of it),
`app/api/v1/endpoints/{auth,users,health,trusted_contacts,check_ins}.py`,
`app/api/v1/deps.py`, `app/core/*`, migrations `cc78d54068bb`,
`d9841015aec7`, `ccd362671e07` (historical — never edited), `.env`
(gitignored, never printed).

---

## 1. Enums & model

### 1.1 `app/models/enums.py` (modified)

`SosStatus` gained `CANCELLED = "cancelled"`. The Phase 2 values were
**kept** (same precedent as Phase 4's `CheckInStatus`): `acknowledged` and
`false_alarm` remain in the enum and the database CHECK but are
**unreachable in Phase 5** — nothing implements them (no responder exists to
acknowledge an incident), exactly like `expired` for check-ins.

### 1.2 `app/models/sos_event.py` (modified)

Three new nullable columns + the CHECK extended to 5 values:

| Column | Type | Rule |
|---|---|---|
| `description` | VARCHAR(500) NULL | optional short note; nothing is ever sent anywhere |
| `location_recorded_at` | timestamptz NULL | server clock at activation, only when coordinates were given |
| `cancelled_at` | timestamptz NULL | server clock when the user retracted the SOS |

**Unchanged:** UUID PK, `user_id` FK `ON DELETE RESTRICT` (indexed),
`status`, `latitude`/`longitude` (+ their range CHECKs), `resolved_at`,
timestamps.

---

## 2. Migration — `alembic/versions/0dd8995649b4_add_sos_description_location_timestamp_.py` (new)

*upgrade():* 3 `add_column`s, then — written by hand, because autogenerate
does **not** compare CHECK constraints — drop + recreate the status CHECK to
include `'cancelled'`, via `batch_alter_table` (cross-dialect) with the short
logical name `status_valid` (expanded to `ck_sos_events_status_valid`).

*downgrade():* **data-safety guard first** (the Phase 4 fix-round pattern):
counts `sos_events` rows with `status='cancelled'` *before any schema
change*; if any exist it raises a clear, actionable error and nothing is
deleted, converted, or altered. Only when zero exist does the reverse run
(constraint back to 4 values, then drop the 3 columns — a *permitted*
downgrade drops those columns' values; the rows survive).

**Applied & proven against the real dev database `roamlary_dev`:**

```
upgrade head         → 0dd8995649b4 (head); 3 new columns present & nullable
live refusal demo    → probe 'cancelled' row inserted → downgrade exit 1
                       ("Refusing to downgrade migration 0dd8995649b4 …");
                       verified unchanged: head, columns, 5-value constraint,
                       probe row still 'cancelled'; probe rows then deleted
downgrade (no rows)  → exit 0, columns confirmed gone
upgrade head         → exit 0, columns + 5-value constraint back
alembic current      → 0dd8995649b4 (head), database left with 0 rows
```

---

## 3. Schema — `app/api/v1/schemas/sos_event.py` (new)

| Schema | Fields | Rules |
|---|---|---|
| `SosEventCreate` | `description`, `latitude`, `longitude` (all optional) | `extra="forbid"` → any injected field (`user_id`, `status`, `created_at`, `cancelled_at`, `resolved_at`, `location_recorded_at`, `id`) is **422** |
| `SosEventRead` | `id`, `user_id`, `status`, `description`, `latitude`, `longitude`, `location_recorded_at`, `created_at`, `updated_at`, `cancelled_at`, `resolved_at` | `from_attributes` — **only these fields can ever leave the API**; all timestamps normalized to UTC on the way out |

Validation:
- **coordinates** → both-or-neither (`model_validator`; one alone → 422);
  latitude `ge=-90, le=90`, longitude `ge=-180, le=180`.
- **description** → trimmed; blank/whitespace-only → **422** (deliberately
  stricter than a check-in's note: an SOS description is a deliberate
  statement); max 500.

There is **no update schema**: SOS incidents have no PATCH — the only state
changes are the dedicated cancel/resolve POSTs, which take **no body** at all,
so no client-controlled timestamp can even be expressed.

---

## 4. Endpoints — `app/api/v1/endpoints/sos_events.py` (new)

Bearer-token required on all five; owner always from the token; identical
`404` ("SOS incident not found.") for missing **and** foreign IDs.

| Route | Behaviour |
|---|---|
| `POST /api/v1/sos` | 201; `status='active'` server-chosen; `location_recorded_at`=server clock **only if** coordinates given |
| `GET /api/v1/sos` | own incidents only, newest first (created_at desc, id desc) |
| `GET /api/v1/sos/{sos_id}` | own only; 404 otherwise |
| `POST /api/v1/sos/{sos_id}/cancel` | active → cancelled + `cancelled_at`=server clock; else **409** |
| `POST /api/v1/sos/{sos_id}/resolve` | active → resolved + `resolved_at`=server clock; else **409** |

**Lifecycle:** `active → cancelled | resolved`; both terminal; repeats and
contradictions always **409** (deliberately *not* idempotent — differs from
Phase 4's `/complete`, per the Phase 5 spec). A failed transition changes
nothing (proven by test).

**Concurrency:** cancel/resolve use a conditional `UPDATE … WHERE id=… AND
status='active'` (compare-and-set) instead of read-then-write, so two racing
transitions cannot both win: exactly one applies, the loser sees
`rowcount == 0` → 409. `updated_at` is refreshed by the same statement.

**Route-shape note:** paths follow the Phase 5 spec exactly (`/sos`, no
trailing slash — unlike the Phase 4 collections); FastAPI redirects a
trailing-slash request, and the difference is documented in the README.

---

## 5. Security & ownership controls

- Ownership from the verified JWT only; request bodies cannot express an
  owner (`extra="forbid"`), and no query parameter can override it.
- Owner filtering happens **in every database query**, not in serialization
  → no insecure direct-object-reference; foreign and missing IDs are
  byte-identical 404s.
- Server-controlled fields (`status`, all timestamps) have no client input
  path: absent from request schemas (422) and set by server clock in code.
- Parameterized ORM statements only; failed transitions roll back.
- Coordinates: range CHECKs exist at **both** schema (422) and database
  (CHECK constraint) layers; the server never obtains/fabricates a location
  and never exposes one to another user.
- No logging of tokens/secrets/location data (no logging added at all).

---

## 6. Tests

### 6.1 `tests/test_sos_events.py` (new — 24 tests)

Auth (unauthenticated + invalid token on all five routes), activation
(minimal, description, coordinates + server timestamp, exact-range edges,
lat-without-lon / lon-without-lat, out-of-range, blank/overlong
description, 7 injected server-controlled fields), ownership (own-only
listing newest first, foreign GET/cancel/resolve 404, byte-identical
missing-vs-foreign 404, thief cannot touch the owner's record), lifecycle
(cancel/resolve with server timestamps ≈now, cancelled-not-resolvable,
resolved-not-cancellable, repeats 409 with first timestamp kept, client
body timestamp ignored, failed transitions leave the record byte-identical),
persistence (response matches the database row), safety boundary (exact
approved field set, no other table touched).

### 6.2 `tests/test_migrations.py` (modified — +2 tests)

`test_phase5_downgrade_refuses_when_cancelled_sos_exist` and
`test_phase5_downgrade_upgrade_roundtrip_without_cancelled_sos` — same
proven conventions as the Phase 4 tests. The two **Phase 4** tests were
pinned to `upgrade ccd362671e07` (instead of `head`, which now means the
Phase 5 revision): their intent is the Phase 4 migration's behaviour, and
the assertions are unchanged — no weakening, no deletions.

### 6.3 `tests/test_postgres_integration.py` (modified — +4 tests)

`test_phase5_sos_columns_exist_and_are_nullable`,
`test_phase5_cancelled_status_allowed_by_check_constraint`,
`test_pg_phase5_downgrade_refuses_when_cancelled_sos_exist`,
`test_pg_phase5_downgrade_upgrade_roundtrip_without_cancelled_sos` — real
PostgreSQL, with alembic itself running against the disposable
`roamlary_test` database. The two Phase 4 PG tests were pinned to
`upgrade ccd362671e07` for the same reason as §6.2.

### 6.4 `tests/test_models.py` (modified — 1 assertion)

The enum contract test now expects `cancelled` in `SosStatus` — the only
pre-existing assertion changed in Phase 5, mirroring Phase 4's documented
`CheckInStatus` change.

### 6.5 `tests/conftest.py` (modified)

`insert_raw_user_and_sos` — raw-SQL probe-row helper for the migration
tests (same purpose as `insert_raw_user_and_checkin`).

### 6.6 Actual results (no fabricated numbers)

| Run | Output |
|---|---|
| `pytest tests/test_sos_events.py -q` | **24 passed** |
| `pytest tests/test_migrations.py tests/test_models.py -q` | **15 passed** |
| Full suite (SQLite + PostgreSQL) | **158 passed**, 0 failed, 0 skipped (142 offline + 16 PG) |
| `ruff check .` | All checks passed! |
| Live E2E vs `roamlary_dev` (full app stack, temp script deleted after run) | **35/35 functional checks passed** — activation variants & validation, ownership/identical-404s, lifecycle & 409s, 401s, UTC timestamps; its 2 rows + 2 users deleted afterwards (DB verified 0 rows) |
| Live migration demo vs `roamlary_dev` | refusal with a `cancelled` row (exit 1, DB verified unchanged), then downgrade+upgrade roundtrip with none (both exit 0) |
| Blocked tests | none |

**Checks NOT performed** (be honest about the difference): no load or soak
testing; no security audit / penetration test; no automated multi-threaded
race test (the compare-and-set logic is code-reviewed and reasoned, only
deterministic transitions are exercised); no frontend integration; no
production/HTTPS deployment check; no test was run against anything other
than SQLite (fast tests) and the disposable `roamlary_test` PostgreSQL
database (integration tests).

**Fixed during the phase (recorded honestly):** the first SOS test run had
1 failure — a **test bug** (a state snapshot was taken before the transition
it should have guarded); the API itself was correct. The two cleanup checks
in the temp E2E script failed because the script's cleanup `LIKE` pattern
kept an old email domain after a rename; the rows were removed with an
explicit follow-up `DELETE` and the database verified empty.

---

## 7. Known limitations & outstanding issues

- `acknowledged` / `false_alarm` are stored (Phase 2) but **unreachable** —
  no responder system exists; a later phase owns that design.
- No pagination on `GET /sos` (unbounded list, fine at prototype scale —
  same limitation as contacts/check-ins).
- SOS activation has **no rate limiting**; an emergency UI must exist in a
  later phase.
- A permitted downgrade reverts the 3 Phase 5 columns **and their values**
  (rows survive) — documented, deliberate.
- The compare-and-set concurrency handling is implemented and reasoned
  about, but a true two-thread race is not exercised by an automated test
  (deterministic transitions are).
- Passing tests are **not** a security audit or a production claim — this
  remains a local hackathon prototype.

---

## 8. Scope confirmation — NOT implemented

- ❌ SMS/WhatsApp/email/push notifications, Twilio, AiSensy, or any alert
  delivery
- ❌ calls to emergency numbers or real dispatch of any kind
- ❌ trusted-contact notification/verification
- ❌ community reports (Phase 6) or nearby-user alerts
- ❌ AI risk analysis (Phase 7)
- ❌ background location tracking (a coordinate is stored only when the
  client deliberately sends it at activation)
- ❌ camera/microphone monitoring
- ❌ Flutter/frontend changes (`frontend/` untouched)
- ❌ commits, pushes, branch changes, resets, stashes (HEAD still `f26536e`)

---

## 9. Evidence summary

| Claim | Where it was verified |
|---|---|
| 5 routes exist and behave as documented | 24 endpoint tests + 35/35 live E2E on real PostgreSQL |
| Migration correct, applied, downgrade data-safe | `alembic current` = `0dd8995649b4 (head)`; refusal + roundtrip proven on SQLite **and** real PostgreSQL; live refusal demo on `roamlary_dev` |
| No cross-user leakage | identical-404 + two-account tests, all green |
| No emergency-service claims | no notification/dispatch code exists; response field sets asserted exact |
| No secrets introduced | `git diff` scanned; `.env` still ignored |
| Working tree is the only change surface | `git status` → 11 modified + 13 new (24 files); HEAD = `origin/backend` = `f26536e` |

---

## 10. Git state

- Branch **`backend`**; HEAD **`f26536e`** (= `origin/backend`).
- **No commits, pushes, merges, resets, or branch switches were made.**
- Working tree: 11 modified + 13 new files = 24 total (Phase 4's 18 plus
  Phase 5's `app/models/sos_event.py` modification and 5 new files).
- `backend/.env` remains gitignored; no secrets, tokens, or generated
  artifacts are tracked; `frontend/` untouched.

> **Update (2026-10-12):** the approval came — these 24 files were
> committed and pushed (see the header note).
