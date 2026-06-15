---
phase: 113-promo-codes-crud
verified: 2026-06-15T13:00:30Z
status: human_needed
score: 14/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Owner login → Тарифы → «Скидки и акции»: real codes list or empty state renders. Click «Создать промокод», fill in the modal, submit — success toast fires, modal closes, new card appears in the list."
    expected: "Card with the UPPER-cased code appears; Активен status pill; discount/usage stats correct."
    why_human: "Requires live browser session with real backend JWT; TanStack Query + Zod parse path cannot be exercised via grep or vitest."
  - test: "On the created promo card, click «Изменить» — modal opens prefilled with the promo's fields. Edit description, save — card updates."
    expected: "Edit toast fires, modal closes, PromoCard reflects updated description."
    why_human: "Requires browser interaction; prefill conversion (wire value → display value for percent/kopecks) cannot be checked programmatically."
  - test: "On an active promo card, click «Деактивировать» — ConfirmModal appears with code in message and danger tone. Confirm — card flips to Неактивен."
    expected: "«Деактивировать» button disappears on the card after deactivation (isActive=false gates it)."
    why_human: "Requires live browser interaction with confirm modal flow."
  - test: "Switch to reception session — open Тарифы. Promo codes list is visible but no «Создать промокод» button and no «Изменить»/«Деактивировать» card actions."
    expected: "Reception sees the list (real data), zero write affordances."
    why_human: "UI RBAC gating can only be confirmed visually in a live session."
---

# Phase 113: Promo Codes CRUD Verification Report

