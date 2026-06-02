# Phase 72: OpenAPI Handoff + CI + E2E Verification — Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/main.py` (modify OPENAPI_TAGS + re-tag) | config / curation | transform | itself (existing `OPENAPI_TAGS` list L139–201) | exact |
| `apps/backend/app/modules/client_auth/router.py` (modify tag) | router | request-response | `apps/backend/app/modules/client_portal/router.py` L126 | exact |
| `packages/api-client/src/schema.contract.test.ts` (add `_v20Checks`) | test | transform | itself (`_v19Checks` block L424–440) | exact |
| `packages/api-client/src/schema.d.ts` (regen byte-stable) | generated artifact | transform | itself (previous regen cycle) | exact |
| `.github/workflows/ci.yml` (add `client-pwa` job + scope frontend) | CI config | event-driven | existing `redocly-lint` job L127–143 | exact |
| `apps/client-pwa/package.json` (verify scripts exist) | config | — | itself (L11–17) | exact |
| `.planning/handoff/clubcore-v2.0-runbook.md` (author new) | documentation | — | `.planning/handoff/clubcore-auth-runbook.md` | exact |
| `.planning/milestones/v2.0-OPERATOR-EVIDENCE.md` (author new) | evidence scaffold | — | `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` | exact |

---

## Pattern Assignments

### `apps/backend/app/main.py` — OPENAPI_TAGS edit (D-72-01)

**Analog:** `apps/backend/app/main.py` (itself), `OPENAPI_TAGS` list at lines 139–201

**Existing "Client" tag entry to rename/replace** (lines 151–156):
```python
    {
        "name": "Client",
        "description": (
            "Client-portal — authenticated gym member self-service: OTP auth, "
            "session management, profile (Phase 68 CAUTH-01..06 / CISO-01..05)."
        ),
    },
```

**Target pattern — rename to "Client-Portal" and update description to cover all v2.0 paths.** Insert between "Users" (L144–149) and "Clients" (L157–159), preserving dict structure:
```python
    {
        "name": "Client-Portal",
        "description": (
            "Client-portal — authenticated gym member self-service: phone-OTP auth, "
            "session management, profile, membership/PT-package read, bookings, QR "
            "check-in, checkout, and payment status "
            "(Phases 68–71 CAUTH-01..06 / CHOME-01..03 / CHIST-01..03 / "
            "CPLAN-01..03 / CBOOK-02..05 / CCHK-01..03 / CPAY-01..05)."
        ),
    },
```

**Decision anchor (D-72-01):** Default is the unified single `"Client-Portal"` tag. The two-tag fallback (keep `"Client"`, add `"Client-Portal"` alongside) is only used if re-tagging causes a drift-gate failure against `contract-freeze-v1.11.0` (staff paths only — client re-tagging does not touch staff paths so drift-gate failure is not expected).

**`openapi_tags` wiring** (line 447 — no change needed, already passes `OPENAPI_TAGS`):
```python
        openapi_tags=OPENAPI_TAGS,
```

---

### `apps/backend/app/modules/client_auth/router.py` — tag change (D-72-01)

**Analog:** `apps/backend/app/modules/client_portal/router.py` line 126

**Current tag** (line 51 of `client_auth/router.py`):
```python
router = APIRouter(tags=["Client"])
```

**Target pattern — copy tag from `client_portal/router.py` line 126:**
```python
router = APIRouter(tags=["Client-Portal"])
```

**No other changes.** All `operation_id` values already carry the `client_` prefix (`client_otp_request`, `client_otp_verify`, `client_session_refresh`, `client_session_logout`, `client_get_me`, `client_patch_me`) — these are unchanged.

---

### `packages/api-client/src/schema.contract.test.ts` — add `_v20Checks` block (D-72-02)

**Analog:** existing `_v19Checks` block at lines 424–440 (most recent milestone pattern). The `_v18Checks` block at lines 378–387 shows the 8-item form; `_v14Checks` at lines 167–241 shows the long-tuple form. All follow the same three-part structure: (1) type aliases, (2) tuple const, (3) `it(...)` + `expect(...).toHaveLength(N)`.

