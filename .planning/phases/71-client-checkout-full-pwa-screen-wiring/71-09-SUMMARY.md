---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: 09
subsystem: client-pwa
tags: [bugfix, camelCase-contract, adapters, seed, gap-closure]
requires:
  - "camelCase API wire contract (Pydantic alias_generator=to_camel)"
  - "packages/api-client/src/schema.d.ts Client* response shapes"
provides:
  - "PlansSheet/HomeScreen/ProfileScreen adapters aligned to camelCase API"
  - "Non-empty client catalog seed (membership_plans + pt_package_plans)"
affects:
  - "apps/client-pwa wired screens (catalog, home, profile)"
  - "apps/backend local UAT seed ergonomics"
tech-stack:
  added: []
  patterns:
    - "Export in-file render adapters for pure-function unit testing"
    - "Idempotent catalog seed via ON CONFLICT DO NOTHING on lower(name) partial-unique indexes"
key-files:
  created:
    - apps/client-pwa/src/screens/sheets/PlansSheet.adapters.test.jsx
    - apps/client-pwa/src/screens/HomeScreen.adapters.test.jsx
    - apps/client-pwa/src/screens/ProfileScreen.adapters.test.jsx
  modified:
    - apps/client-pwa/src/screens/sheets/PlansSheet.jsx
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/backend/scripts/seed_demo_data.py
decisions:
  - "Canonical API wire format is camelCase — fix the adapters, not a snake_case shim at the clientFetcher boundary (keeps PWA aligned with generated typed contract)."
  - "Seed pt_package_plans (the catalog/SKU table read by fetch_pt_packages_catalog), not pt_packages (the instance table)."
metrics:
  duration: 6m
  tasks: 3
  files: 7
  completed: 2026-05-30
---

# Phase 71 Plan 09: PWA camelCase Adapter Alignment + Catalog Seed Summary

Aligned all wired client-PWA render adapters (catalog, home membership/next-booking,
profile membership + visit/PT/payment history) to the camelCase API wire contract,
closing the UAT test-1 NaN/"undefined дней" BLOCKER and its latent siblings, and seeded
a minimal client catalog so the fix is verifiable end-to-end without a manual SQL insert.

## What Was Built

- **Task 1 — PlansSheet:** `toMembershipCard`/`toPtCard` now read `priceKopecks` /
  `durationDays` / `sessionCount` (was `price_kopecks` / `duration_days` /
  `session_count` → NaN). Adapters exported for unit testing. Kopecks→RUB math,
  badge/popular logic, and ru-RU rendering unchanged.
- **Task 2 — HomeScreen:** `toSubInfo` reads `daysUntilEnd` / `expiringSoon` /
  `startDate` / `endDate` / `planNameSnapshot`; `nextBooking` source is
  `homeData.nextBooking`; `UpcomingCard` + `HomeMinimal` read `startTime` /
  `trainerName`. WR-03 UTC-midnight parse and Europe/Moscow formatting intact.
  `toSubInfo` exported for testing.
- **Task 3 — ProfileScreen + seed:** `toSubInfo` (mirrors Home), `VisitsList`
  (`gymDate`/`checkedInAt`), `TrainingsList` (`trainerNameSnapshot`/`performedAt`/
  `cancelledAt`), `PurchasesList`/`PurchaseRow` (`amountKopecks`/`subjectKind`/
  `receivedAt`) all read camelCase. `seed_demo_data.py` idempotently seeds one active
  `membership_plans` row ("Месяц безлимит", 5000 ₽, 30 дней) and one `pt_package_plans`
  row ("5 тренировок", session_count 5, 15000 ₽) so the catalog is non-empty for local UAT.

## Verification

- Per-task grep gates: zero residual snake_case API field reads in all three screens;
  required camelCase keys present. All pass.
- Unit tests (TDD RED→GREEN per task): 6 new adapter assertions across 3 files;
  full client-pwa suite green (7 files / 19 tests).
- Backend seed: `ast.parse` OK; `ruff check` clean; `mypy` (strict) clean.
- Subject-enum string values (`'membership'`, `'pt_package'`) were correctly left
  unchanged — only the FIELD name `subject_kind` → `subjectKind` was renamed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Quality] Tightened seed helper type to AsyncSession**
- **Found during:** Task 3
- **Issue:** Initial `_seed_catalog(session: object)` annotation was loose; the repo
  mandates mypy strict (CLAUDE.md). Imported `AsyncSession` and annotated the param.
- **Files modified:** apps/backend/scripts/seed_demo_data.py
- **Commit:** ebb47f93

## Notes / Out-of-Scope

- Pre-existing esbuild "Duplicate key" warnings exist in HomeScreen.jsx (style object,
  `background`) and PushToast.jsx (`border`). Unrelated to this plan's field renames —
  left untouched per scope boundary.
- `userName` in HomeScreen/ProfileScreen intentionally left as the demo fallback
  (`'Саша'`) — real-identity binding is plan 71-10.

## Known Stubs

None introduced. Demo-only surfaces that remain (gym status pill, notifications feed,
hardcoded card `•••• 4821`, `userName` fallback) are pre-existing and explicitly
out-of-scope for this plan (notifications/identity deferred to later 71 plans).