**Phase Goal:** Owner can manage promo codes directly in the admin app — create, edit, deactivate — and the Plans page displays real promo data instead of mock cards.
**Verified:** 2026-06-15T13:00:30Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Owner gets a paginated promo-code list (items/total/page/pageSize) with used_count aggregate per code | ✓ VERIFIED | `repository.list_promo_codes` returns `PaginatedData[PromoCodeListItemResponse]` with correlated scalar subquery for `used_count`; 20 integration tests pass including `test_used_count_reflects_promo_redemptions` |
| 2 | Owner can create a promo code; code is UPPER-normalized and unique among alive rows | ✓ VERIFIED | `service.create_promo_code` strips + uppers code before insert; `uq_promo_codes_code_alive` IntegrityError → 409; `test_create_code_is_uppercased`, `test_duplicate_alive_code_returns_409` green |
| 3 | Owner can edit an existing promo code's fields (including description) | ✓ VERIFIED | `PATCH /{promo_id}` endpoint wired to `service.update_promo_code`; partial edit with `exclude_unset`; `test_edit_happy_path` passes |
| 4 | Owner can deactivate a promo code (is_active=False) via PATCH /{id}/deactivate | ✓ VERIFIED | `PATCH /{promo_id}/deactivate` returns 204; `repository.deactivate_promo_code` bulk-UPDATE is_active=False WHERE deleted_at IS NULL; `test_deactivate_happy_path` green |
| 5 | Reception receives 403 on create/edit/deactivate but can read the list | ✓ VERIFIED | `(CREATE|EDIT|DELETE, PROMO_CODES)` in OWNER_ONLY; reception GET → 200; all 3 reception 403 tests in `test_promo_codes_rbac.py` pass |
| 6 | Writes without X-CSRF-Token return 403 csrf_mismatch; require_permission fires before verify_csrf | ✓ VERIFIED | RBAC-04 ordering confirmed in router.py (require_permission before verify_csrf in all 3 mutation endpoints); `test_csrf_missing_write_returns_403_csrf_mismatch` passes |
| 7 | promo_codes table has a nullable description column after migration 0072 applies | ✓ VERIFIED | `alembic current` → `0072_promo_codes_description (head)`; `PromoCode.__table__.columns['description'].nullable = True`, type `VARCHAR(500)` |
| 8 | Backend OWNER_ONLY and FE can.ts stay in parity (count 42 → 45); parity test passes | ✓ VERIFIED | `len(OWNER_ONLY) == 45` confirmed in Python; `can.ts` has 45 entries; `test_owner_only_count_is_forty_five` passes (4/4 parity tests green) |
| 9 | Plans «Скидки и акции» section lists real codes from GET /api/v1/promo-codes (mock cards removed) | ✓ VERIFIED | `PlansPage.tsx` calls `usePromoCodes({}, role)` → `staffRequest('get', '/api/v1/promo-codes')` → `PromoCodesListResponseSchema.parse`; `mockData.promos.map` block removed; grid renders `promoCodesQuery.data.items.map((p) => <PromoCard>)` |
| 10 | Empty/loading/error/403 states render correctly in the promo section | ✓ VERIFIED | `PlansPage.tsx` lines 448–495: `!canListPromoCodes` → Lock EmptyState; `isPending` → `<PageLoading />`; `promoCodesForbidden` → Lock EmptyState; `isError && !forbidden` → `<PageError>`; `items.length === 0` → empty EmptyState with create CTA |
| 11 | Owner sees «Создать промокод» and per-card «Изменить»/«Деактивировать»; reception sees none | ✓ VERIFIED | `can(role,'create','promo-codes')` gates SectionHead button; `can(role,'edit','promo-codes')` gates «Изменить»; `can(role,'delete','promo-codes') && p.isActive` gates «Деактивировать» in `PromoCard.tsx`; RBAC unit tests (can.test.ts) pass at count 45 |
| 12 | Creating/editing persists and list appears after invalidation | ✓ VERIFIED | `useCreatePromoCode` / `useUpdatePromoCode` mutations call `onSettled → qc.invalidateQueries(promoCodesKeys.lists())`; CR-01 BLOCKER fix: both use `PromoCodeWriteResponseSchema` (omits usedCount) not the list schema |
| 13 | Zod schemas match the REAL wire shapes (camelCase) returned by the backend | ✓ VERIFIED | `PromoCodeSchema` camelCase fields match `PromoCodeListItemResponse` (alias_generator); `PromoCodeWriteResponseSchema = PromoCodeSchema.omit({ usedCount: true })` matches `PromoCodeResponse`; D-V32-DRIFT-LESSON test `test_used_count_reflects_promo_redemptions` parses real response |
| 14 | RBAC parity invariant: permissions.py ↔ can.ts ↔ registry.ts ↔ test_rbac_parity.py ↔ can.test.ts all consistent at 45 entries | ✓ VERIFIED | All 5 surfaces checked: `permissions.py` 45 entries; `can.ts` 45 entries; `registry.ts` 'promo-codes' in Resource union; parity test `== 45`; can.test.ts `== 45` with promo-codes RBAC coverage; 8/8 can.test.ts pass |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0072_promo_codes_description.py` | Additive nullable description column migration | ✓ VERIFIED | `down_revision = "0071_seed_settings"`; `op.add_column` nullable String(500); applied at head |
| `apps/backend/app/modules/promo_codes/router.py` | Admin CRUD router (list/create/edit/deactivate) | ✓ VERIFIED | 4 routes; RBAC-04 ordering; no per-endpoint try/except |
| `apps/backend/app/modules/promo_codes/repository.py` | Paginated list with used_count subquery + CRUD | ✓ VERIFIED | Correlated `func.count()` scalar subquery; `list_promo_codes`, `get_alive`, `insert_promo_code`, `update_promo_code`, `deactivate_promo_code` |
| `apps/backend/app/modules/promo_codes/schemas.py` | Create/Update/ListItem/ListQuery DTOs (camelCase wire) | ✓ VERIFIED | `PromoCodeCreateRequest`, `PromoCodeUpdateRequest`, `PromoCodeListItemResponse`, `PromoCodeListQuery`, `PromoCodeResponse` all present; `model_post_init` + `model_validator` for discount + date window |
| `apps/backend/app/core/permissions.py` | Resource.PROMO_CODES + 3 OWNER_ONLY write pairs | ✓ VERIFIED | `PROMO_CODES = "promo-codes"`; `(CREATE|EDIT|DELETE, PROMO_CODES)` in frozenset; total 45 |
| `apps/admin-app/src/shared/session/can.ts` | 3 promo-codes write entries mirroring permissions.py | ✓ VERIFIED | `create/edit/delete` × `promo-codes` entries present; 45 total |
| `apps/admin-app/src/shared/session/registry.ts` | 'promo-codes' added to Resource union | ✓ VERIFIED | `'promo-codes' // NEW Phase 113` present in union type |
| `apps/admin-app/src/features/promoCodes/schemas.ts` | Zod wire schemas + create/update input schemas | ✓ VERIFIED | `PromoCodeSchema`, `PromoCodeWriteResponseSchema`, `PromoCodesListResponseSchema`, `PromoCodeCreateSchema`, `PromoCodeUpdateSchema` |
| `apps/admin-app/src/features/promoCodes/api.ts` | promoCodesKeys + usePromoCodes/useCreate/useUpdate/useDeactivate hooks | ✓ VERIFIED | All 4 hooks present; `PromoCodeWriteResponseSchema` used for mutations (CR-01 fix); `ApiError` re-exported |
| `apps/admin-app/src/components/modals/PromoCodeModal.tsx` | Create/edit promo form modal | ✓ VERIFIED | AdaptiveModal; 4 sections per UI-SPEC; percent/kopecks conversion; Zod safeParse; create/edit mode branching; error mapping |
| `apps/admin-app/src/pages/plans/components/PromoCard.tsx` | Real-data PromoCard with owner-gated actions | ✓ VERIFIED | Props `PromoCodeData + role`; `can()` gates; `StatusPill`; stat rows with real data |
| `apps/admin-app/src/pages/plans/PlansPage.tsx` | Promo section wired to real query + create button + deactivate confirm | ✓ VERIFIED | `usePromoCodes` + `useDeactivatePromoCode`; all 5 render states; `PromoCodeModal` mounted; mock block removed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/backend/app/api/v1/router.py` | `apps/backend/app/modules/promo_codes/router.py` | `v1.include_router(promo_codes_router, prefix="/promo-codes")` | ✓ WIRED | Line 62 in v1/router.py |
| `apps/backend/app/modules/promo_codes/repository.py` | `PromoRedemption.promo_code_id` | Correlated count subquery for used_count | ✓ WIRED | `func.count()` scalar subquery on `PromoRedemption.promo_code_id == PromoCode.id` |
| `apps/backend/tests/integration/test_rbac_parity.py` | `permissions.py` + `can.ts` | Set-equality parity assertion | ✓ WIRED | `test_owner_only_count_is_forty_five` asserts both sides == 45; 4/4 tests pass |
| `apps/admin-app/src/pages/plans/PlansPage.tsx` | `/api/v1/promo-codes` | `usePromoCodes` hook | ✓ WIRED | `staffRequest('get', '/api/v1/promo-codes')` in queryFn |
| `apps/admin-app/src/features/promoCodes/api.ts` | POST/PATCH `/api/v1/promo-codes` | `staffRequest` with auto X-CSRF-Token | ✓ WIRED | All 3 mutation hooks use `staffRequest` with correct paths |
| `apps/admin-app/src/pages/plans/components/PromoCard.tsx` | `can(role, 'edit'\|'delete', 'promo-codes')` | Owner-gated action buttons | ✓ WIRED | `can(role,'edit','promo-codes')` line 105; `can(role,'delete','promo-codes') && p.isActive` line 114 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `PlansPage.tsx` — promo section | `promoCodesQuery.data.items` | `usePromoCodes({}, role)` → `staffRequest('get', '/api/v1/promo-codes')` → `PromoCodesListResponseSchema.parse` | Yes — DB query via `repository.list_promo_codes` with used_count correlated subquery | ✓ FLOWING |
| `PromoCard.tsx` | `promo: PromoCodeData` | Passed from `PlansPage` via `promoCodesQuery.data.items.map` | Yes — real wire data validated by `PromoCodeSchema.parse` | ✓ FLOWING |
| `useCreatePromoCode` / `useUpdatePromoCode` | mutation response | `PromoCodeWriteResponseSchema.parse((raw).data)` | Yes — backend returns `PromoCodeResponse` (no usedCount); CR-01 fix ensures correct schema used | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 20 promo_codes integration tests pass | `cd apps/backend && uv run pytest tests/integration/promo_codes/ -q` | 20 passed in 6.63s | ✓ PASS |
| RBAC parity test (count 45) | `uv run pytest tests/integration/test_rbac_parity.py -x -q` | 4 passed in 1.05s | ✓ PASS |
| mypy --strict on promo_codes module | `uv run mypy --strict app/modules/promo_codes/ app/core/permissions.py app/api/v1/router.py` | 8 source files, no issues | ✓ PASS |
| ruff on promo_codes module | `uv run ruff check app/modules/promo_codes/` | All checks passed | ✓ PASS |
| import-linter contracts | `uv run lint-imports` | 3 contracts kept, 0 broken | ✓ PASS |
| Frontend TypeScript check | `pnpm exec tsc -b --noEmit` | No output (clean) | ✓ PASS |
| Frontend vitest (355 tests) | `pnpm exec vitest run --silent` | 28 test files, 355 tests passed | ✓ PASS |
| can.test.ts (45 count + promo-codes RBAC) | `pnpm exec vitest run src/shared/session/can.test.ts --silent` | 8 passed in 3ms | ✓ PASS |
| Frontend production build | `pnpm run build` | Built in 3.27s | ✓ PASS |
| OWNER_ONLY == 45 at runtime | `python -c "from app.core.permissions import OWNER_ONLY; print(len(OWNER_ONLY))"` | 45 | ✓ PASS |
| Migration at head + description column present | `uv run alembic current` + `python -c "..."` | `0072_promo_codes_description (head)`, nullable=True, VARCHAR(500) | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` found for this phase; conventional probe discovery yielded no results.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PROMO-01 | 113-01, 113-02, 113-03 | Owner can create, edit, and deactivate/archive promo codes (percentage or fixed, with limits) via the Plans page, persisted to the existing promo_codes backend | ✓ SATISFIED | Router POST/PATCH/PATCH-deactivate endpoints; PromoCodeModal; owner-gated actions in PromoCard; 20 integration tests green |
| PROMO-02 | 113-01, 113-02, 113-03 | Plans «Скидки и акции» section lists real promo codes from the backend (replacing mock cards) | ✓ SATISFIED | `usePromoCodes` → `staffRequest('/api/v1/promo-codes')`; `mockData.promos.map` block removed; `promoCodesQuery.data.items.map` renders real PromoCards |