**Type-alias section to add** (after line 440, before the `describe` block at line 442):
```typescript
// --- v2.0 surface — Client-Portal (Phases 68–71) --------------------------
// auth/profile (Phase 68 CAUTH-*): otp/request, otp/verify, session/refresh,
//   session/logout, GET /me, PATCH /me
// read (Phase 69 CHOME/CHIST/CPLAN): membership, home, bookings-list,
//   visit-history, pt-session-history, payment-history, plans, pt-packages, trainers
// write (Phase 70 CBOOK/CCHK): booking POST, booking cancel, slots GET,
//   qr-token GET, check-in POST
// checkout (Phase 71 CPAY): checkout/memberships, checkout/pt-packages, payment status
//
// All paths are LANDED (Phase 71 complete); hard AssertNonNever guards — no HasPath<>.
type _ClientOtpRequest = AssertNonNever<paths['/api/v1/client/otp/request']['post']>
type _ClientOtpVerify = AssertNonNever<paths['/api/v1/client/otp/verify']['post']>
type _ClientSessionRefresh = AssertNonNever<paths['/api/v1/client/session/refresh']['post']>
type _ClientSessionLogout = AssertNonNever<paths['/api/v1/client/session/logout']['post']>
type _ClientGetMe = AssertNonNever<paths['/api/v1/client/me']['get']>
type _ClientPatchMe = AssertNonNever<paths['/api/v1/client/me']['patch']>
type _ClientGetMembership = AssertNonNever<paths['/api/v1/client/membership']['get']>
type _ClientGetHome = AssertNonNever<paths['/api/v1/client/home']['get']>
type _ClientListBookings = AssertNonNever<paths['/api/v1/client/bookings']['get']>
type _ClientListVisitHistory = AssertNonNever<paths['/api/v1/client/history/visits']['get']>
type _ClientListPtSessionHistory = AssertNonNever<paths['/api/v1/client/history/pt-sessions']['get']>
type _ClientListPaymentHistory = AssertNonNever<paths['/api/v1/client/history/payments']['get']>
type _ClientListPlans = AssertNonNever<paths['/api/v1/client/plans']['get']>
type _ClientListPtPackages = AssertNonNever<paths['/api/v1/client/pt-packages']['get']>
type _ClientListTrainers = AssertNonNever<paths['/api/v1/client/trainers']['get']>
type _ClientCreateBooking = AssertNonNever<paths['/api/v1/client/booking']['post']>
type _ClientCancelBooking = AssertNonNever<paths['/api/v1/client/booking/{booking_id}/cancel']['post']>
type _ClientListSlots = AssertNonNever<paths['/api/v1/client/slots']['get']>
type _ClientGetQrToken = AssertNonNever<paths['/api/v1/client/qr-token']['get']>
type _ClientCheckIn = AssertNonNever<paths['/api/v1/client/check-in']['post']>
type _ClientCheckoutMembership = AssertNonNever<paths['/api/v1/client/checkout/memberships/{plan_id}']['post']>
type _ClientCheckoutPtPackage = AssertNonNever<paths['/api/v1/client/checkout/pt-packages/{plan_id}']['post']>
type _ClientGetPaymentStatus = AssertNonNever<paths['/api/v1/client/payments/{payment_id}/status']['get']>

// Static checks for v2.0 Client-Portal surface — each must resolve to true.
const _v20Checks: [
  _ClientOtpRequest,
  _ClientOtpVerify,
  _ClientSessionRefresh,
  _ClientSessionLogout,
  _ClientGetMe,
  _ClientPatchMe,
  _ClientGetMembership,
  _ClientGetHome,
  _ClientListBookings,
  _ClientListVisitHistory,
  _ClientListPtSessionHistory,
  _ClientListPaymentHistory,
  _ClientListPlans,
  _ClientListPtPackages,
  _ClientListTrainers,
  _ClientCreateBooking,
  _ClientCancelBooking,
  _ClientListSlots,
  _ClientGetQrToken,
  _ClientCheckIn,
  _ClientCheckoutMembership,
  _ClientCheckoutPtPackage,
  _ClientGetPaymentStatus,
] = [
  true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true,
]
```

