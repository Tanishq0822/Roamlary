# Phase 6 — Complete Change Review (Community Safety Reports & Location Search)

**Project:** Roamlary · **Workstream:** Backend · **Branch:** `backend`
**Base commit:** `f602505` (Phases 4+5) · **State at review time:** all changes **uncommitted**
(owner rule: no commits during the phase — review with `git status` / `git diff`)

> **Post-close update (2026-10-12):** the owner instructed commit & push —
> all **15 files** were committed and pushed to `origin/backend` (see
> `git log`); the working tree is clean. The review-time state below
> describes the tree *before* that commit.

This file exists so the project owner can review **every Phase 6 change
individually**. It is the standalone companion to `report.md` §12 (the
mandatory dev log); nothing here replaces it.

> **Trust boundary reminder:** Phase 6 only *stores and searches* reports.
> Every report is an **unverified user submission** — filing one proves
> nothing about the place, and the API never claims a location is dangerous
> or safe. No moderation/verification system exists, nothing is sent to
> anyone (no notifications, no emergency services, no nearby-user alerts),
> and submitter identity is never exposed.

---

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend` (HEAD stays at f602505):
git status            # 10 modified + 5 new files (all Phase 6)
git diff              # every changed line of the modified files
git diff --stat       # one-line summary per file
```

New files are untracked (`??`), so open them directly — their full content
is the change.

**Review order (bottom-up, each layer only uses the ones below it):**

1. Enums & model → 2. Migration → 3. Schemas → 4. Endpoints → 5. Router
6. Tests → 7. Documentation

---

## Change inventory at a glance

| # | File | Action | One-line reason |
|---|---|---|---|
| 1 | `app/models/enums.py` | modified | add `ReportCategory` (6 values) + `ReportStatus` docstring for the no-moderation reality |
| 2 | `app/models/community_report.py` | modified | add `category_valid` CHECK constraint; Phase 6 docstring |
| 3 | `alembic/versions/ab32047c8481_add_community_report_category_check.py` | **new** | apply change #2 to the database (upgrade-side data guard) |
| 4 | `app/api/v1/schemas/community_report.py` | **new** | strict create schema + privacy-preserving read schema |
| 5 | `app/api/v1/endpoints/community_reports.py` | **new** | 4 report routes: create, list (filters+pagination), nearby (haversine), get-by-id |
| 6 | `app/api/v1/router.py` | modified | register the reports router |
| 7 | `tests/conftest.py` | modified | add `insert_raw_user_and_report` raw-SQL helper |
| 8 | `tests/test_reports.py` | **new** | 28 endpoint tests |
| 9 | `tests/test_migrations.py` | modified | +2 SQLite tests (upgrade guard, roundtrip) |
| 10 | `tests/test_postgres_integration.py` | modified | +3 real-PostgreSQL tests (constraint, guard, roundtrip) |
| 11 | `tests/test_models.py` | modified | `ReportCategory` contract + category CHECK existence tests |
| 12 | `tests/test_db_operations.py` | modified | sample category `lighting` → `poor_lighting` (closed set) |
| 13 | `README.md` | modified | client-facing Phase 6 docs + counts + troubleshooting |
| 14 | `report.md` | modified | §12 Phase 6 record + status/history updates |
| 15 | `PHASE6_CHANGES.md` | **new (this file)** | this review document |

**Deliberately untouched:** `frontend/` (all of it),
`app/api/v1/endpoints/{auth,users,health,trusted_contacts,check_ins,sos_events}.py`,
`app/api/v1/deps.py`, `app/core/*`, all older migrations `cc78d54068bb`,
`d9841015aec7`, `ccd362671e07`, `0dd8995649b4` (historical — never edited),
`.env` (gitignored, never printed).

**No duplicate artifacts:** Phase 6 created **no new table** — the Phase 2
`community_reports` table (and its migration) is reused as-is; the only
schema change is one added CHECK constraint.

---

## 1. Enums & model

### 1.1 `app/models/enums.py` (modified)

New `ReportCategory` StrEnum — the product decision the Phase 2 model
explicitly deferred ("categories are a Phase 6 product decision"):

| Value | Meaning |
|---|---|
| `unsafe_area` | general "do not linger here" observation |
| `harassment` | someone was harassed at/near this place |
| `suspicious_activity` | unusual or unsettling behaviour observed |
| `road_hazard` | roads/transport danger |
| `poor_lighting` | dark streets, broken lamps, blind corners |
| `other` | genuine concern that fits nowhere above |

All six fit the column's `VARCHAR(40)`. `ReportStatus` (Phase 2, three
values) is **unchanged** — its docstring now documents the Phase 6 reality:
`approved`/`rejected` are reserved for a future moderation system and no
endpoint can set them.

### 1.2 `app/models/community_report.py` (modified)

