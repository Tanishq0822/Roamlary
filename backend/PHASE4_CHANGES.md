# Phase 4 — Complete Change Review

**Project:** Roamlary · **Workstream:** Backend · **Branch:** `backend`
**Base commit:** `f26536e` (Phase 3 audit) · **State:** all changes **uncommitted**
(owner rule: no commits during the phase — review with `git status` / `git diff`)

> **Post-close update (2026-10-12):** after the owner's explicit approval,
> the Phase 4 delta (including the §10 fix round) was **committed and
> pushed to `origin/backend` together with Phase 5** — see `git log`.
> The review-time state described below (uncommitted tree, base `f26536e`)
> is preserved as written.

This file exists so the project owner can review **every Phase 4 change
individually**. It is the standalone companion to `report.md` §10 (the
mandatory dev log); nothing here replaces it.

> **Safety boundary reminder:** Phase 4 only *stores* contacts and check-ins.
> Nothing is sent to anyone — no SMS, no email, no push, no emergency
> services, no SOS. Saving a contact does not notify or verify that contact,
> and an overdue check-in triggers no action whatsoever.

---

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend` (HEAD stays at f26536e):
git status            # 10 modified + 8 new files (Phase 4 + its fix round, §10)
git diff              # every changed line of the 10 modified files
git diff --stat       # one-line summary per file
```

New files are untracked (`??`), so open them directly — their full content
is the change.

**Review order (bottom-up, each layer only uses the ones below it):**

1. Models & enums → 2. Migration → 3. Schemas → 4. Endpoints → 5. Router
6. Tests → 7. Documentation

---

## Change inventory at a glance

| # | File | Action | One-line reason |
|---|---|---|---|
| 1 | `app/models/enums.py` | modified | add `cancelled` check-in status |
| 2 | `app/models/trusted_contact.py` | modified | add `relationship` column |
| 3 | `app/models/check_in.py` | modified | add `note` column + allow `cancelled` in CHECK |
| 4 | `alembic/versions/ccd362671e07_….py` | **new** | apply change #3 to the database |
| 5 | `app/api/v1/schemas/trusted_contact.py` | **new** | strict contact request/response shapes |
| 6 | `app/api/v1/schemas/check_in.py` | **new** | strict check-in shapes + time policies |
| 7 | `app/api/v1/endpoints/trusted_contacts.py` | **new** | 5 contact routes |
| 8 | `app/api/v1/endpoints/check_ins.py` | **new** | 5 check-in routes + state machine |
| 9 | `app/api/v1/router.py` | modified | register the 2 new routers |
| 10 | `tests/conftest.py` | modified | shared `api_client` + `register_user`; fix round added `insert_raw_user_and_checkin` |
| 11 | `tests/test_trusted_contacts.py` | **new** | 20 contact tests |
| 12 | `tests/test_check_ins.py` | **new** | 17 check-in tests |
| 13 | `tests/test_postgres_integration.py` | modified | +3 real-PostgreSQL schema tests; fix round added +2 downgrade-guard tests |
| 14 | `tests/test_models.py` | modified | enum assertion includes `cancelled` |
| 15 | `README.md` | modified | client-facing Phase 4 docs (+ downgrade-guard docs in the fix round) |
| 16 | `report.md` | modified | §10 Phase 4 record + status/history updates (+ §10.15 fix round) |
| 17 | `PHASE4_CHANGES.md` | **new (this file)** | this review document |
| 18 | `tests/test_migrations.py` | modified (fix round) | +2 data-dependent downgrade regression tests |

**Deliberately untouched:** `frontend/` (all of it), `app/api/v1/endpoints/{auth,users,health}.py`,
all Phase 1–3 tests' assertions (except #14), migrations `cc78d54068bb` and
`d9841015aec7` (historical — never edited), `.env` (gitignored, never printed).

---

## 1. Models & enums

### 1.1 `app/models/enums.py` (modified)

