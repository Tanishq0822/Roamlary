# Phase 8 — Complete Change Review (Stranger Chat, Blocking & Account Security)

Date: 2026-10-14 · Branch: `backend` · Base: `2b52ec2` (= `origin/backend`)
· Migration: `7f3a9c1e5b42` (applied to `roamlary_dev`)
· Tests: **406 passed, 0 failed, 0 skipped** (369 offline + 37 real-PostgreSQL)
· Live E2E on `roamlary_dev`: **29/29 checks passed**
· Commits this phase: **none** (owner rule — awaiting review)

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend` (HEAD stays at 2b52ec2):
git status --short             # 19 modified + 14 untracked files, all under backend/
git diff --stat backend/       # modified-file delta sizes

# Consolidated suite (offline; PostgreSQL tests skip without the env var):
cd backend
.venv\Scripts\python -m pytest tests -q --ignore=tests\test_postgres_integration.py
# → 369 passed

# PostgreSQL integration (URL derived from backend/.env — never printed):
# set ROAMLARY_TEST_DATABASE_URL to the roamlary_test database, then:
.venv\Scripts\python -m pytest tests\test_postgres_integration.py -q
# → 37 passed

# Lint:
.venv\Scripts\python -m ruff check app tests     # → All checks passed!
```

The full engineering record is `report.md` §17 (audit §17.1, design
§17.2, file log §17.3, migration §17.4, lifecycle §17.5, blocking §17.6,
revocation §17.7, race fix §17.8, tests §17.9, live §17.10, limits
§17.11). This file is the condensed delta review. Phase 7's record (§14)
is preserved untouched except one dated amendment (§14.11) noting the
race fix.

## Change inventory at a glance

| Area | Files | What |
|---|---|---|
| Models | 4 created, 3 modified | `user_blocks`, `conversations`, `messages`, `auth_sessions` + `ConversationStatus` + `users.token_version` + travel canonical-pair columns/index |
| Migration | 1 created | `7f3a9c1e5b42` (additive + derived backfill; downgrade data-guarded) |
| Core | 2 created | `pairing.canonical_pair`, `blocks.blocked_user_ids` (shared rule) |
| Auth/session core | 2 modified | JWT `sid`/`tv` claims; per-request revocation in `get_current_user` |
| Schemas | 3 created/modified | `schemas/chat.py`, `schemas/blocks.py`, session schemas in `schemas/auth.py` |
| Endpoints | 2 created, 3 modified | `chat.py` (11 routes), `blocks.py` (3 routes), auth +5 session routes, travel send/accept block + pair integration, router +2 |
| Service | 1 modified | `services/discovery.py` block exclusion (discover + public profile) |
| Tests | 3 created, 6 modified | 67 new tests (60 offline + 7 PG) |
| Docs | 2 modified, 1 created | README (3 sections + tables + troubleshooting), report.md §17, this file |

## 1. Audit first

Phase 7 verified present as commit `2b52ec2` (the brief's "uncommitted"
note was stale) — no recovery needed, no resets. Audit confirmed: no
messaging/block/session/refresh structures existed; auth is stateless
HS256 (`sub`+`iat`+`exp`) so revocation needs the minimal session
mechanism the brief allows; the Phase 7 cross-direction race was still
open (two per-direction partial indexes only); rate limiting is
in-process only (no new infrastructure per the brief).

## 2. Models & migration

- **`UserBlock`**: blocker/blocked FKs RESTRICT, no-self CHECK, UNIQUE
  pair (racing duplicate blocks lose at the database).
- **`Conversation`**: canonical `(low, high)` UUID pair, no-self +
  status CHECKs, **UNIQUE pair** (one row per unordered pair forever —
  duplicate pending asks structurally impossible, even racing, even
  opposite-direction), `requested_by` + `responded_at`.
- **`ChatMessage`**: text-only body, sender FK, `is_deleted`/
  `deleted_at` soft delete (rows never removed), history index.
- **`AuthSession`**: user FK, optional label, `revoked_at` NULL =
  active. No fingerprinting/IP/UA anywhere.
- **`users.token_version`**: NOT NULL default 0 (backfilled in one
  statement — the secure starting point for legacy tokens).
- **Travel race fix**: `pair_low_id`/`pair_high_id` + pending-only
  UNIQUE index; dialect-aware backfill (PG LEAST/GREATEST, SQLite
  min/max — ordering verified identical to `canonical_pair`); kept
  alongside the per-direction indexes (no destructive change).
- Migration `7f3a9c1e5b42`: upgrade unguarded for new tables;
  downgrade data-guarded (refuses with row census while any Phase 8 row
  exists). Proven on SQLite, PostgreSQL, and live.

## 3. Auth & revocation

Tokens now carry `sid` (session row) + `tv` (version); every login/
register mints exactly one session row. `get_current_user` enforces
both on every request: version mismatch or missing/revoked/foreign
session row → 401 "Session has been revoked. Please log in again."
Legacy pre-Phase-8 tokens (no `sid`) are governed by the version check,
so revoke-all kills them. `decode_access_token` signature/behavior
unchanged; `CurrentSession` dependency serves "this session" endpoints.
Optional `device_label` on the strict login/register schemas (blank →
NULL).