Added `CheckConstraint("category IN (…)", name="category_valid")` — the
database layer of the two-layer category validation (schema rejects with
422, database rejects anything that bypasses the API). Column types,
nullable lat/lon, `status` CHECK, range CHECKs, and the `user_id` FK
(`ON DELETE RESTRICT`, indexed) are **unchanged** from Phase 2.

---

## 2. Migration — `alembic/versions/ab32047c8481_add_community_report_category_check.py` (new)

*upgrade():* **data guard first** — counts `community_reports` rows whose
category is outside the closed set *before any schema change*; if any
exist, it raises `RuntimeError: Refusing to upgrade migration
ab32047c8481: … data-handling decision …` and **nothing** is deleted,
converted, or altered (the database stays at `0dd8995649b4`). Only when
all existing categories are in-set does the CHECK get added, via
`batch_alter_table` (cross-dialect, short logical name `category_valid`
expanded by the naming convention to `ck_community_reports_category_valid`).

*Why the guard is on the upgrade, not the downgrade:* the Phase 2 schema
allowed **any** string as a category, so pre-Phase-6 rows (hand-written or
from an old client) may carry out-of-set values that the new CHECK would
reject — and forcing the constraint through would mean silently converting
or deleting user data. The refusal forces an explicit decision instead.

*downgrade():* drops the constraint — dropping a CHECK can neither lose
nor alter stored data (every category value survives; the loose Phase 2
rules return), so this direction is unconditionally safe and has no guard.

**Applied & proven against the real dev database `roamlary_dev`:**

```
upgrade head            → ab32047c8481 (head); constraint present,
                          pg_constraint def lists all 6 values
live guard demo         → downgrade to 0dd8995649b4 → raw 'theft' row
                          inserted → upgrade exit 1 ("Refusing to upgrade
                          migration ab32047c8481 … data-handling
                          decision …"); verified unchanged: version still
                          0dd8995649b4, category-constraint-count=0,
                          probe row still 'theft/pre-phase6 category'
probe row deleted       → explicit DELETE of my own demo row (documented
                          data-handling decision)
upgrade head (clean)    → exit 0; alembic current → ab32047c8481 (head);
                          constraint back; database verified empty
                          (0 users, 0 reports)
```

---

## 3. Schemas — `app/api/v1/schemas/community_report.py` (new)

| Schema | Fields | Rules |
|---|---|---|
| `ReportCreate` | `category`, `description`, `latitude`, `longitude` (all required) | `extra="forbid"` → any injected field (`user_id`, `status`, `id`, `created_at`, `updated_at`) is **422** |
| `ReportRead` | `id`, `category`, `status`, `description`, `latitude`, `longitude`, `created_at`, `updated_at` | `from_attributes` — **only these 8 fields can ever leave the API**; timestamps normalized to UTC on the way out; **`user_id` deliberately absent** |

Validation:
- **category** → `ReportCategory` closed set; anything else → 422.
- **coordinates** → **required** (a location-based feature is pointless
  without a location): latitude `ge=-90, le=90`, longitude
  `ge=-180, le=180`.
- **description** → required, trimmed; blank/whitespace-only → **422**;
  max 500 (same bound as check-in notes and SOS descriptions).

There is **no update schema**: reports have no PATCH/DELETE — the status
column belongs to the future moderation system, not the submitter.

---

## 4. Endpoints — `app/api/v1/endpoints/community_reports.py` (new)

Bearer-token required on all four. Reports are **community content**:
any authenticated user may read them; identity comes only from the token.

| Route | Behaviour |
|---|---|
| `POST /api/v1/reports` | 201; `user_id` from token; `status='pending'` server-chosen; `409` only on an integrity failure |
| `GET /api/v1/reports` | visible reports, newest first (`created_at desc, id desc`); optional `category`, `status=pending\|approved` filters; `offset` (≥0, default 0) + `limit` (1–100, default 20) |
| `GET /api/v1/reports/nearby` | required `latitude`, `longitude`, `radius_m` (meters, 0 < r ≤ 50000); optional `category`, `offset`, `limit`; nearest first (distance asc, then newest first) |
| `GET /api/v1/reports/{report_id}` | visible reports only; **404 for missing *and* rejected** (byte-identical) |

**Route order:** `/nearby` is declared **before** `/{report_id}` so a
literal `nearby` path can never be parsed as a UUID and mis-422.

**Visibility model:** every query carries `status != 'rejected'`. Hidden
rows disappear from list, nearby, and get-by-id the day moderation exists —
no query rewrite needed later. `status=rejected` as a *filter* → 422
(hidden is not filterable).

**Pagination:** Phase 6 introduces the API's first bounded pagination
(offset/limit, capped at 100). Responses stay **plain JSON arrays** to
match every other list endpoint (no envelope format divergence).