**What changed:** `CheckInStatus` gained `CANCELLED = "cancelled"`.

```python
class CheckInStatus(StrEnum):
    PENDING = "pending"  # scheduled, waiting for the user's answer
    SAFE = "safe"  # user confirmed they are safe
    NEEDS_HELP = "needs_help"  # user indicated they need help
    EXPIRED = "expired"  # deadline passed (set by a FUTURE phase's job)
    CANCELLED = "cancelled"  # user abandoned this check-in   ← NEW (Phase 4)
```

**Why:** the brief's suggested lifecycle includes `cancelled`, and without it
a user who creates a check-in by mistake could never close it (Phase 4 has no
expiry job either). The other four values are the original Phase 2 design and
were **kept**, per the brief's "use existing model conventions" rule — the
docstring now maps them to the generic lifecycle (`active`→`pending`,
`completed`→`safe`).

**Impact:** the `expired` state remains unreachable in Phase 4 (only a later
background job will set it).

### 1.2 `app/models/trusted_contact.py` (modified)

**What changed:** one new column.

```python
# Optional label for how the contact knows the user ("mother", "friend").
# Declared AFTER the `owner` relationship above on purpose: inside a class
# body the name `relationship` refers to the most recent assignment, so
# declaring it first would make `owner = relationship(...)` call a column.
relationship: Mapped[str | None] = mapped_column(String(50))
```