**`it(...)` block to add** inside the `describe('schema.contract', ...)` block, mirroring line 478–479:
```typescript
  it('compiles against the regenerated v2.0 Client-Portal surface (Phases 68-71)', () => {
    expect(_v20Checks).toHaveLength(23)
  })
```

**Exact path spellings must be verified against the regenerated `schema.d.ts` after regen** — the paths listed above follow the `/api/v1/client/...` prefix pattern from `client_portal/router.py` (prefix set in `main.py` router include) and `client_auth/router.py`. The planner's implementation step must confirm path keys in the live `schema.d.ts` before finalizing the type aliases.

---

### `packages/api-client/src/schema.d.ts` — byte-stable regen

**Analog:** itself (previous regen cycle). No hand-editing.

**Regen command** (from `ci.yml` line 106 — run locally before commit):
```bash
pnpm --filter @clubcore/api-client codegen
```

**Drift gate pattern** (from `ci.yml` lines 114–117 — the exact WR-06 pattern to keep green):
```yaml
- name: Drift gate — packages/api-client/src/schema.d.ts
  run: |
    git ls-files --error-unmatch packages/api-client/src/schema.d.ts
    git diff --exit-code packages/api-client/src/schema.d.ts
```

The regen must be run after `apps/backend/openapi.json` has been updated (tag change + export) so the client schema reflects the unified `"Client-Portal"` tag.

---

### `.github/workflows/ci.yml` — add `client-pwa` job + scope `frontend` job (D-72-03/04/05)

**Analog:** existing `redocly-lint` job (lines 127–143) — same structure as a parallel independent job with `no needs:` and a minimal Node setup.

**New `client-pwa` job to add** — copy the `redocly-lint` pnpm/Node setup pattern from the `frontend` job (lines 79–101) but scoped to `@clubcore/client-pwa`:
```yaml
  client-pwa:
    name: Client PWA (typecheck + lint + test + build)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up pnpm
        uses: pnpm/action-setup@v3
        with:
          version: 9

      - name: Set up Node 20
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"

      - name: pnpm install
        run: pnpm install --frozen-lockfile

      - name: Typecheck
        run: pnpm -F @clubcore/client-pwa typecheck

      - name: Lint
        run: pnpm -F @clubcore/client-pwa lint

      - name: Test
        run: pnpm -F @clubcore/client-pwa test

      - name: Build
        run: pnpm -F @clubcore/client-pwa build
```

**`frontend` job scoping change (D-72-05)** — the three `-r` (recursive) steps at lines 93–100 must exclude `@clubcore/client-pwa` to prevent double-run. The `--filter '!@clubcore/client-pwa'` flag is the pnpm-native exclusion syntax:
```yaml
      - name: Lint (workspaces)
        run: pnpm -r --filter '!@clubcore/client-pwa' lint

      - name: Typecheck (workspaces)
        run: pnpm -r --filter '!@clubcore/client-pwa' typecheck

      - name: Test (workspaces)
        run: pnpm -r --filter '!@clubcore/client-pwa' test
```

**Note:** The `pnpm -F @clubcore/api-client test` (line 103), `codegen` (line 106), and the `schema.d.ts` drift gate (lines 114–117) in the `frontend` job are **not changed** — they target a specific package, not recursive, so no double-run risk.

**`concurrency` and `permissions` blocks** (lines 8–17) are unchanged — already apply to all jobs.

---

### `apps/client-pwa/package.json` — verify scripts (D-72-04)

**Status: already correct.** The four CI gate commands are already present at lines 11–17:
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "lint": "eslint .",
  "test": "vitest run",
  "typecheck": "tsc -b --noEmit"
}
```

No changes needed. The planner should confirm this in the implementation step.

---

### `.planning/handoff/clubcore-v2.0-runbook.md` — new runbook (D-72-09)

**Analog:** `.planning/handoff/clubcore-auth-runbook.md` (lines 1–199+)

**Format pattern to copy:**
- Frontmatter block: `# clubcore [scope] Runbook (v[N])` title, `> Аудитория` + `**Backend version**` + `**Source-of-truth contract**` block.
- Section structure: numbered `##` sections, each with: prose description → curl example block → optional Postman callout.
- Bilingual: prose in Russian, curl labels/variable names in English.
- curl examples use `-c cookies.txt / -b cookies.txt` for cookie jar, `-H "X-CSRF-Token: $CSRF"` for mutating requests, awk line to extract CSRF from cookie jar.
- Operator-pending items are clearly labelled `N/A-until-production` or `OPERATOR-PENDING` with documented trigger condition (precedent from `v1.11-OPERATOR-EVIDENCE.md` lines 47–53).

