# Roamlary — Shared Documents

This folder is for **cross-workstream documentation** that does not belong
inside `backend/` or `frontend/`.

It was empty until now — git cannot store an empty folder, so this short
README exists to make the folder's purpose visible on GitHub.

## Planned contents (future phases, not written yet)

| Planned file | Purpose | Owning phase |
|---|---|---|
| `docs/merge-report.md` | Backend ↔ frontend API-contract alignment report | Phase 9 (needs the frontend report from Laptop 2) |
| API contract exports | Frozen OpenAPI snapshots the Flutter app builds against | Phase 9 |
| Cross-laptop decision records | Agreements that affect more than one workstream | as needed |

## Where the current documentation lives meanwhile

- `backend/report.md` — the backend development log (living document,
  phase-by-phase records with real test outputs)
- `backend/README.md` — how to configure and run the backend
- `backend/PHASE4_CHANGES.md`, `backend/PHASE5_CHANGES.md`,
  `backend/PHASE6_CHANGES.md` — per-phase change reviews for the owner
- `frontend/roamlary_app/` — the Flutter application (Laptop 2's
  workstream)

Nothing in this folder contains secrets; credentials live only in
gitignored `.env` files.
