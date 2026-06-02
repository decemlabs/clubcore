---
phase: 69-client-read-endpoints-pwa-stack-alignment
plan: "03"
subsystem: backend-tests
tags: [integration-tests, idor-sweep, client-portal, security, parametrize]
dependency_graph:
  requires:
    - 69-01 (client-portal read endpoints under test)
    - 68-client-auth-foundation (OTP auth flow, require_client())
  provides:
    - tests/integration/client_portal/ package (IDOR sweep + behavioral tests)
    - T-69-01 closed: parametrized cross-client enumeration proves no BOLA leakage
    - T-69-02 closed: 200/null empty-state tested (no existence oracle)
    - T-69-03 closed: D-69-05 trainer catalog field projection verified
  affects:
    - apps/backend/tests/integration/client_portal/ (new test package)
tech_stack:
  added:
    - tests/integration/client_portal/ (new test package: __init__, conftest, 2 test files)
  patterns:
    - SAVEPOINT IDOR sweep with both attacker/victim orderings (D-20-IDOR / CISO-04)
    - OTP auth helper reuse (_auth_as_client from client_auth/test_idor.py)
    - SeededOwnedData dataclass for structured A/B fixture assertions
    - camelCase wire format assertions (ContractModel alias_generator=to_camel, D-07)
key_files:
  created:
    - apps/backend/tests/integration/client_portal/__init__.py
    - apps/backend/tests/integration/client_portal/conftest.py
    - apps/backend/tests/integration/client_portal/test_idor_sweep.py
    - apps/backend/tests/integration/client_portal/test_read_endpoints.py
decisions:
  - "camelCase wire assertions: response keys use camelCase per ContractModel alias_generator=to_camel (D-07); test assertions updated accordingly (daysUntilEnd, expiringSoon, pageSize, subjectKind, amountKopecks)"
  - "PtPackage seeded with status='exhausted' to avoid partial UNIQUE conflict (one active per client) while still providing PT-session ownership chain for CHIST-02 sweep"
  - "near_expiry membership in conftest seeded as status='frozen' so primary /membership query (status='active') returns the far-future one; near-expiry behavioral test seeds its own fresh client with an active near-expiry membership"
  - "Visit checked_in_at offset by phone_index timedelta to keep (client_id, gym_date) UNIQUE across both clients in same test DB snapshot"
metrics:
  duration: "~7 minutes"
  completed_date: "2026-05-29"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 0
---

# Phase 69 Plan 03: IDOR Sweep + Behavioral Tests Summary

**One-liner:** Parametrized 12-case IDOR sweep and 11 behavioral tests prove the Phase 69 client-portal read surface is BOLA-free with correct temporal fields, 200/null empty states, pagination shape, refund visibility, and client-safe catalog projections.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | conftest with seeded client A/B owning all resource types | `8f6346d9` | `__init__.py`, `conftest.py` |
| 2 | parametrized IDOR sweep + behavioral read tests | `bba33b60` | `test_idor_sweep.py`, `test_read_endpoints.py` |

## What Was Built

### Task 1: Test Package + Seeded Fixtures (conftest.py)

- `__init__.py` — empty package marker.
- `conftest.py` provides:
  - `stub_client_otp_sender` autouse fixture — no-op Telegram sender (mirrors client_auth/conftest.py).
  - `redis_clean` — flushes Redis between tests.
  - `seeded_staff` — RECEPTION user for `created_by_user_id` FK.
  - `client_a` / `client_b` — two distinct Client rows with E.164 phones (+79997770001/+79997770002) and telegram_user_id links.
  - `seeded_owned_data` — `SeededOwnedData` dataclass containing `ClientOwnedData` for both clients, each seeded with: active Membership (far-future), frozen near-expiry Membership, Trainer + slot + Booking (upcoming confirmed), Visit, PtPackage (exhausted) + PtSession, Payment (positive) + Refund (negative, linked via refund_of).

### Task 2: IDOR Sweep + Behavioral Tests

**test_idor_sweep.py** (12 parametrized cases):
- `_auth_as_client` helper copied verbatim from `client_auth/test_idor.py` (OTP request → patch OtpCode hash → verify → extract cc_client_access cookie).
- `test_owned_resource_idor` parametrized over 6 endpoints × 2 orderings: membership, home, bookings, history/visits, history/pt-sessions, history/payments — both attacker_is_a=True and False.
- Per case: asserts status 200, collects all `id` fields via recursive `_extract_ids_from_data`, asserts no victim-owned ID appears in the response.