**Why:** `relationship` is the brief's optional contact field. One name is
used everywhere (Python attribute, database column, API field) so there is no
confusing alias — the ordering comment prevents the one real pitfall
(shadowing SQLAlchemy's `relationship()` function).

**Unchanged:** `user_id` (FK `ON DELETE RESTRICT`, indexed), `name`
(VARCHAR 80 NOT NULL), `phone` (VARCHAR 32 NOT NULL), `email` (nullable),
timestamps.

### 1.3 `app/models/check_in.py` (modified)

**What changed:** two things.

```python
__table_args__ = (
    CheckConstraint(
        "status IN ('pending', 'safe', 'needs_help', 'expired', 'cancelled')",  # +cancelled
        name="status_valid",
    ),
)
…
note: Mapped[str | None] = mapped_column(String(500))   # NEW: optional free-text note
```

**Why:** store the optional note the brief asks for, and let the database
itself reject any status outside the five allowed values (belt-and-braces —
even raw SQL can't insert an invalid status).

**Unchanged:** `due_at` (the "planned return time" — name kept from Phase 2,
see decision D5 in `report.md` §10.3), `completed_at`, `user_id` FK,
status index.

---

## 2. Migration

### 2.1 `alembic/versions/ccd362671e07_add_contact_relationship_checkin_note_.py` (new)

**What it does, in order:**

*upgrade():*
1. `op.add_column('check_ins', note VARCHAR(500) NULL)`
2. `op.add_column('trusted_contacts', relationship VARCHAR(50) NULL)`
3. `batch_alter_table("check_ins")`: drop the status CHECK constraint and
   recreate it including `'cancelled'`.

*downgrade():* **data-safety guard first** — counts `check_ins` rows with
`status = 'cancelled'`; if any exist, it raises a clear, actionable error
*before any schema change* (nothing is deleted, converted, or altered — an
explicit data-handling decision is required first; see §10). Only when
zero `cancelled` rows exist does the reverse proceed: constraint back to 4
values, then both columns dropped.

**Key decisions to review:**

| Point | Detail |
|---|---|
| Why hand-edited at all | `alembic revision --autogenerate` detected the 2 columns but **not** the CHECK-constraint change (Alembic doesn't compare CHECK constraints by default) |
| Why `batch_alter_table` | plain `op.drop_constraint` works on PostgreSQL but crashes SQLite — and `tests/test_migrations.py` runs the whole chain on SQLite. Batch mode issues a real `ALTER TABLE` on PostgreSQL and a table rebuild on SQLite |
| Why the names are short | the project's naming convention (`ck_%(table_name)s_%(constraint_name)s`) expands `status_valid` → `ck_check_ins_status_valid`. Passing the expanded name double-prefixes and fails |
| Why the convention is copied in | migrations are frozen history — the file never imports live app code, so a future refactor can't break it |
| Data safety | the upgrade is purely additive/nullable — no row altered or dropped. The downgrade refuses to run while any `cancelled` row exists (§10), and a *permitted* downgrade drops the two new columns (their values revert to nothing — that is what undoing the feature means) while the rows themselves survive |

**Applied & proven against the real dev database `roamlary_dev`:**

```
upgrade head   → ccd362671e07 (head); \d shows relationship + note;
                 ck_check_ins_status_valid includes 'cancelled'
downgrade one  → columns confirmed gone (check_ins had 0 rows at this point;
                 §10 adds the now-guarded data-dependent behaviour)
upgrade head   → columns + 5-value constraint confirmed back
alembic current → ccd362671e07 (head)
```

(Re-run after the final edits precisely so the committed file — not an
earlier draft — is what produced the live schema.)

---

## 3. Schemas (validation lives here, not in the routes)

### 3.1 `app/api/v1/schemas/trusted_contact.py` (new)

| Schema | Fields | Rules |
|---|---|---|
| `TrustedContactCreate` | `name`, `phone` (required); `relationship`, `email` (optional) | `extra="forbid"` → any injected field (e.g. `user_id`) is **422** |
| `TrustedContactUpdate` | all four optional | same strictness; `model_fields_set` lets the route tell "absent" from "explicit null" (null clears `relationship`/`email`; null `name`/`phone` → 422) |
| `TrustedContactRead` | `id`, `user_id`, `name`, `phone`, `relationship`, `email`, `created_at`, `updated_at` | `from_attributes` — **only these fields can ever leave the API** |

Validators (shared logic between create/update):
- **name** → trimmed; blank → 422; max 80.
- **phone** → strip spaces/dashes/parentheses/dots, keep leading `+`; must
  then match `^\+?\d{7,15}$`. *No country code assumed or added* —
  `"+91 98765 43210"` and `"(415) 555-2671"` store as `+919876543210` and
  `4155552671`.
- **relationship** → trimmed; blank → `NULL`; max 50.
- **email** → trimmed + lowercased (same policy as account emails),
  `EmailStr` format.

### 3.2 `app/api/v1/schemas/check_in.py` (new)

| Schema | Fields | Rules |
|---|---|---|
| `CheckInCreate` | `note`, `due_at` (both optional) | `extra="forbid"`; **no** `status`/`user_id`/`completed_at` — the server picks all three |
| `CheckInUpdate` | `note`, `due_at`, `status` (optional) | transition legality enforced in the route (needs the current state); still no protected fields |
| `CheckInRead` | `id`, `user_id`, `status`, `note`, `due_at`, `completed_at`, `created_at`, `updated_at` | approved fields only + `_to_utc` serializer |

The two time policies (enforced with 422 + a plain-language message):
1. **Timezone required** — `Z` or an offset; a naive timestamp is rejected
   (guessing a timezone on a safety deadline could be off by hours).
2. **Future required** — `due_at` must be after server UTC *now*, on create
   *and* on update.

`_to_utc()` on every outgoing timestamp makes the "responses are UTC"
contract true **at the API layer** instead of depending on the database:
PostgreSQL returns tz-aware values, SQLite returns naive ones — both are
normalized to UTC (`…Z`) before hitting the wire.

---

## 4. Endpoints (the routes)

### 4.1 `app/api/v1/endpoints/trusted_contacts.py` (new)

| Route | Status | Behaviour |
|---|---|---|
| `POST /api/v1/trusted-contacts/` | 201 | owner = **token user only**; returns the stored row |
| `GET /api/v1/trusted-contacts/` | 200 | caller's contacts only, oldest first (then `id` tie-break) |
| `GET /api/v1/trusted-contacts/{contact_id}` | 200 / 404 | |
| `PATCH /api/v1/trusted-contacts/{contact_id}` | 200 / 404 | edits any subset; empty body `{}` = no-op (`updated_at` untouched) |
| `DELETE /api/v1/trusted-contacts/{contact_id}` | 204 / 404 | removes only that row |

The private helper `_get_owned_contact()` is the ownership chokepoint: it
queries `WHERE id = :id AND user_id = :token_user` and raises **the same 404**
whether the row is missing or someone else's — so IDs can't be probed. Errors
are fixed `detail` strings (no SQL, no stack traces).

### 4.2 `app/api/v1/endpoints/check_ins.py` (new)

| Route | Status | Behaviour |
|---|---|---|
| `POST /api/v1/check-ins/` | 201 | status always starts `pending` (server-chosen) |
| `GET /api/v1/check-ins/` | 200 | caller's only, newest first; optional `?status=` (unknown value → 422) |
| `GET /api/v1/check-ins/{checkin_id}` | 200 / 404 | same identical-404 helper |
| `PATCH /api/v1/check-ins/{checkin_id}` | 200 / 404 / 409 | see state machine |
| `POST /api/v1/check-ins/{checkin_id}/complete` | 200 / 404 / 409 | see below |

**The state machine** (one table, `ALLOWED_TRANSITIONS`, in the file):

```
pending ──▶ safe          (PATCH, or POST /complete)
        ├──▶ needs_help   (PATCH)
        └──▶ cancelled    (PATCH)

safe / needs_help / expired / cancelled  →  NO exits (terminal, locked)
```

- Any other target — including re-setting the same value, or any move out of
  a terminal state — → **409** with
  `"Invalid status transition: a safe check-in cannot become pending."`
- `note`/`due_at` edits are allowed **only while pending**; once answered the
  record is read-only → **409**.
- First answer reaching `safe` or `needs_help` stamps `completed_at =
  server clock`; `cancelled` leaves it `NULL` (abandonment, not an answer).
  Clients have no field for `completed_at` anywhere.

**`POST …/complete` (documented as idempotent):**

| Current state | Result |
|---|---|
| `pending` | → `safe`, `completed_at = server now`, 200 |
| `safe` (repeat/retry) | 200, record unchanged — `completed_at` keeps the **first** call's time |
| `needs_help`, `cancelled`, `expired` | **409** (`safe` must never overwrite a `needs_help` answer) |

No SOS, no notification, no "emergency resolved" claim — this endpoint only
writes one row.

### 4.3 `app/api/v1/router.py` (modified)

Two lines: import `check_ins, trusted_contacts` and
`include_router(...)` both. Nothing else moved. Result: **10 new routes**
(verified via `/api/v1/openapi.json` — 15 paths total incl. health/auth/users).

---

## 5. Test infrastructure

### 5.1 `tests/conftest.py` (modified)

Two additions shared by both new test files (instead of duplicating the
boilerplate twice):

- **`api_client` fixture** — a real `TestClient` wired to the in-memory
  SQLite database (overrides `get_db`, clears stale overrides on entry/exit).
- **`register_user(client, email, …)` helper** — registers an account through
  the actual API and returns `(user_id, headers)`, so ownership tests can spin
  up two independent users exactly the way a real client would.

Imports `get_db` for the override; existing fixtures untouched.

---

## 6. Tests (40 new)

### 6.1 `tests/test_trusted_contacts.py` (new — 20 tests)

Group → what it proves:

- **Creation** (6): valid create returns exactly the approved field set;
  unauthenticated → 401; missing name/phone → 422; bad phone/email/blank
  name/overlong name → 422; **client-supplied `user_id` → 422 and ownership
  still comes from the token**; phone normalization
  (`"+1 (415) 555-2671"` → `+14155552671`).
- **Reads** (4): list returns only my contacts, oldest first, two-account
  isolation; get own → 200; get other's → 404; **foreign ID and fake ID give
  byte-identical 404 bodies** (no ownership enumeration).
- **Updates** (3): edit own works and leaves untouched fields alone; edit
  other's → 404 (owner's copy verified unchanged); injected `user_id` → 422
  and ownership unchanged.
- **Deletes** (3): delete own → 204 then 404; delete other's → 404 (owner's
  copy still 200); **deleting one contact leaves the user, their check-ins,
  and their other contact intact** (query-level verification).

### 6.2 `tests/test_check_ins.py` (new — 17 tests)

- **Creation** (7): approved field set + `pending` server-chosen +
  `completed_at null`; minimal `{}` create; unauthenticated → 401; **past
  `due_at` → 422**; **naive timestamp → 422**; malformed payload → 422;
  injected `status`/`user_id`/`completed_at` → 422.
- **Reads** (3): only my check-ins, newest first, two-account isolation;
  `?status=` filter works and unknown value → 422; cross-user GET/PATCH/
  `/complete` → 404.
- **Updates** (5): note + future deadline while pending; past deadline → 422;
  all three legal transitions from `pending`; **every terminal state refuses
  all four target values (409) and note edits are refused too**; protected
  fields (`id`/`user_id`/`created_at`/`completed_at`) → 422 with the record
  unchanged.
- **Completion** (4): sets `safe` + server timestamp ≈ now; **repeat
  completion is 200 and preserves the first `completed_at`**; `needs_help`
  and `cancelled` → 409 and stay unchanged; `cancelled` leaves
  `completed_at` null.
- **Safety boundary** (1): after completing, `sos_events` for that user is
  still **0**, and the response contains no `notified`/`sos`/`alert` field.

### 6.3 `tests/test_postgres_integration.py` (modified — +3 tests)

SQLite can't prove PostgreSQL compatibility, so these run against the
**disposable** `roamlary_test` database:

1. `test_phase4_columns_exist_and_are_nullable` — both new columns exist in
   `information_schema` and accept NULL.
2. `test_phase4_relationship_and_note_round_trip` — real INSERT/SELECT of
   `'mother'` and `'north trail'` through PostgreSQL.
3. `test_phase4_cancelled_status_allowed_by_check_constraint` — the relaxed
   CHECK constraint really accepts `'cancelled'` on a real PostgreSQL server.

The owner-assigned fix round (§10) later added 2 more here:
`test_pg_phase4_downgrade_refuses_when_cancelled_checkins_exist` and
`test_pg_phase4_downgrade_upgrade_roundtrip_without_cancelled_records` —
alembic itself runs against the disposable database in both.

### 6.4 `tests/test_models.py` (modified — 1 assertion)

The Phase 2 contract test now expects `cancelled` in the enum set. This is
the **only** pre-existing assertion changed anywhere in Phase 4, and it
encodes the contract Phase 4 intentionally extended (recorded in
`report.md` §10.4).

### 6.5 Actual results (no fabricated numbers)

Phase 4 close (before the fix round of §10): full suite **124 passed**, 0
failed, 0 skipped; `test_migrations.py` 3 passed; live E2E 28/28. After the
fix round added 4 tests, the final state is:

| Run | Output |
|---|---|
| Full suite (SQLite + PostgreSQL) | **128 passed**, 0 failed, 0 skipped |
| Phase 4 new tests | 37 passed (20 + 17) + 3 PG = 40 |
| Fix-round new tests (§10) | 4 passed (2 SQLite + 2 PostgreSQL migration tests) |
| `ruff check .` | All checks passed! |
| Live E2E vs `roamlary_dev` (full app stack) | **28/28 checks passed**, then its rows deleted |
| `tests/test_migrations.py` (SQLite up+down) | 5 passed |
| Blocked tests | none |

**Fixed during the phase (recorded honestly, final state is the table
above):** doubled constraint-name prefix on first migration attempt (rolled
back cleanly, short names fixed it); plain `drop_constraint` broke the SQLite
migration tests (`batch_alter_table` fixed it); a duplicated `drop_column`
block broke downgrade until removed; first endpoint-test run had 4 failures
— 2 real gaps (UTC responses, same-value status lock) fixed in code, 2 test
bugs fixed in the tests.

---

## 7. Documentation

### 7.1 `README.md` (modified)

- "Current scope" header → Phase 4; adds the 10 routes and the 124-test count.
- New **Trusted contacts & Safety check-ins** section: endpoint tables,
  request/response examples (fake data + placeholder tokens only), field
  validation rules, status values + allowed transitions, timestamp format &
  timezone behaviour, ownership/error-code summary.
- Migrations section: `ccd362671e07` added to the applied list.
- Tests section: 114 offline + 10 PostgreSQL numbers explained.
- Common problems: new rows for the Phase 4 422/409 cases.

### 7.2 `report.md` (modified)

- §2/§3/§4: git state, phase table, and change log updated — historical rows
  **annotated** (e.g. the Phase 3 audit's later commit `f26536e`), never
  rewritten.
- §5: the 10 routes moved from "proposed" to "implemented", with the Phase 4
  error contract.
- §6: third migration + new columns documented.
- **New §10: full Phase 4 record** — decisions table, file-by-file log,
  endpoint inventory, security checks, test commands + real numbers,
  regression results, limitations, checklist, scope, git state.
- §10/§11 → renumbered §11/§12 (Known limitations, Pending tasks) with
  Phase 4 content; the §9.14 note pointing at "§10, §11" carries a renumber
  annotation so the historical reference stays findable.

### 7.3 `PHASE4_CHANGES.md` (new — this file)

Standalone review companion, as requested by the owner.

---

## 8. What Phase 4 did **not** do (scope verification)

Checked against the brief's exclusion list — **none** of these exist in the
diff:

- ❌ SOS workflows / emergency escalation (the `sos_events` table is
  untouched; tests assert it stays empty)
- ❌ automated alerts for overdue check-ins / background jobs
- ❌ SMS, WhatsApp, email, push notifications
- ❌ Firebase Authentication
- ❌ live location tracking/sharing
- ❌ community safety reports
- ❌ AI/ML features
- ❌ Flutter or any frontend change (`frontend/` untouched)
- ❌ payments or unrelated features
- ❌ roles/admin functionality (users manage only their own records)
- ❌ commits, pushes, branch changes, resets, stashes (HEAD still `f26536e`)

---

## 9. Evidence summary

| Claim | Where it was verified |
|---|---|
| Phase 3 gate passed before Phase 4 started | 84-test run in preflight (report §10.1) |
| 10 routes exist and behave as documented | 37 endpoint tests + OpenAPI listing + 28/28 live E2E |
| Migration correct, applied, downgrade data-safe | `alembic current` head; refusal + roundtrip proven on SQLite **and** real PostgreSQL; SQLite 5 tests, 12 PG tests; live refusal demo on `roamlary_dev` (§10) |
| No cross-user leakage | identical-404 + two-account tests, all green |
| No false safety claims | no notification code exists; `sos_events` = 0 asserted |
| No secrets introduced | `git diff` scanned; `.env` still ignored |
| Working tree is the only change surface | `git status` → 10 modified + 8 new; HEAD = `origin/backend` = `f26536e` |

Passing automated tests are **not** a security audit or a production claim —
this remains a local hackathon prototype.

---

## 10. Migration-safety fix round (owner-assigned, after Phase 4 review)

The owner reviewed Phase 4 and flagged one real gap: the Phase 4 migration's
`downgrade()` restored the **old** 4-value CHECK constraint without first
checking whether any `cancelled` check-in rows exist. With such rows the
downgrade would fail mid-migration against PostgreSQL (a cryptic constraint
violation), and the earlier "reversible" claim did not establish that this
data-dependent case was handled.

### 10.1 What changed

Only the `downgrade()` of `ccd362671e07` (the Phase 4 migration, still
uncommitted working-tree history — the frozen migrations `cc78d54068bb` and
`d9841015aec7` were **not** touched). `upgrade()` is unchanged, so the live
schema is unchanged too. The `downgrade()` now:

1. **Counts** `check_ins` rows with `status = 'cancelled'` **before any
   schema change** (plain `SELECT count(*)`, works on both dialects).
2. If any exist → **raises** a clear error naming the count, the reason (the
   old constraint would reject those rows), what was NOT changed (nothing),
   and the explicit data-handling decisions available. No records are
   deleted, converted, or otherwise altered to force the downgrade.
3. Only when zero `cancelled` rows exist → the original reverse steps run
   (constraint back to 4 values, then the two columns dropped).

Because the check runs before any DDL, a refused downgrade leaves the schema,
the constraint, `alembic_version`, and every record exactly as they were.

### 10.2 Behaviour, both ways (proven, not assumed)

| Situation | `alembic downgrade d9841015aec7` | Result |
|---|---|---|
| ≥1 `cancelled` check-in exists | **Refused** (exit 1, actionable message) | Nothing changed: still at `ccd362671e07`, columns intact, 5-value constraint intact, the `cancelled` row untouched |
| No `cancelled` check-ins | **Succeeds** | Columns dropped, version = `d9841015aec7`; rows themselves survive (the dropped columns' values do not — that is what undoing the feature means) |
| Either case, then `upgrade head` | **Succeeds** | Exact Phase 4 schema restored |

### 10.3 New regression tests (4)

- `tests/test_migrations.py` **+2** (SQLite, same subprocess conventions):
  refusal-with-cancelled-row (asserts version/columns/constraint/row all
  unchanged) and downgrade→upgrade roundtrip without cancelled rows.
- `tests/test_postgres_integration.py` **+2** (gated on
  `ROAMLARY_TEST_DATABASE_URL`, same conventions): both scenarios again, on
  **real PostgreSQL**, with alembic itself running against the disposable
  `roamlary_test` database. A shared raw-SQL helper
  `insert_raw_user_and_checkin` was added to `tests/conftest.py` so both
  files insert probe rows the same way (bypassing the ORM, like real
  pre-existing data).
- Historical tests unchanged: `test_alembic_downgrade_base_removes_tables`
  still passes (a fresh database has no `cancelled` rows, so the guard lets
  it through).

### 10.4 Verified results (real output, 2026-10-12)

| Run | Output |
|---|---|
| `pytest tests/test_migrations.py -v` | **5 passed** (3 old + 2 new) |
| Full suite (offline + PostgreSQL) | **128 passed**, 0 failed, 0 skipped (116 offline + 12 PG) |
| `ruff check .` | All checks passed! |
| Live refusal demo on `roamlary_dev` | probe `cancelled` row inserted → downgrade exit **1** with "Refusing to downgrade migration ccd362671e07: 1 check-in record(s)…" → verified version still `ccd362671e07 (head)`, `note`+`relationship` still present, 5-value constraint still active, probe row still `cancelled` |
| Live normal path on `roamlary_dev` | probe rows deleted → downgrade **exit 0** (columns gone) → `upgrade head` **exit 0** → `alembic current` = `ccd362671e07 (head)`, columns + constraint back, database left with 0 users / 0 contacts / 0 check-ins / 0 SOS events |

### 10.5 Honest limitation this round documents

A *permitted* downgrade drops `note` and `relationship` **columns and their
values** (the rows survive). That is the definition of reverting the
feature, and it is why the downgrade stays a deliberate operator decision —
never something the app runs on its own.