**Sections the v2.0 runbook must cover** (per D-72-09):
1. Dev-stack setup (`docker compose up`, `seed_demo_data`, `seed_dev_client`, env vars `ENVIRONMENT=dev DEV_OTP_PIN_ENABLED=true`)
2. Phone-OTP login (`POST /api/v1/client/otp/request` → `POST /api/v1/client/otp/verify`) — dev credentials: phone `+79999999999`, code `111111`
3. Read-path walkthrough (live gate): home → membership → slots → book slot → QR check-in → history
4. ЮKassa checkout leg (OPERATOR-PENDING): test card `5555 5555 5555 4477`, manual webhook `POST /api/v1/_internal/yookassa/webhook` with real payment id, `YOOKASSA_SANDBOX=true`
5. Client session management: refresh, logout
6. CSRF discipline for client endpoints (same `X-CSRF-Token` pattern but cookie name `clubcore_client_csrf` and client cookie names `cc_client_access` / `cc_client_refresh`)

**File location:** `.planning/handoff/clubcore-v2.0-runbook.md`

---

### `.planning/milestones/v2.0-OPERATOR-EVIDENCE.md` — new evidence scaffold (D-72-06)

**Analog:** `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` (lines 1–60+)

**Format pattern to copy** (YAML front-matter + append-only convention):
```markdown
---
milestone: v2.0
milestone_name: Client PWA
created: 2026-05-31
convention: append-only — RUN-* walkthrough captures append to this file
items:
  - RUN-00-read-path-live
  - RUN-01-yookassa-checkout
decisions_honored:
  - D-72-06
  - D-72-07
  - D-72-09
---
```

**Index pattern** (from `v1.11-OPERATOR-EVIDENCE.md` lines 46–53):
```markdown
## Index

- [RUN-00-read-path-live] — status: COMPLETE <date> (see section below)
- [RUN-01-yookassa-checkout] — status: OPERATOR-PENDING (ЮKassa sandbox creds + hosted-page manual webhook; see section below)
```

**D-67-03 no-fabrication rule applies:** real terminal transcripts only; absent capability → explicit `OPERATOR-PENDING` row with trigger condition.

---

## Shared Patterns

### OpenAPI tag scheme discipline
**Source:** `apps/backend/app/main.py` lines 130–138 (comment block above `OPENAPI_TAGS`)
**Apply to:** D-72-01 tag rename + `OPENAPI_TAGS` edit
```python
# D-64-TAG-INTERNAL: internal webhook handlers (email, yookassa) are
# listed LAST so the business-domain navigation in Redocly remains clean.
```
The new `Client-Portal` tag entry must be placed in the business-domain section (between `Users` and `Clients`), not at the end.

### Drift gate (WR-06) double-check pattern
**Source:** `apps/backend/ci.yml` lines 60–64
**Apply to:** both drift gates (openapi.json and schema.d.ts)
```yaml
- name: Drift gate — apps/backend/openapi.json
  working-directory: ${{ github.workspace }}
  run: |
    git ls-files --error-unmatch apps/backend/openapi.json
    git diff --exit-code apps/backend/openapi.json
```
`git ls-files --error-unmatch` MUST precede `git diff --exit-code` — silently passing when a file is gitignored is the WR-06 failure mode this guards against.

### `AssertNonNever` + tuple + `toHaveLength` triple
**Source:** `packages/api-client/src/schema.contract.test.ts` lines 14–15 + pattern from `_v18Checks` (L377–387 + L473–475):
```typescript
type AssertNonNever<T> = [T] extends [never] ? false : true
// ...type aliases...
const _vNNChecks: [Type1, Type2, ...] = [true, true, ...]
// in describe block:
it('compiles against the regenerated vN.N surface (...)', () => {
  expect(_vNNChecks).toHaveLength(N)
})
```
The `toHaveLength(N)` is both a runtime sanity check and the exact count documentation for the milestone's operation count.