**Nearby math:** a parameterized SQL **haversine** (Earth radius
6,371,000 m), with `a` clamped to ≤1 so rounding at antipodal points can
never push `asin()` out of its domain. No PostGIS, no spatial index —
documented in the README (O(n) scan, no index, <1% error at city scale,
NULL-coordinate rows skipped, wrap-safe at the antimeridian, accurate at
high latitudes).

---

## 5. Security, ownership, privacy & trust controls

- **Authentication** on all four routes (401 without/with a bad token);
  identity only from the verified JWT — `user_id` cannot be supplied
  (`extra="forbid"` → 422), so impersonating another submitter is
  structurally impossible.
- **No owner lifecycle exists** — reports are read-only public content;
  no PATCH/DELETE/status endpoint, hence no ownership attack surface for
  mutations. (Bounded scope: the brief permits only actions the existing
  design allows, and that design reserves `status` for moderation.)
- **Ordinary users cannot self-verify**: `status` is absent from the
  create schema (422) and set to `pending` in server code. Nothing can
  set `approved`/`rejected` today.
- **Privacy:** `user_id` is stored (accountability/abuse follow-up) but
  never returned; the read schema is a closed 8-field set with no email,
  phone, or auth data — asserted by tests with exact-field-set checks.
- Parameterized ORM statements only; range validation at **both** schema
  (422) and database (CHECK) layers; query bounds on radius/limit/offset;
  no logging added (no tokens, no secrets, no coordinates logged).

---

## 6. Tests

### 6.1 `tests/test_reports.py` (new — 28 tests)

Creation (pending + exact 8-field set + trim, all six categories
accepted, unknown/blank category, missing fields, blank/overlong
description, out-of-range + edge coordinates, 4 injected server-controlled
fields), auth (401 ×4 routes + invalid token), reads & privacy (get,
404, newest-first + two accounts see identical identity-free payloads,
persistence stores `user_id` while the response omits it), moderation
visibility (`rejected` hidden from list/nearby/get with byte-identical
404, `status` filter accepts pending/approved but 422s rejected/unknown,
category filter), pagination (offset/limit pages, bounds 422, default cap
of 20 over 21 rows), nearby (inside/outside radius, nearest-first vs a
Python haversine cross-check, radius unit/bounds, center-coordinate
validation, **antimeridian wrap** 179.9°/−179.9°, **high latitude** 78°N,
NULL-coordinate rows skipped, category filter + pagination bounds).

### 6.2 `tests/test_migrations.py` (modified — +2 tests)

`test_phase6_upgrade_refuses_when_unknown_categories_exist` (guard fires,
exit ≠ 0, refusal text, version/constraint/row all verified unchanged)
and `test_phase6_upgrade_downgrade_roundtrip_with_valid_data` (constraint
appears, downgrade drops it while the stored category survives,
re-upgrade restores it). Both pinned to explicit revisions, matching the
Phase 4/5 convention.

### 6.3 `tests/test_postgres_integration.py` (modified — +3 tests)

`test_phase6_category_constraint_enforced_on_pg` (in-set insert ok,
`'theft'` → `IntegrityError`),
`test_pg_phase6_upgrade_refuses_when_unknown_categories_exist`,
`test_pg_phase6_downgrade_upgrade_roundtrip` (pg_constraint count 0 → 1,
row data survives).

### 6.4 `tests/test_models.py` (modified — 2 new tests)

`ReportCategory` enum contract (exactly the six values) and the
`ck_community_reports_category_valid` CHECK's existence in metadata.

### 6.5 `tests/test_db_operations.py` (modified — sample value only)

The Phase 2 test stored the loose sample `category="lighting"`; under the
closed set that value is now rejected by the database, so the sample
became `poor_lighting` (same intent — "Dark square near the station").
The assertions kept their exact-match strength (stored-value round-trip);
no assertion was deleted or weakened. This mirrors the documented Phase
4/5 enum-assertion updates.

### 6.6 `tests/conftest.py` (modified)

`insert_raw_user_and_report` — raw-SQL probe-row helper for the migration
tests (same purpose as the check-in/SOS helpers; `category` is a plain
string on purpose so tests can express out-of-set values).

### 6.7 Actual results (no fabricated numbers)

| Run | Output |
|---|---|
| `pytest tests/test_reports.py -q` | **28 passed** |
| `pytest tests/test_migrations.py tests/test_models.py -q` | **19 passed** |
| Full suite (SQLite + PostgreSQL) | **193 passed**, 0 failed, 0 skipped (174 offline + 19 PG) |
| `ruff check .` / `ruff format --check .` | All checks passed! / no changes |
| Live E2E vs `roamlary_dev` (full app stack, temp script deleted after run) | **51/51 functional checks passed** — creation/validation (all 6 categories, injections, coordinate edges), privacy (exact field sets, two-account identical views), filters + pagination bounds, rejected-hidden semantics, nearby (inside/outside, antimeridian, high latitude, radius bounds, Python distance cross-check), 401s; database verified empty afterwards |
| Live migration guard demo vs `roamlary_dev` | refusal with an out-of-set row (exit 1; version/constraint/row verified unchanged), probe row deleted, clean upgrade to `ab32047c8481 (head)`, DB verified empty |
| Blocked tests | none |

