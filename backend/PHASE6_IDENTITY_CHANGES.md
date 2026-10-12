# Phase 6 (second assignment) — Complete Change Review (Identity Verification & Social Access Foundation)

**Project:** Roamlary · **Workstream:** Backend · **Branch:** `backend`
**Base commit:** `9939515` (Phase 6 + docs placeholder) · **State at review time:** all changes **uncommitted**
(owner rule: no commits during the phase — review with `git status` / `git diff`)

This file exists so the project owner can review **every change of this
phase individually**. It is the standalone companion to `report.md` §13
(the mandatory dev log); nothing here replaces it.

> **Trust boundary reminder:** this phase implements a **manual-review**
> workflow only. It collects **no identity documents** — no Aadhaar, no ID
> numbers, no scans — anywhere: not in requests, not in the database, not
> in logs, tests, or reports. "Verified" here means *an owner manually
> approved a short note*, not that any real identity check happened. No
> external identity provider, email, or notification is integrated or
> claimed to work. Account/safety workflows (trusted contacts, check-ins,
> SOS, profile, reports) stay reachable while unverified.

---

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend` (HEAD stays at 9939515):
git status            # 11 modified + 15 new files (all Phase 6 second assignment)
git diff              # every changed line of the modified files
git diff --stat       # one-line summary per file
```

New files are untracked (`??`), so open them directly — their full content
is the change.

**Review order (bottom-up, each layer only uses the ones below it):**

1. Enums & models → 2. Migration → 3. Policy/rate-limit core →
4. Schemas → 5. Gates (deps) → 6. Endpoints → 7. CLI → 8. Router →
9. Tests → 10. Documentation

---

## Change inventory at a glance

| # | File | Action | One-line reason |
|---|---|---|---|
| 1 | `app/models/enums.py` | modified | add `VerificationStatus` (4 values), `VerificationRequestStatus` (3), `UserRole` (2) |
| 2 | `app/models/user.py` | modified | add NOT NULL `verification_status`/`role` columns with CHECKs + secure defaults + relationship |
| 3 | `app/models/__init__.py` | modified | register the 3 new models |
| 4 | `alembic/versions/3e285edb0896_add_identity_verification_foundation.py` | **new** | apply #2/#5–7 to the database (downgrade guarded by data) |
| 5 | `app/models/identity_verification.py` | **new** | one row per verification request (history) |
| 6 | `app/models/app_setting.py` | **new** | keyed runtime config (the policy row) |
| 7 | `app/models/setting_change.py` | **new** | append-only audit (who/when/old→new) |
| 8 | `app/core/policy.py` | **new** | fail-closed policy read + audited write (`set_policy`) |
| 9 | `app/core/rate_limit.py` | **new** | in-process fixed-window limiter (policy PATCH: 5/hour/owner) |
| 10 | `app/api/v1/schemas/verification.py` | **new** | strict request/response shapes (7 schemas) |
| 11 | `app/api/v1/schemas/social.py` | **new** | `DiscoveryResponse` (empty `profiles` + honest message) |
| 12 | `app/api/v1/deps.py` | modified | add `require_owner` + `require_verified_user` reusable gates |
| 13 | `app/api/v1/endpoints/verification.py` | **new** | 2 routes: status, submit request |
| 14 | `app/api/v1/endpoints/admin.py` | **new** | 4 routes: queue, approve, reject, policy read/patch |
| 15 | `app/api/v1/endpoints/social.py` | **new** | 1 gated placeholder route: discovery |
| 16 | `app/api/v1/router.py` | modified | register the 3 new routers (7 routes total) |
| 17 | `app/cli.py` | **new** | `python -m app.cli make-owner <email>` — the only owner-grant path |
| 18 | `tests/conftest.py` | modified | add `insert_raw_user_and_verification` raw-SQL probe helper |
| 19 | `tests/test_verification.py` | **new** | 20 endpoint tests (states, gate, no self-verify) |
| 20 | `tests/test_admin.py` | **new** | 19 endpoint tests (queue, review, policy, audit, rate limit) |
| 21 | `tests/test_migrations.py` | modified | +4 SQLite tests (columns/CHECKs, downgrade guard, roundtrip) |
| 22 | `tests/test_models.py` | modified | +4 contract tests + expected-tables list |
| 23 | `tests/test_postgres_integration.py` | modified | +5 real-PostgreSQL tests (CHECKs, guard, roundtrip) |
| 24 | `README.md` | modified | client-facing verification/gate/CLI docs + counts + troubleshooting |
| 25 | `report.md` | modified | §13 record + PART 1 status updates (§14/§15 renumbered) |
| 26 | `PHASE6_IDENTITY_CHANGES.md` | **new (this file)** | this review document |