No orphaned requirements — traceability table in REQUIREMENTS.md maps PROMO-01/02 → Phase 113, both marked `[x] Complete`.

### Review Findings Status (from 113-REVIEW.md)

All review findings from 113-REVIEW.md were addressed in commits 50d635a9..cf441c95:

| Finding | Severity | Commit | Status |
|---------|----------|--------|--------|
| CR-01: FE write response parsed with wrong schema (usedCount required, backend omits it) | BLOCKER | 50d635a9 | FIXED — `PromoCodeWriteResponseSchema = PromoCodeSchema.omit({ usedCount: true })` |
| WR-01: Update schema missing percentage ≤ 100% cap | WARNING | 6d9a4ba1 | FIXED — `_validate_effective_discount` in service.py enforces cap on merged values |
| WR-02: No backend validation that valid_until >= valid_from | WARNING | 36202705 + 6d9a4ba1 | FIXED — `model_validator(mode="after")` on create schema; merged-value check in update service |
| WR-03: discount_type change without re-validating discount_value | WARNING | 6d9a4ba1 | FIXED — `_validate_effective_discount` validates against effective merged type |
| WR-04: Generic IntegrityError can surface as opaque 500 | WARNING | 6d9a4ba1 | FIXED — known CHECK-constraint names mapped to `PromoCodeValidationError` (422) |
| WR-05: Reception canList=false causes infinite PageLoading | WARNING | 5ac7c88f | FIXED — `!canListPromoCodes` renders Lock EmptyState directly (line 450) |
| IN-01: PromoCard rendered code twice (text + chip) | INFO | a6a58a9d | FIXED — only `<code>` chip remains; plain text removed |
| IN-02: Dead hint prop (`undefined : undefined`) on valid-until field | INFO | cf441c95 | FIXED — hint prop removed entirely |
| IN-03: parseIntField returned NaN for non-integer input | INFO | d4a6e92c | FIXED — returns `undefined` for non-integer/empty input |
| IN-04: table name f-string interpolation in _read_plan_price | INFO | — | INTENTIONALLY LEFT — safe today (ternary with two literal constants); no change required |

