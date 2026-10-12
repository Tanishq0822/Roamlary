# Phase 7 — Complete Change Review (Travel Buddies, Travel Plans & Social Discovery)

Date: 2026-10-13 · Branch: `backend` · HEAD: `30977c0` (= `origin/backend`)
· Migration: `426dcef31e27` (applied to `roamlary_dev`)
· Tests: **339 passed, 0 failed, 0 skipped** (309 offline + 30 real-PostgreSQL)
· Live E2E on `roamlary_dev`: **24/24 checks passed**
· Commits this phase: **none** (owner rule — awaiting review)

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend` (HEAD stays at 30977c0):
git status                      # 13 modified + 13 untracked files, all under backend/
git diff --stat backend/        # modified-file delta sizes

# Full test suite (offline; PostgreSQL tests skip without the env var):
cd backend
.venv\Scripts\python -m pytest tests -q --ignore=tests\test_postgres_integration.py
# → 339 - 30 = 309 passed

# PostgreSQL integration (URL derived from backend/.env — never printed):
# set ROAMLARY_TEST_DATABASE_URL to the roamlary_test database, then:
.venv\Scripts\python -m pytest tests\test_postgres_integration.py -q
# → 30 passed

# Lint:
.venv\Scripts\python -m ruff check app tests     # → All checks passed!
```

The full engineering record is `report.md` §14 (audit §14.1, design
§14.2–§14.7, tests §14.9, live verification §14.10, limitations §14.11).
This file is the condensed delta review.

## Change inventory at a glance

| Area | Files | What |
|---|---|---|
| Models | 3 created, 3 modified | `travel_profiles`, `travel_plans`, `travel_partner_requests` + 3 enums + user backrefs |
| Migration | 1 created | `426dcef31e27` (additive; downgrade data-guarded) |
| Matching core | 1 created | `app/core/matching.py` — pure functions, weights sum to 100 |
| Discovery service | 2 created | `app/services/{__init__,discovery}.py` — SQL prefilter + scoring/pagination |
| Schemas | 1 created, 1 rewritten | `schemas/travel.py` (10 schemas); `schemas/social.py` over the real feed |
| Endpoints | 3 created, 1 reimplemented, 1 modified | travel_profile, travel_plans, travel_buddies; social.py over `broad_feed()`; router +3 |
| Tests | 4 created, 4 modified, 1 assertion update | 94 new tests (88 offline + 6 PG) |
| Docs | 2 modified, 1 created | README (Phase 7 section + tables + troubleshooting), report.md §14, this file |

## 1. Enums & models

### 1.1 `app/models/enums.py` (modified) — three new VARCHAR-backed enums

`TravelPlanStatus` = `active | paused | completed` ·
`PlanVisibility` = `private | discoverable` ·
`BuddyRequestStatus` = `pending | accepted | rejected | cancelled`.
Stored as `String` + named CHECK constraints (project convention — no
native PostgreSQL enums, so downgrades stay simple).

### 1.2 New model files (created)

- **`travel_profile.py`** — one row per account: `user_id` FK→users
  RESTRICT + **UNIQUE index**; optional `travel_nickname` (≤40),
  `bio` (≤200), `home_region` (≤80); JSON `languages` / `travel_styles`
  / `interests` (generic `JSON` so the SQLite offline suite keeps
  working; closed sets validated at the schema layer);
  `group_size_pref` with CHECK 2–12; `discoverable` NOT NULL default
  **false** (opt-in visibility).
- **`travel_plan.py`** — `user_id` FK RESTRICT; `destination` (≤120) +
  `destination_normalized` (NOT NULL); optional `region` (≤80) +
  `region_normalized`; `start_date`/`end_date` with CHECK
  `end_date >= start_date`; `flexible_dates` default false; `status`
  CHECK; `visibility` CHECK default `private`; composite index
  `(destination_normalized, status, visibility)` matching the discovery
  query shape + `(start_date, end_date)`.
- **`travel_partner_request.py`** — `requester_id`/`recipient_id`
  FK→users RESTRICT, CHECK `<>` (self-requests impossible); optional
  `plan_id` FK→travel_plans **RESTRICT** (the RECIPIENT's public plan as
  context; deleting a referenced plan → 409); `status` CHECK default
  `pending`; `responded_at` nullable; two **partial UNIQUE indexes**
  `(requester_id, recipient_id)` and `(recipient_id, requester_id)`
  WHERE `status='pending'` — racing *identical* sends lose at the
  database; cross-direction duplicates are endpoint-guarded (exact
  boundary in §10).
- `user.py` (modified) — three backrefs. `__init__.py` exports them.