**Deliberately untouched:** `frontend/` (all of it), `app/core/security.py`
+ auth/JWT flow (roles and status are read live from the database on every
request — tokens stay unchanged), `UserProfile` schema (verification state
is exposed only via `GET /verification/status`), SOS/report/check-in/
contact endpoints (safety workflows keep working while unverified), all
older migrations `cc78d54068bb`…`ab32047c8481` (historical — never
edited), `.env` (gitignored, never printed).

**Owner decisions baked in (answered before coding):** the gated surface
is **one placeholder route** (`GET /social/discovery` → empty list + honest
Phase 7 message), and owner provisioning is **`users.role` + a server-side
CLI** — no API path grants privileges.

---

## 1. Enums & models

### 1.1 `app/models/enums.py` (modified) — three distinct enums

| Enum | Values | Stored on |
|---|---|---|
| `VerificationStatus` (account state) | `unverified`, `pending`, `verified`, `rejected` | `users.verification_status` |
| `VerificationRequestStatus` (request history) | `pending`, `approved`, `rejected` | `identity_verifications.status` |
| `UserRole` | `user`, `owner` | `users.role` |

Three enums instead of one shared "status" because the two lifecycles are
genuinely different: an *account* is `unverified`; a *request* is
`pending`; a request becomes `approved` while its account becomes
`verified`. Sharing one enum would have allowed nonsense states to compile.
Every value is enforced a second time at the database with CHECK
constraints (two-layer validation, same as the Phase 6 category set).

There is deliberately **no `expired`, `requires_review`, or similar**
status — the brief allows only the states above; extending later is a
migration, not a silent value.

### 1.2 `app/models/user.py` (modified)

Two new NOT NULL columns on `users`:

- `verification_status` VARCHAR(20), CHECK ∈ the 4 values,
  `server_default="unverified"`
- `role` VARCHAR(10), CHECK ∈ the 2 values, `server_default="user"`

The `server_default` exists so **three** writers agree on the same value:
the ORM (Python-side default on new instances), raw SQL inserts (tests and
any future script), and Alembic (backfilling existing rows when the column
is added). A Python-only default would have left raw SQL failing with
"null value in column" — exactly the kind of mismatch the tests catch.
Both defaults are the **secure** choices: a brand-new or unknown account
is unprivileged.

Also added: `identity_verifications` relationship (a user's request
history, newest first), plus docstrings documenting that no route accepts
either field from a client.

### 1.3 New model files (created)

| File | Table | Notes |
|---|---|---|
| `app/models/identity_verification.py` | `identity_verifications` | `id` UUID PK, `user_id` FK→users (RESTRICT, indexed), `status` CHECK ∈ the 3 values, `applicant_note` (text, the applicant's own words), `review_note` (text, the owner's words — deliberately separate fields so applicants and reviewers can never overwrite each other; schemas bound both to ≤200 chars), `reviewed_at` (timezone-aware)/`reviewed_by` nullable (`reviewed_by` FK→users, RESTRICT), `created_at`. History rows are never edited by clients. |
| `app/models/app_setting.py` | `app_settings` | `key` VARCHAR(64) unique index, `value` VARCHAR(100) (plain text — validity is enforced by the application layer: the policy reader in `core/policy.py` fails closed on anything unexpected, and only `set_policy` ever writes), `updated_by` FK→users nullable, timestamps. One row today (`social_requires_verification`); the shape generalizes to future runtime config. |
| `app/models/setting_change.py` | `setting_changes` | `setting_key`, `old_value` nullable, `new_value`, `changed_by` FK→users, `created_at`. **Append-only**: no update/delete path exists anywhere in the code. |

