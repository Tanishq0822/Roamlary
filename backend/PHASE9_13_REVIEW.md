# Phases 9–13 — Complete Change Review (Meetups, House Parties, Moderation, Notifications, Sharing, SOS & AI)

Date: 2026-10-15 · Branch: `backend` · Base: `a0123dc` (= `origin/backend`)
· Migration: `b8e2f4a1c6d9` (applied to `roamlary_dev`)
· Tests: **472 passed, 0 failed, 0 skipped** (430 offline + 42 real-PostgreSQL)
· Live E2E on `roamlary_dev`: **30/30 checks passed**
· Commits during implementation: **none** (owner rule — see §9)

## How to review (30 seconds)

```powershell
# From the repository root, on branch `backend`:
git status --short            # 22 modified + 24 untracked files, all under backend/
git diff --stat backend/      # modified-file delta sizes

# Consolidated suite (offline; PostgreSQL tests skip without the env var):
cd backend
.venv\Scripts\python -m pytest tests -q --ignore=tests\test_postgres_integration.py
# → 430 passed

# PostgreSQL integration (URL derived from backend/.env — never printed):
# set ROAMLARY_TEST_DATABASE_URL to the roamlary_test database, then:
.venv\Scripts\python -m pytest tests\test_postgres_integration.py -q
# → 42 passed

# Lint:
.venv\Scripts\python -m ruff check app tests     # → All checks passed!
```

The full engineering record is `report.md` §18 (audit §18.1, design
§18.2, file log §18.3, migration §18.4, lifecycles §18.5–§18.8,
security §18.9, tests §18.10, live §18.11, limits §18.12, regression
§18.13, git §18.14). This file is the condensed delta review. All
Phase 0–8 records are preserved untouched except dated amendments
(§14.11 race fix already noted in Phase 8; §15/§16 current-state
updates).

## Change inventory at a glance

| Area | Files | What |
|---|---|---|
| Models | 6 created, 3 modified | `meetups`, `meetup_memberships`, `event_invitations`, `meetup_announcements`, `notifications`, `trip_shares` + 8 enums + report/SOS audit columns |
| Migration | 1 created | `b8e2f4a1c6d9` (additive + CHECK widening; downgrade data-guarded) |
| Services | 3 created | `events.py` (shared rules), `notifications.py` (honest states), `ai_provider.py` (mock/unavailable) |
| Schemas | 3 created, 2 extended | `meetup.py`, `sharing.py`, `ai.py`; report `reviewed_at` + moderate; SOS `acknowledged_at` |
| Endpoints | 5 created, 3 extended | `meetups.py` (14 routes), `parties.py` + invitations (12), `notifications.py` (3), `trip_shares.py` (5), `ai.py` (2); report moderate, SOS ack/retry/listing, check-ins overdue |
| Config | 1 modified + example | `AI_PROVIDER`/`AI_API_KEY`/`AI_TIMEOUT_SECONDS` (neutral defaults) |
| Tests | 5 created, 6 extended | 66 new tests (61 offline + 5 PG) |
| Docs | 2 modified, 1 created | README (7 sections + tables + troubleshooting), report.md §18, this file |

## 1. Audit first

Phase 8 verified present as commit `a0123dc` (clean tree, migration
`7f3a9c1e5b42`, routes live) — nothing to recover, no resets. Audit
confirmed greenfield for events/invitations/notifications/shares/AI
(only unrelated word matches), reusable gates/patterns throughout, and
genuine gaps only where claimed: report moderation endpoint, SOS
acknowledgement/attempt observability, overdue surfacing, and the AI
surface itself. No provider, key, or frontend app exists (template
only — backend priority, zero frontend changes).

## 2. Models & migration

- **`meetups`** (shared Phases 9–10 foundation): kind/status/
  visibility/participation/category/capacity/date CHECKs, public
  `location_text` + gated `venue_details`, discovery index.