## 2. Migration — `426dcef31e27_add_travel_profiles_plans_buddy_requests.py`

Creates the three tables exactly as the models describe them. The
**upgrade** is additive (new tables — no existing row can violate
anything, no data guard needed). The **downgrade** counts rows in all
three tables first and, while any travel row exists, raises
`Refusing to downgrade: N travel row(s) exist (…) — Export or delete
this data first … a deliberate data-handling decision` **before**
touching the schema. Proven on SQLite (subprocess Alembic) and real
PostgreSQL, offline and live.

## 3. Matching core — `app/core/matching.py` (new, pure)

No clock, no database, no AI — unit-testable directly (14 tests).
Weights (module constants, sum = 100):

| Signal | Points |
|---|---|
| Destination matches the searcher's `?destination=` filter (normalized) | +40 |
| Region matches the `?region=` filter instead | +20 |
| Date overlap with the searcher's window | +30 strict / +15 via the ±7-day flexible grace |
| Shared interests | +5 each, cap 15 |
| Shared travel styles | +5 each, cap 10 |
| Shared language | +5 |

Normalization = casefold + whitespace collapse (punctuation is **not**
stripped — documented). `ScoreBreakdown.total` caps at `SCORE_MAX = 100`.
The destination/region/date components score **the searcher's stated
filters**; an unfiltered browse ranks by shared preferences only.
**Honesty boundary (in every response `note`):** a deterministic ranking
of logistics and preferences — *never* a claim that anyone is safe.

## 4. Discovery service — `app/services/discovery.py` (new)

`discover()` = indexed SQL prefilter (eligibility states, `end_date >=`
today UTC read-time expiry, verification join while the policy requires
it, self + accepted-partner + pending-counterparty exclusion, grace-
widened date window as a documented superset) → documented Python
secondary stage (preference filters, precise strict/flexible/no-overlap
classification, scoring) → per-user dedupe (best plan; ties → earliest
start, then id) → deterministic sort `(-score, start-ordinal, user_id)`
→ offset/limit page. `MAX_CANDIDATE_ROWS = 500` hard ceiling;
`min_score` bounded 0–100; `limit` 1–100.
`public_profile_for()` = the limited projection (404 when missing **or**
not discoverable). `broad_feed()` = the ≤10-profile feed behind
`/social/discovery`.

## 5. Schemas — strict (`extra="forbid"` everywhere)

`schemas/travel.py`: profile create/patch/read (+ `completion` hints,
explicitly decoupled from verification), plan create/patch/read
(`created_at`/`updated_at` optional so discovery projections omit them),
`DiscoveryCandidateRead` (user_id + limited profile + best plan +
score + `match_breakdown` + `existing_request` state), `DiscoveryPage`
(+ honesty `note`), `PublicTravelProfileRead`, request
create/read/list. `schemas/social.py` rewritten to serve the real feed
while keeping the `{profiles, message}` wire contract Phase 6 UI work
depends on.

## 6. Endpoints — 12 new routes (33 OpenAPI paths total, live-verified)

| Route | Gate |
|---|---|
| `GET/POST/PATCH/DELETE /travel-profile/me` | plain login (own data) |
| `POST/GET /travel-plans/`, `GET/PATCH/DELETE /travel-plans/{id}` | plain login (own data; 404 identical for missing/foreign) |
| `GET /travel-buddies/discover` | **social gate** |
| `GET /travel-buddies/{user_id}` | **social gate** |
| `POST /travel-buddies/requests` | **social gate** (+ recipient eligibility + 30/hour limiter) |
| `GET /travel-buddies/requests` (+ direction/status/paging) | plain login (own history) |
| `GET /travel-buddies/requests/{id}` | plain login (party only → else 404) |
| `POST /travel-buddies/requests/{id}/accept\|reject` | **social gate** (recipient; verification rechecked live at accept → 409 if lapsed) |
| `POST /travel-buddies/requests/{id}/cancel` | plain login (requester only) |

The social gate is the **unchanged** `require_verified_user` dependency
from Phase 6 second assignment (live fail-closed policy read).
`/social/discovery` was reimplemented over `broad_feed()` — same gate,
same `{profiles, message}` contract, real data instead of the
placeholder.

Key behaviors: recipient eligibility (hidden / no profile / fails policy)
collapses to one identical **404 "Recipient not found."**; self-request
→ **422** (schema + DB CHECK); duplicate `pending`/`accepted` either
direction → **409**; terminal states locked → **409**; wrong party →
**404** (existence privacy); resend after reject/cancel allowed; deleting
a plan a request references → **409** (RESTRICT).

## 7. Tests