`app/models/__init__.py` registers all three so Alembic autogenerate and
metadata see them.

---

## 2. Migration — `alembic/versions/3e285edb0896_add_identity_verification_foundation.py` (new)

*`upgrade()` — no guard needed, by construction:*
adds the two `users` columns with `server_default` so every existing row
is backfilled to `unverified`/`user` in the same statement that adds the
column, then creates the three new tables. No pre-existing value can
violate the new CHECKs (the columns are new — old rows simply receive the
defaults), which is why this direction carries **no** data guard (the
reverse of the Phase 6 category CHECK, where legacy *data* could violate a
*new* constraint).

*`downgrade()` — guarded first (the Phase 4/5 discipline):* counts
verification requests, policy rows, audit rows, **and** users with a
non-default state/role *before any schema change*; if any exist it raises
`RuntimeError: Refusing to downgrade migration 3e285edb0896: <exact
census> … no schema changes were made …`. Dropping the columns/tables
underneath that data would orphan it, so the refusal forces an explicit
data-handling decision instead. Only when everything is back at defaults
does the downgrade drop the tables, constraints, and columns.

**Applied & proven against the real dev database `roamlary_dev`:**

```
upgrade head            → 3e285edb0896 (head); tables present
live guard demo         → data in place (4 requests, 1 setting, 2 audit
                          rows, 3 non-default users) → downgrade exit 1
                          ("Refusing to downgrade migration
                          3e285edb0896: … 4 verification request(s), 1
                          setting row(s), 2 audit row(s) and 3 user(s) …
                          no schema changes were made"); verified
                          unchanged: version still 3e285edb0896 (head),
                          counts identical
my test data deleted    → scoped cleanup of this phase's own rows only
                          (a pre-existing owner-acknowledged row was
                          left untouched — see §7)
downgrade (clean)       → exit 0 (only default-state data present)
upgrade head (clean)    → exit 0; alembic current → 3e285edb0896 (head);
                          pre-existing row survived with backfilled
                          defaults; phase tables empty (0/0/0)
```

---

## 3. Policy & rate-limit core

### 3.1 `app/core/policy.py` (new) — fail-closed by design

One question, one answer: *does social access require a verified
account?* The answer lives in `app_settings` (row key
`social_requires_verification`), **not** an environment variable, because
the brief requires a runtime, owner-changeable, audited policy.

`get_policy(db)` — read on **every** gated request (one indexed SELECT):

| Row state | Effective answer |
|---|---|
| row missing | `True` (secure default: verification required) |
| `"true"` | `True` |
| `"false"` | `False` |
| anything else (corrupt) | `True` — **a broken read never opens the gate** |