**Checks NOT performed** (be honest about the difference): no load or soak
testing (the O(n) nearby scan was not measured beyond small data); no
security audit / penetration test; no moderation workflow of any kind; no
frontend integration; no production/HTTPS deployment check; no test was
run against anything other than SQLite (fast tests) and the disposable
`roamlary_test` PostgreSQL database (integration tests); the antimeridian
and high-latitude behaviour is proven by example points, not an exhaustive
geodesy suite.

**Fixed during the phase (recorded honestly):** the first full-suite run
had 1 failure — a Phase 2 test (`test_db_operations`) using the loose
sample category `lighting`, now rejected by the new CHECK (§6.5: sample
value updated, assertions unchanged). The first live E2E run showed 2
failures that were **script-expectation bugs** (an offset page computed
past the end of the data, and a nearest-first assertion that forgot a
closer report existed); the API behaved correctly — after fixing the
script's expectations the run was 51/51. One accidental keyboard-mash
fragment found in `PHASE5_CHANGES.md` (line 250, pre-existing from before
this phase) was restored to the committed state and reported to the owner.

---

## 7. Known limitations & outstanding issues

- **No moderation:** every report stays `pending` forever; `approved`/
  `rejected` are unreachable (no roles, no dashboard — both explicitly
  out of scope). `rejected`-hiding is implemented and tested but can only
  be triggered from the database until moderation lands.
- **No owner lifecycle:** submitters cannot edit or delete their own
  reports (no PATCH/DELETE by design of this phase's scope).
- Nearby search **scans the table** (no index, no PostGIS); radius capped
  at 50 km; spherical Earth model (<1% error at city scale).
- The list endpoint has no `total` count (arrays only, matching existing
  list conventions); pagination exists **only** on reports — other list
  endpoints remain unbounded.
- Rate limiting / abuse controls (flood of reports) do not exist yet.
- Passing tests are **not** a security audit or a production claim — this
  remains a local hackathon prototype.

---

## 8. Scope confirmation — NOT implemented

- ❌ moderation/verification workflow, roles, or a moderation dashboard
- ❌ SMS/WhatsApp/email/push notifications, Twilio, AiSensy, or any alert
  delivery
- ❌ calls to emergency numbers or real dispatch of any kind
- ❌ trusted-contact notification, nearby-user alerts, community alerts
- ❌ AI risk analysis (later phase)
- ❌ background tracking, camera/microphone (a coordinate is stored only
  when the client deliberately sends it)
- ❌ PostGIS / new infrastructure dependencies
- ❌ Flutter/frontend changes (`frontend/` untouched)
- ❌ commits, pushes, branch changes, resets, stashes (HEAD still `f602505`)

---

## 9. Evidence summary

| Claim | Where it was verified |
|---|---|
| 4 routes exist and behave as documented | 28 endpoint tests + 51/51 live E2E on real PostgreSQL |
| Category enforced at both layers | schema 422 tests + DB CHECK tests (SQLite + `IntegrityError` on real PG) |
| Migration applied, upgrade guard data-safe | `alembic current` = `ab32047c8481 (head)`; refusal + roundtrip proven on SQLite **and** real PG; live refusal demo on `roamlary_dev` (DB verified unchanged) |
| No identity leakage | exact-8-field assertions, two-account identical-view test, no `user_id` key anywhere |
| No self-verified reports | `status` absent from create schema (422 injection tests); server sets `pending` |
| No real alerts / notifications | no such code exists; reports only write rows; responses asserted exact |
| No secrets introduced | `git diff` scanned; `.env` still ignored |
| Working tree is the only change surface | `git status` → 10 modified + 5 new (15 files); HEAD = `origin/backend` = `f602505` |

---

## 10. Git state

- Branch **`backend`**; HEAD **`f602505`** (= `origin/backend`).
- **No commits, pushes, merges, resets, or branch switches were made
  during the phase.**
- Working tree at review time: 10 modified + 5 new files = 15 total.
- `backend/.env` remains gitignored; no secrets, tokens, or generated
  artifacts are tracked; `frontend/` untouched.

> **Update (2026-10-12):** the owner instructed commit & push — these 15
> files were committed and pushed (see the header note). Whole-tree check:
> the pushed branch contains `backend/`, `frontend/` (27 tracked files),
> and `.gitignore`; the on-disk `docs/` folder is empty, which git cannot
> push (an empty directory has no contents to store).