- **`meetup_memberships`**: UNIQUE (meetup, user); requested/approved/
  declined/removed/left with `decided_at`/`decided_by` audit.
- **`event_invitations`**: UNIQUE (meetup, invitee); pending/accepted/
  declined/revoked/expired (re-invite reuses the row — no replay).
- **`meetup_announcements`**: host-only one-way bulletins (no replies —
  no group chat by design).
- **`notifications`**: UNIQUE idempotency key; honest status set;
  attempts + last_error; in-app is the only delivering channel.
- **`trip_shares`**: owner + optional plan + expiry (≤90 days) +
  revocation; viewers resolved live (accepted partners only).
- **Report/SOS columns**: `reviewed_by`/`reviewed_at`,
  `acknowledged_at`; status CHECK widened with `resolved` (additive).
- Migration `b8e2f4a1c6d9`: upgrade unguarded (new tables + widening);
  downgrade data-guarded (6 tables + `resolved` census). Proven on
  SQLite (batch path), PostgreSQL, and live. Model↔migration index
  names verified equal; 21 tables total.

## 3. Services

- **`services/events.py`**: visibility/venue/serialization/capacity/
  ended/block rules shared by meetups + parties (no drift).
- **`services/notifications.py`**: `record_notification()` (closed
  kind set, idempotent get-or-create, UNIQUE index as truth) +
  `reattempt()` (same row, attempts+1); `NullProvider` records honest
  `unavailable`. Provider acceptance without receipt → `unknown`, never
  `delivered`.
- **`services/ai_provider.py`**: `AIProvider` surface;
  `UnavailableProvider` default (explicit message, verified=false);
  `MockProvider` for tests (deterministic, no network/cost);
  `select_provider()` central mapping. Keys server-side only.

## 4. Endpoints — 35 new paths (84 OpenAPI paths total, live-verified)

- **Meetups** (14): create/discover/get/patch/cancel/complete/join/
  participants/approve/reject/leave/remove/announcements×2. Social gate
  throughout; capacity enforced at join + approve (PG row lock) +
  UNIQUE backstop + edit floor; blocked hosts vanish; ended events
  refuse at read time.
- **House parties** (9) + **invitations** (3): forced-private
  immutable kind/visibility; never in discovery/search; outsider 404s
  (no id enumeration); venue gated to host + approved; invite
  eligibility + block collapse (404); UNIQUE pair (no duplicates/
  replay); atomic accept with capacity recheck; blocks freeze accepts.
- **Moderation** (1, owner-only): lifecycle pending→approved|rejected,
  approved→resolved|rejected, terminal lock, audit stamps, identity-free
  responses, `resolved` list filter.
- **Notifications** (3): own inbox, idempotent read, in-place retry of
  failed/unavailable only.
- **Trip shares** (5): bounded creation (own plans, ≤90-day future
  expiry), owner history, accepted-partner itinerary (plan facts only,
  no GPS), instant owner revocation, server-side expiry.
- **SOS** (+3): owner acknowledge (compare-and-set; still closes),
  per-contact honest attempts at activation (idempotent, persistence
  never gated), in-place retry (active only), observable listing.
- **Check-ins** (+1): read-time overdue listing (no jobs, no alerts).
- **AI** (2): status (boolean, never keys); chat (own-trip context,
  20/hour, stable unavailable contract, honest 503s).

## 5. Tests