`set_policy(db, value, changed_by)` — the **only** writer:
validates to `true`/`false`, upserts the row, and appends the
`setting_changes` audit row (`old_value`, `new_value`, `changed_by`) in
the **same transaction** — a change and its audit record cannot come
apart. The first-ever write audits `old_value = NULL` ("there was no
setting before"). A no-op write (setting the value it already has) touches
**nothing**: no `updated_by` churn, no audit row. It deliberately never
touches `users.verification_status` or any historical review row —
changing policy never auto-verifies anyone (tested).

### 3.2 `app/core/rate_limit.py` (new) — in-process throttle

A minimal fixed-window counter (timestamp deque per key, lock-guarded).
Used only by the policy PATCH endpoint: **5 accepted-or-rejected-at-limit
attempts per owner per rolling hour → the 6th raises 429.** It is
in-process by necessity — the architecture has no shared rate-limit store
(one dev server, one process), and adding Redis/DB-backed limiting would
be a new infrastructure dependency outside this phase's scope. The
limitation is documented (README + report §14). Requests rejected earlier
(403 owner-gate, 422 validation) never reach the limiter and therefore do
not consume attempts.

---

## 4. Schemas — what clients may send and ever see back

### 4.1 `app/api/v1/schemas/verification.py` (new — 7 schemas)

| Schema | Direction | Fields / rules |
|---|---|---|
| `VerificationRequestCreate` | body in | exactly one optional `note` (≤200, trimmed, blank→`None`); `extra="forbid"` → `{"status": …}`/`{"user_id": …}`/any document field = **422** |
| `VerificationRequestSummary` | out (submitter) | `id`, `status`, `created_at`, `reviewed_at`, `review_note`, `applicant_note` — **6 fields**, UTC |
| `VerificationStatusResponse` | out (status route) | `verification_status`, `role`, `social_access_required` (live policy echo), `latest_request` (`VerificationRequestSummary \| None`) — the caller's OWN picture only |
| `VerificationRequestReview` | out (owner only) | 9 fields: summary + `user_id`, `display_name`, `reviewed_by` — the only shapes that ever disclose who a request belongs to, reachable only through owner-gated routes |
| `ReviewActionRequest` | body in | optional `review_note` (≤200, trimmed); `extra="forbid"` |
| `PolicyResponse` | out (owner only) | `key`, `requires_verification`, `updated_at`, `updated_by` |
| `PolicyUpdateRequest` | body in | exactly one boolean `requires_verification`; `extra="forbid"` |

**No identity-data schema exists** — there is no field, anywhere, for an
ID number, document, or scan. `UserProfile` (Phase 3) was deliberately
**not** modified: verification state is visible only via
`GET /verification/status`, so profile consumers are unaffected.

### 4.2 `app/api/v1/schemas/social.py` (new)

`DiscoveryResponse` = `profiles: list` (always empty this phase) +
`message: str` (the honest "not implemented yet (Phase 7)" text). No user
data of any kind is ever placed in it.

---

## 5. Gates — `app/api/v1/deps.py` (modified)

Two new reusable dependencies, composed from the existing
`get_current_user` (JWT/auth itself is **unchanged**):

- **`require_owner`** — demands an exact `role == owner` match (else
  **403** "Owner privileges required for this action."). Fail-closed by
  construction: an unknown/corrupt role value is *denied*, never elevated.
- **`require_verified_user`** — order is intentional: (1) authenticate →
  401; (2) read the **live** policy (fail-closed); (3) policy off → every
  authenticated account passes; (4) policy on → only `verified` passes;
  anyone else gets **403** with a status-specific, actionable message
  (unverified → "submit a verification request first
  (POST /api/v1/verification/requests)"; pending → "your request is under
  review"; rejected → "you may submit a new one"; corrupt status → generic
  fail-closed message).

`OwnerUser` / `SocialUser` are the `Annotated` aliases route handlers use.
The safety/account routes (contacts, check-ins, SOS, reports, profile,
verification itself) deliberately do **not** use `require_verified_user` —
incomplete verification must never lock anyone out of safety tools (a
dedicated test asserts this).

---

## 6. Endpoints — 7 new routes

### 6.1 `endpoints/verification.py` (new) — caller's own account, never gated

| Route | Behaviour |
|---|---|
| `GET /api/v1/verification/status` | 200 for any authenticated role/state: own `verification_status`, own `role`, live `social_access_required`, own latest request. No user-id parameter exists — asking about someone else is structurally impossible |
| `POST /api/v1/verification/requests` | 201; allowed only from `unverified`/`rejected`; server sets request `status=pending` **and** moves the account to `pending` in the **same transaction**; `409` while `pending` or already `verified`; `422` on injected fields |

The only collected datum is the optional ≤200-char `note`.

### 6.2 `endpoints/admin.py` (new) — every route behind `require_owner`

| Route | Behaviour |
|---|---|
| `GET /api/v1/admin/verification-requests` | review queue, **oldest submitted first** (FIFO); optional `?status=pending\|approved\|rejected` (unknown → 422), `?offset≥0`, `?limit` 1–100 (default 20) |
| `POST …/{id}/approve` | 200; request → `approved`, account → `verified`, `reviewed_at` + `reviewed_by` recorded — all in one transaction; **compare-and-set on `pending`** so two racing reviewers cannot both decide (loser gets 409) |
| `POST …/{id}/reject` | same shape; request → `rejected`, account → `rejected` (the applicant may then re-submit) |
| `GET /admin/policy/social-verification` | 200: effective value + `updated_at`/`updated_by` (fail-closed reporting) |
| `PATCH /admin/policy/social-verification` | 200: validated boolean → rate limit (429) → `set_policy` (audit) → response. Never touches users or history |

Shared review rules: **404** unknown id · **409** not `pending` ·
**409** "You cannot review your own verification request" — self-review is
refused for *everyone*, owner included (no self-elevation, ever; with a
single owner that means the owner's own account stays `unverified` through
the API — documented limitation, §7).

### 6.3 `endpoints/social.py` (new) — the gated placeholder

`GET /api/v1/social/discovery` behind `require_verified_user` returns
`{"profiles": [], "message": "…not implemented yet (planned for
Phase 7+)…"}`. It exists this phase so the gate is enforced by a **real**
endpoint that can be tested end-to-end; Phase 7 replaces the body and
keeps the same gate.

---

## 7. Owner provisioning — `app/cli.py` (new)

```
.venv\Scripts\python -m app.cli make-owner someone@example.com
```

The **only** supported way to grant `owner`: it requires shell access to
the machine holding the database credentials — the strongest boundary the
project has. Registration always creates `role="user"`; no endpoint, body
field, or header can change a role (422 on injection); email address,
signup order, or knowing project details grants nothing. Properties:
prints only email + result (never `DATABASE_URL`, passwords, tokens),
idempotent (already-owner → no change), exit code 0/1 (script-friendly),
`LookupError` → `FAILED: no account with that email` on stderr. No
hardcoded credentials, no secret answers, no email-list bootstrap
anywhere in the phase.

---

## 8. Router — `app/api/v1/router.py` (modified)

Three imports + three `include_router` calls; OpenAPI confirms exactly
**7** new paths (`/verification/status`, `/verification/requests`,
`/admin/verification-requests[/{id}/approve|/reject]`,
`/admin/policy/social-verification`, `/social/discovery`). All other
routes untouched.

---

## 9. Tests

### 9.1 `tests/test_verification.py` (new — 20 tests)

New-account default state + gate on · status requires auth · status
response exposes only own safe fields · register cannot send
`role`/`verification_status` · profile update cannot change either ·
submit body cannot choose status/target · submit → `pending` + request row
· empty body & blank-note collapse · note length bound · duplicate-while-
pending 409 · submit-while-verified 409 · resubmit-after-rejection allowed
· discovery requires auth · unverified/pending/rejected each denied with
their specific 403 · verified passes after owner approval · **owner role
does NOT bypass the gate** · safety/account workflows stay open while
unverified · no cross-user discovery leak via the status route.

### 9.2 `tests/test_admin.py` (new — 19 tests)

Auth required on all admin routes · ordinary user 403 everywhere · queue
oldest-first + exact shape · queue status filter + invalid filter 422 ·
pagination bounds · review outcomes record reviewer identity · unknown id
404 · invalid transitions 409 · **owner cannot review own request** ·
approve/reject work without a body · reject outcome visible to applicant ·
policy default requires verification · policy change records who/when/
old/new · no-op change writes no audit row · invalid policy body 422 ·
policy change rate-limited (429 on 6th attempt) · policy change does not
auto-verify anyone or rewrite history · policy off opens gate / on closes
it · corrupt policy value fails closed.

### 9.3 Modified test files

- `tests/conftest.py` — `insert_raw_user_and_verification` raw-SQL probe
  helper (same purpose as the Phase 6 report helper; lets the migration
  tests create rows with specific states/roles).
- `tests/test_migrations.py` — **+4**: new columns exist with CHECKs and
  secure server defaults; downgrade **refuses** while verification/
  policy/audit data or non-default users exist (SQLite, pinned
  revisions); clean downgrade→upgrade roundtrip; expected-tables list +3.
- `tests/test_models.py` — **+4**: the three enums' exact value contracts,
  the two `users` CHECK constraints' existence in metadata,
  expected-tables list +3.
- `tests/test_postgres_integration.py` — **+5**: role/status CHECK
  enforcement on real PostgreSQL (valid values ok, bogus values →
  `IntegrityError`), downgrade guard refusal with data, and a
  downgrade→upgrade roundtrip with clean data.

### 9.4 Actual results (no fabricated numbers, no skipped tests counted as passed)

| Run | Output |
|---|---|
| `pytest tests/test_verification.py -q` | **20 passed** |
| `pytest tests/test_admin.py -q` | **19 passed** |
| `pytest --collect-only -q` | 245 collected (193 baseline + 52 new) |
| Full suite (SQLite + real PostgreSQL, `ROAMLARY_TEST_DATABASE_URL` set) | **245 passed, 0 failed, 0 skipped** (221 offline + 24 PG) in 120.83s — final run after all documentation edits |
| `ruff check .` / `ruff format --check .` | All checks passed! / 64 files already formatted |
| Live E2E vs `roamlary_dev` (full app stack) | **54/54 functional checks passed** (details in report §13.10) |
| Live migration-guard demo vs `roamlary_dev` | refusal with exact census (exit 1), verified unchanged (head + counts identical) |
| Live clean downgrade→upgrade roundtrip vs `roamlary_dev` | exit 0 / exit 0, final state `3e285edb0896 (head)` |
| Blocked tests | none |

**Checks NOT performed** (honest difference): no real identity provider
of any kind; no email/notification delivery (none claimed); no
multi-process/multi-instance rate-limit behaviour (single dev process
only); no load/security-penetration testing; no frontend integration
(Flutter untouched); no test exercised anything except SQLite (fast
tests), the disposable `roamlary_test` PostgreSQL database (integration
tests), and the local `roamlary_dev` server (live E2E script).

**Fixed during the phase (recorded honestly):** the first live E2E run
failed at the account step with 401s on the server's own tokens. The
cause was a **bug in my E2E script, not the app**: it passed a header
dictionary where a raw bearer-token string was expected, producing
`Authorization: Bearer {'Authorization': …}` — an invalid JWT. A
standalone probe (register → `/users/me` → login → local decode with the
`.env` secret) proved the server's auth worked correctly end-to-end;
after fixing the script's `call()` helper, the run was 54/54. No
application code was changed to make it pass. Separately, one intermediate
full-suite invocation reported "221 passed, 24 errors": all 24 were
*setup* errors caused by my one-off shell command leaving a stray `=` at
the front of `ROAMLARY_TEST_DATABASE_URL` (off-by-one while parsing
`.env`) — re-run with the variable parsed correctly it is 245/0/0. Again,
no application code or test was changed.

---

## 10. Known limitations & outstanding issues

- **Manual review only:** no Aadhaar/ID/any identity data is collected
  anywhere, and no real verification provider is integrated — "verified"
  means an owner read a short note. A real provider is required before
  any production claim.
- **Single-owner self-review deadlock:** the owner cannot approve their
  own request (by rule), so with exactly one owner that account stays
  `unverified` through the API. A second reviewer or a deliberate
  server-side DB action is the documented escape.
- **In-process rate limiter:** 5/hour/owner policy changes reset on
  restart and are per-process — fine on one dev machine, revisit before
  multi-process deployment.
- **States are exactly** `unverified/pending/verified/rejected` (+ request
  `pending/approved/rejected`): no `expired`/`requires_review`; extending
  means a migration.
- **The social surface is a placeholder** (empty discovery list) until
  Phase 7; report moderation remains untouched (reports stay `pending`).
- **No client UI** for any of this yet (Phase 9); no email/notification
  claims.
- Passing tests are **not** a security audit or a production claim —
  this remains a local hackathon prototype.

---

## 11. Scope confirmation — NOT implemented

- ❌ Aadhaar/ID numbers, document uploads, scans, or any sensitive
  identity data — in requests, tables, fixtures, logs, or this document
- ❌ real identity-provider integration (or any external API call)
- ❌ discovery/chat/events/AI implementation (one gated **placeholder**
  route only, per the owner's explicit decision)
- ❌ Flutter/frontend changes (`frontend/` untouched)
- ❌ SOS lifecycle changes (Phase 5 schema/endpoints untouched)
- ❌ report moderation changes (reports still `pending`-only)
- ❌ email/SMS/push notifications of any kind — and no claim that
  anything was delivered
- ❌ self-verification paths: no request/profile/client value can set
  `verified` (or any state/role) — enforced by schema (422), gates (403),
  DB CHECKs, and tests
- ❌ email- or registration-order-based privilege grants; hardcoded
  credentials; secret answers
- ❌ commits, pushes, merges, branch changes, resets, stashes during the
  phase (HEAD still `9939515`)

---

## 12. Evidence summary

| Claim | Where it was verified |
|---|---|
| 7 routes exist and behave as documented | 39 new endpoint tests + 54/54 live E2E on real PostgreSQL |
| Users can never self-verify or set roles | strict-schema 422 tests (register/profile/submit), DB CHECK tests, submit-409 tests, "owner role does NOT bypass gate" test |
| Social gate is server-side, reusable, fail-closed | `require_verified_user` in `deps.py` + corrupt-policy fail-closed test + per-status 403 tests + policy off/on flip test |
| Safety/account workflows stay open while unverified | dedicated test across contacts/check-ins/SOS/profile/verification routes |
| Owner-only policy: audited, rate-limited, no auto-verify | who/when/old/new audit test, no-op test, 429 rate-limit test, no-auto-verify/rewrite-history test, corrupt-value fail-closed test |
| Owner provisioning is server-side only | `app/cli.py` is the sole grant path; register/profile injections 422; CLI prints no secrets (live E2E checks) |
| Migration is data-safe both directions | upgrade needs no guard (server-default backfill), downgrade refusal + roundtrip proven on SQLite **and** real PG; live refusal demo + live roundtrip on `roamlary_dev` |
| No identity/sensitive data anywhere | no schema/field accepts or returns any (exact-field-set tests); grep-level review of all new files |
| No skipped tests counted as passed | full suite reported as **245 passed, 0 failed, 0 skipped** |
| No secrets introduced | `git diff` reviewed; `.env` gitignored and never printed |
| Working tree is the only change surface | `git status` → 11 modified + 15 new (26 files); HEAD = `origin/backend` = `9939515` |

---

## 13. Git state

- Branch **`backend`**; HEAD **`9939515`** (= `origin/backend`).
- **No commits, pushes, merges, resets, or branch switches were made
  during the phase.**
- Working tree at review time: 11 modified + 15 new files = 26 total.
- `backend/.env` remains gitignored; no secrets, tokens, or generated
  artifacts are tracked; `frontend/` untouched.
- Migration `3e285edb0896` **was applied to `roamlary_dev`** during the
  phase (schema work is live-verified, per the phase brief); the dev
  database ends at `3e285edb0896 (head)` with this phase's test data
  cleaned up.