### Parallel CI job structure (no `needs:`)
**Source:** `.github/workflows/ci.yml` lines 127–143 (`redocly-lint` job)
**Apply to:** new `client-pwa` job
No `needs:` key — runs in parallel with `backend`, `frontend`, `redocly-lint`. Isolates client-pwa failures from the shared frontend gate.

### `os.environ.setdefault` env-prep before `app.main` import
**Source:** `apps/backend/scripts/export_openapi.py` lines 31–51
**Apply to:** any new seed/export script invoked in the v2.0 runbook
```python
os.environ.setdefault("ENVIRONMENT", "dev")
# ... other required settings ...
from app.main import create_app
```
This ordering is mandatory — env-prep must precede any `app.*` import.

---

## Operation Enumeration for `_v20Checks`

The following 23 operations are sourced from the live routers (verified against the code read above):

**From `client_auth/router.py`** (6 operations, currently tag `"Client"` → re-tagged `"Client-Portal"`):
1. `POST /api/v1/client/otp/request` — `client_otp_request`
2. `POST /api/v1/client/otp/verify` — `client_otp_verify`
3. `POST /api/v1/client/session/refresh` — `client_session_refresh`
4. `POST /api/v1/client/session/logout` — `client_session_logout`
5. `GET /api/v1/client/me` — `client_get_me`
6. `PATCH /api/v1/client/me` — `client_patch_me`

**From `client_portal/router.py`** (17 operations, already tag `"Client-Portal"`):
7. `GET /api/v1/client/membership` — `client_get_membership`
8. `GET /api/v1/client/home` — `client_get_home`
9. `GET /api/v1/client/bookings` — `client_list_bookings`
10. `GET /api/v1/client/history/visits` — `client_list_visit_history`
11. `GET /api/v1/client/history/pt-sessions` — `client_list_pt_session_history`
12. `GET /api/v1/client/history/payments` — `client_list_payment_history`
13. `GET /api/v1/client/plans` — `client_list_plans`
14. `GET /api/v1/client/pt-packages` — `client_list_pt_packages`
15. `GET /api/v1/client/trainers` — `client_list_trainers`
16. `POST /api/v1/client/booking` — `client_create_booking`
17. `POST /api/v1/client/booking/{booking_id}/cancel` — `client_cancel_booking`
18. `GET /api/v1/client/slots` — `client_list_slots`
19. `GET /api/v1/client/qr-token` — `client_get_qr_token`
20. `POST /api/v1/client/check-in` — `client_check_in`
21. `POST /api/v1/client/checkout/memberships/{plan_id}` — `client_checkout_membership`
22. `POST /api/v1/client/checkout/pt-packages/{plan_id}` — `client_checkout_pt_package`
23. `GET /api/v1/client/payments/{payment_id}/status` — `client_get_payment_status`

**Note:** The exact path prefix (`/api/v1/client/`) must be confirmed against the `apps/backend/app/main.py` router include for `client_auth` and `client_portal` modules before finalizing the `schema.contract.test.ts` type aliases. If the prefix differs, all path strings in `_v20Checks` must be adjusted accordingly.

---

## No Analog Found

None. All 8 files have close analogs in the live codebase.

---

## Metadata

**Analog search scope:** `apps/backend/app/main.py`, `apps/backend/app/modules/client_auth/router.py`, `apps/backend/app/modules/client_portal/router.py`, `apps/backend/scripts/export_openapi.py`, `apps/backend/scripts/seed_dev_client.py`, `apps/backend/scripts/seed_demo_data.py`, `packages/api-client/src/schema.contract.test.ts`, `.github/workflows/ci.yml`, `apps/client-pwa/package.json`, `.planning/handoff/clubcore-auth-runbook.md`, `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md`
**Files scanned:** 11 live files read directly
**Pattern extraction date:** 2026-05-31