### Anti-Patterns Found

No blockers found. Scan of all 15 phase-modified files:
- No `TBD`, `FIXME`, or `XXX` markers
- No stub implementations (`return null`, `return {}`, `return []`)
- No hardcoded empty data flowing to rendering
- No `as unknown as keyof paths` is a known intentional pattern (OpenAPI schema regeneration deferred to Phase 117; documented in api.ts docblock and 113-03-SUMMARY)

### Human Verification Required

Browser UAT is required — these items cannot be verified programmatically. Per project policy they are auto-deferred during autonomous runs but must be completed before the phase is marked fully shipped.

#### 1. Owner Create Flow (End-to-End)

**Test:** Login as owner → navigate to Тарифы → «Скидки и акции» section. Click «Создать промокод», fill fields (code, discount type, discount value, optional limits/dates), submit.
**Expected:** Success toast fires, modal closes, new PromoCard appears in the list with UPPER-cased code, correct discount display, Активен status pill.
**Why human:** Requires live browser session with JWT auth, TanStack Query fetch, Zod parse path, and Sonner toast rendering.

#### 2. Owner Edit Flow

**Test:** On an existing promo card, click «Изменить». Verify modal opens with prefilled fields (percent/rubles conversion applied correctly — e.g. wire value 1000 → display "10" for percentage). Edit description, save.
**Expected:** Edit toast fires, modal closes, PromoCard updates with new description.
**Why human:** Prefill conversion (wire → display) and modal state management cannot be verified without browser rendering.