| File | Tests | Covers |
|---|---|---|
| `test_matching.py` (new) | 14 | normalization, window classification, every weight + cap, closed sets |
| `test_travel_plans.py` (new) | 21 | profile/plan lifecycle, 404-guidance, ownership identical-404s, date revalidation, RESTRICT 409, gate matrix, strict 422s |
| `test_discovery.py` (new) | 23 | gates, every eligibility exclusion, scoring + ranking, filters, dedupe, pagination bounds, privacy, public profile, `/social/discovery` contract |
| `test_buddy_requests.py` (new) | 21 | lifecycle, privacy 404s, terminal 409s, **DB-level** race + self-request proofs, accept-time eligibility recheck, 429 limiter |
| `test_models.py` (+6 → 20) | | travel FK/CHECK/UNIQUE/partial-index metadata, enum contracts, EXPECTED_TABLES +3 |
| `test_migrations.py` (+3 → 16) | | upgrade creates tables + partial indexes; downgrade refuses with data; clean roundtrip |
| `test_postgres_integration.py` (+6 → 30) | | native uuid + RESTRICT FK census; partial index both directions (`IntegrityError`); CHECKs; JSON roundtrip; PG downgrade guard + roundtrip |

### Actual results (2026-10-13, real output)

```text
ruff format: 72 files left unchanged          ruff check: All checks passed!
pytest tests -q --ignore=tests\test_postgres_integration.py
→ 309 passed, 3 warnings in 110.64s           (Phase 6b baseline 221 → +88)
pytest tests\test_postgres_integration.py -q
→ 30 passed in 63.07s                         (baseline 24 → +6)
```

The 3 warnings are the pre-existing Starlette 422-deprecation warning
(seen since Phase 3-era suites; unrelated).

One Phase 6b assertion changed (documented in report §14.9):
`test_verified_user_passes_gate_after_owner_approval` pinned the old
placeholder message ("Phase 7 will replace…"); it now pins the shipped
honesty message. The gate behavior it protects (403 → 200 after
approval, `{profiles, message}` shape, no fabricated users) is unchanged.

## 8. Live verification on `roamlary_dev` (24/24, real output)

`alembic upgrade head` → `426dcef31e27 (head)`; server restarted;
`/api/v1/health` returned the **byte-identical** pre-Phase-7 contract.
Two throwaway accounts + owner CLI + policy toggle walked the full path:
discover 403 while unverified → policy off → profiles + plans created →
unfiltered discovery (preferences-only score 20, exact documented
breakdown; no email/timestamps leaked) → filtered discovery scores the
full **90** (40+30+20) → send 201 → duplicate 409 → self 422 → incoming
visible → accept 200 → candidate leaves discovery → `/social/discovery`
contract kept → public profile without email → policy restored ON →
discover 403 again. Cleanup removed every `live-*` row (verified: 0
remain, `user@example.com` untouched, 0 travel rows, policy ON); the
static UI at :3000 still serves (frontend untouched).

## 9. Known limitations & outstanding issues

- No blocking system (pre-existing §12 gap) — exclusions are
  verification + discoverability + partner/pending state only.
- Cross-direction request race: the partial indexes lock each *direction*;
  two truly simultaneous opposite sends can create one pending row each
  (endpoint pre-check covers the normal path; canonical-pair expression
  index is the documented fix if ever needed).
- Destination matching is exact after casefold/whitespace normalization —
  punctuation/spelling variants do not match.
- Rate limiter (30 sends/hour/user) is in-process (resets on restart,
  per-process) — same caveat as the owner-policy limiter.
- Read-time plan expiry (no background job); preference filtering is a
  Python secondary stage (SQLite-portable JSON); `MAX_CANDIDATE_ROWS=500`
  ranking ceiling.
- No chat/messaging/notifications/events; an accepted request is a
  connection row only. No client UI (Phase 9).

## 10. Scope confirmation — NOT implemented (deliberately)

No AI matching, no external providers, no chat/blocking/notifications,
no verification-provider work (the existing `require_verified_user` gate
was reused unchanged), no sensitive identity data anywhere in any Phase 7
table or response, **zero changes under `frontend/`**, health contract
unchanged, and `main` untouched. No commit or push was made this phase.

## 11. Git state

```text
branch: backend    HEAD: 30977c0 (= origin/backend)    commits this phase: none
git status --porcelain → 13 modified + 13 untracked files (all under backend/,
incl. untracked backend/app/services/ with __init__.py + discovery.py)
```

The exact per-file list is reproduced in `report.md` §16.7. Awaiting the
owner's review; on approval the change set will be committed/pushed only
on explicit instruction.