**test_read_endpoints.py** (11 behavioral tests):
- `test_membership_temporal_fields_present` — asserts `daysUntilEnd` (int ≥ 0) + `expiringSoon=False` for far-future membership.
- `test_membership_expiring_soon_true_for_near_expiry` — seeds fresh client with 3-day membership; asserts `expiringSoon=True` and `daysUntilEnd ≤ 7`.
- `test_membership_empty_state_returns_200_null` — fresh client with no membership gets 200 + data=null (D-69-03).
- `test_home_composite_empty_client_returns_null_slots` — empty client gets 200 + membership=null, nextBooking=null, expiringSoon=False.
- `test_home_composite_with_data_returns_fields` — confirms presence of membership/nextBooking/expiringSoon keys.
- `test_visit_history_pagination_shape` — asserts {items, total, page, pageSize} + total ≥ 1.
- `test_pt_session_history_pagination_shape` — same shape + ownership via pt_packages.client_id (CHIST-02).
- `test_payment_history_pagination_shape_and_refund_visible` — asserts total ≥ 2 + refund items with negative amountKopecks.
- `test_trainer_catalog_client_safe_fields` — asserts id + fullName present; phone/isActive/deletedAt/createdAt/updatedAt/rates absent (D-69-05).
- `test_plans_catalog_returns_active_items` — asserts id/name/priceKopecks/durationDays present; freezeDaysLimit absent.
- `test_pt_packages_catalog_returns_items` — asserts id/name/sessionCount/priceKopecks present.

## Verification

- `uv run pytest tests/integration/client_portal/ -q` → **23 passed** (12 IDOR sweep + 11 behavioral).
- `uv run ruff check tests/integration/client_portal/` → **All checks passed**.
- `pytest --collect-only -q` → 23 tests collected, no import/collection errors.

## Deviations from Plan

### Auto-fixed: camelCase wire format in assertions (Rule 1 - Bug)

**Found during:** Task 2 (first test run)
**Issue:** Test assertions used snake_case field names (`days_until_end`, `expiring_soon`, `page_size`, `subject_kind`, `amount_kopecks`) but the API serializes all fields as camelCase via `ContractModel.alias_generator=to_camel` (schemas.py D-07). Tests failed with `AssertionError: 'days_until_end' not in {'daysUntilEnd': 60, ...}`.
**Fix:** Updated all test assertions to use camelCase forms: `daysUntilEnd`, `expiringSoon`, `pageSize`, `nextBooking`, `subjectKind`, `amountKopecks`, `fullName`, `priceKopecks`, `durationDays`, `sessionCount`.
**Files modified:** `test_read_endpoints.py`
**Commit:** `bba33b60` (included in same task commit after fix)

### Design adaptation: PtPackage status in conftest (Rule 2 - Missing Critical)

**Found during:** Task 1 design
**Issue:** The `pt_packages` table has a partial UNIQUE constraint `uq_pt_packages_active_per_client` on `(client_id) WHERE status='active'` — only one active PT-package per client. Seeding both clients A and B with active PT-packages in the same test would conflict.
**Fix:** Seeded PtPackage with `status='exhausted'` (0 sessions remaining). This still provides the ownership chain for CHIST-02 (`pt_sessions JOIN pt_packages WHERE pt_packages.client_id = :client_id`) while avoiding the UNIQUE constraint.

### Design adaptation: Visit gym_date offset (Rule 1 - Bug prevention)

**Found during:** Task 1 design
**Issue:** Visit table has `UNIQUE (client_id, gym_date)`. If both clients have visits on the same day, seeding would fail.
**Fix:** Used `phone_index` parameter (1 for A, 2 for B) to offset `checked_in_at` by 1 or 2 days from the base date, ensuring each client's visit lands on a unique date.

## Known Stubs

None — all tests assert against real database data.

## Threat Flags

No new threat surface introduced — this plan creates test files only.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `tests/integration/client_portal/__init__.py` | FOUND |
| `tests/integration/client_portal/conftest.py` | FOUND |
| `tests/integration/client_portal/test_idor_sweep.py` | FOUND |
| `tests/integration/client_portal/test_read_endpoints.py` | FOUND |
| Commit 8f6346d9 (Task 1) | FOUND |
| Commit bba33b60 (Task 2) | FOUND |