## 4. Endpoints — 19 new routes (49 OpenAPI paths total, live-verified)

- **Chat** (`/chat`, 11): request send/list/get/accept/reject/cancel,
  conversation list/get, history (stable `(created_at, id)` order,
  limit 1–100), text send (1–2000 chars, sender always = caller),
  sender-only soft delete. Gate asymmetry mirrors Phase 7 (own-data on
  plain login; sends/accepts/history on the unchanged social gate).
  **No auto-chat from travel partners** (proven by test).
- **Blocks** (`/blocks`, 3, plain auth): block (201; 422 self, 404
  unknown, 409 duplicate), own list only, blocker-only unblock (204).
- **Sessions** (`/auth`, 5): list, logout (current dies; 410 if already
  gone; 404 for legacy), revoke-one (cross-user ids 404), revoke-others
  (preserves exactly caller), revoke-all (kills caller too + version
  bump).
- **Integration**: blocks excluded from discovery, public profiles, and
  travel send (404-collapse)/accept (409); sends rate-limited (30/hour
  asks, 60/hour messages, shared in-process mechanism).

## 5. Tests

| File | Tests | Covers |
|---|---|---|
| `test_chat.py` (new) | 24 | lifecycle, gates, duplicate/reverse 409s, terminal 409s, non-party 404s, pending-send 409, validation, stable pagination, soft delete, recent-first ordering, no-auto-chat, block freeze + readable history, blocked-ask 404s, accept-while-blocked 409, lapsed-counterparty 403, accept recheck, send 429 |
| `test_blocks.py` (new) | 12 | lifecycle, auth, self/unknown/duplicate (+DB race + CHECK proofs), blocker-only unblock, unverified blocking, discovery/profile/travel exclusions, travel-accept-while-blocked |
| `test_sessions.py` (new) | 12 | mint+list, labels, gates, logout/revoke-one/revoke-others/revoke-all, legacy kill, version-bump kill, deleted-row kill, cross-user 404s, unrelated survival |
| `test_models.py` (+8 → 28) | | EXPECTED_TABLES +4, FK/CHECK/UNIQUE/version/index metadata, enum + pairing proofs |
| `test_migrations.py` (+4 → 20) | | Phase 7 repointed, 4 Phase 8 tests incl. backfill-order proof |
| `test_postgres_integration.py` (+7 → 37) | | Phase 7 repointed, 7 Phase 8 tests incl. LEAST/GREATEST proof |
| `test_auth.py`, `test_buddy_requests.py` | same counts | deleted-user teardown respects RESTRICT; race test proves the fix |

### Actual results (2026-10-14, real output)

```text
ruff format: 84 files left unchanged          ruff check: All checks passed!
pytest tests -q --ignore=tests\test_postgres_integration.py
→ 369 passed in 155.47s                       (Phase 7 baseline 309 → +60)
pytest tests\test_postgres_integration.py -q
→ 37 passed in 104.63s                        (baseline 30 → +7)
```

Two mid-phase failures fixed honestly (never skipped): non-UUID `sub`
401 mapping after the claims refactor (fixed in `deps.py`) and the
deleted-user test teardown vs RESTRICT sessions (clears session rows
first; assertion unchanged).

## 6. Live verification on `roamlary_dev` (29/29, real output)

`alembic upgrade head` → `7f3a9c1e5b42 (head)`; server restarted;
health byte-identical; 49 OpenAPI paths. Two throwaway accounts + owner
CLI + policy toggles: gate 403s → sessions listed → ask 201 → duplicate
409 → accept 200 → messages 201/201 → paginated history → travel
profiles → travel A→B 201 → opposite travel send 409 (race fix live) →
block 201 → blocked send 403 → history readable → cross-block travel
404 → discovery exclusion → unblock 204 → policy ON → 403s → logout 200
→ logged-out 401 → B alive. Cleanup verified (0 `live-*` rows,
`user@example.com` sole user, 0 feature rows, policy ON). Static UI at
:3000 re-served from untouched `build/web` after its background shell
had ended.

## 7. Known limitations

No group chat/events/notifications/search/attachments; stateless bearer
JWTs (revocation enforced per-request at the API boundary); in-process
limiters (same caveats); Phase 7 limits unchanged (§14.11); no client UI
(Phase 9). No safety claims anywhere — chat has no safety fields at all.

## 8. Scope confirmation — NOT implemented (deliberately)

Frontend/UI, group chat, meetups/invitations, AI, notification
providers, emergency dispatch, identity providers, deployment,
refactors, dependency upgrades. No commit or push this phase.

## 9. Git state

```text
branch: backend    HEAD: 2b52ec2 (= origin/backend)    commits this phase: none
git status --short → 19 modified + 14 untracked files (all under backend/)
```

The exact per-file list is reproduced in `report.md` §16.8. Awaiting the
owner's review; on approval the change set will be committed/pushed only
on explicit instruction.