| File | Tests | Covers |
|---|---|---|
| `test_meetups.py` (new) | 17 | validation/gates, discovery + party exclusion, open/approval joins, capacity + DB race proof, host powers, leave/rejoin/remove, cancel freeze + notify, capacity floor, bulletin tiers, blocked exclusion, create 429 |
| `test_parties.py` (new) | 13 | forced-private + invisibility + immutability, outsider 404s, invite→accept + venue gating, recipient validation, duplicate + DB race proof, decline→reinvite, revoke, full-party pending kept, blocked 404, cancelled freeze, invitee-only answers |
| `test_moderation.py` (new) | 8 | lifecycle + stamps + identity-free, owner gate, rejected hidden, resolved filter, SOS acknowledge, honest attempts, idempotent retry, SOS privacy |
| `test_notifications.py` (new) | 7 | inbox/gates, read/retry states, cross-user 404s, share lifecycle + validation, partner-visible share, stranger/expiry/revoke exclusion |
| `test_ai.py` (new) | 6 | unavailable default + footers, mock with context, foreign-plan 404, validation/gates, policy-ON 403, rate-limit 429 |
| `test_check_ins.py` (+1) | 22 | overdue read-time listing |
| `test_models.py` (+6 → 34) | | EXPECTED_TABLES +6, FK/CHECK/UNIQUE metadata, enum contracts |
| `test_migrations.py` (+3 → 23) | | upgrade/guard/roundtrip for the new revision |
| `test_postgres_integration.py` (+5 → 42) | | UNIQUEs, resolved CHECK, PG guard + roundtrip |
| `test_reports.py`, `test_sos_events.py` | same counts | pinned shapes extended with additive fields |

### Actual results (2026-10-15, real output)

```text
ruff format: 107 files left unchanged          ruff check: All checks passed!
pytest tests -q --ignore=tests\test_postgres_integration.py
→ 430 passed in 163.81s                       (Phase 8 baseline 369 → +61)
pytest tests\test_postgres_integration.py -q
→ 42 passed in 123.88s                        (baseline 37 → +5)
```

Mid-phase failures fixed honestly (never skipped, none weakened):
ambiguous `CommunityReport.user` FKs (scoped both sides); blank-title
NULL slip (dedicated rejecting validators); `TrustedContact.owner_id`
misname; 90-day epsilon; `NotificationRead.from_attributes`; SQLite
batch-mode for report changes; old head pins repointed; PG-vs-SQLite
downgrade transactional difference documented in-test.

## 6. Live verification on `roamlary_dev` (30/30, real output)

`alembic upgrade head` → `b8e2f4a1c6d9 (head)`; server restarted;
health byte-identical; 84 OpenAPI paths. Two throwaway accounts +
owner CLI + policy toggles: meetup 201 → discovered → join requested
→ approved → bulletin posted/read; party forced private → absent from
discovery → invite 201 → venue hidden → accept → venue visible; report
→ approved w/ stamp → resolved; contact → SOS 201 → attempt
`unavailable` → acknowledged → inbox lists it; share created; check-in
created → overdue empty; AI status unconfigured → unavailable answer;
policy restored ON. Cleanup verified (0 `live-*` rows,
`user@example.com` sole user, 0 rows in all 16 feature tables, policy
ON). Static UI :3000 serves 200 (frontend untouched).

## 7. Known limitations

No group chat/events/search/attachments; no external delivery (honest
`unavailable`); no live GPS (plan facts + check-in states only); no
background jobs (read-time expiry/overdue); terminal moderation states
lock (new reports correct mistakes); in-process limiters keep all
caveats; AI has no real provider (mock/unavailable only — needs config
+ implementation behind `select_provider`); no client UI (Phase 14);
capacity race = PG row lock + UNIQUEs. No safety claims anywhere.

## 8. Scope confirmation — NOT implemented (deliberately)

Frontend/UI, offline AI tunnels, new identity-verification provider,
emergency-service dispatch, background camera/mic monitoring, redesigns,
unrelated modules/architecture, deployment infra, dependency upgrades,
commits/pushes without approval. No delivery/AI/safety claim was
fabricated anywhere.

## 9. Git state

```text
branch: backend    HEAD: a0123dc (= origin/backend)    commits during work: none
git status --short → 22 modified + 24 untracked files (all under backend/)
```

The exact per-file list is reproduced in `report.md` §16.9. Awaiting the
owner's review; on approval the change set will be committed/pushed only
on explicit instruction.