#### 3. Owner Deactivate Flow

**Test:** On an active promo card, click «Деактивировать». Verify ConfirmModal appears with the promo code in the message and danger tone. Click confirm.
**Expected:** Card transitions to Неактивен status pill; «Деактивировать» button disappears from the card.
**Why human:** Confirm modal flow and conditional button visibility require live browser interaction.

#### 4. Reception Read-Only View

**Test:** Switch to reception session → open Тарифы. Observe «Скидки и акции» section.
**Expected:** Promo codes list renders (reception retains LIST); no «Создать промокод» button in section header; no «Изменить» or «Деактивировать» buttons on any card.
**Why human:** UI RBAC gating can only be confirmed visually in a live session; vitest covers the logic path but not the rendered output.

---

## Gaps Summary

No automated gaps. All 14 must-haves are verified. All REVIEW findings (1 BLOCKER + 5 WARNINGs + 3 INFO items) were addressed in commits 50d635a9..cf441c95. IN-04 is intentionally left as a safe pre-existing pattern.

Status is `human_needed` because 4 browser UAT items require a live session to confirm the owner create/edit/deactivate flows and the reception read-only view. These are auto-deferred during autonomous runs per project policy.

---

_Verified: 2026-06-15T13:00:30Z_
_Verifier: Claude (gsd-verifier)_
