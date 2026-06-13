# Requirements: clubcore — v3.0 Production Admin — Backend Wiring

**Defined:** 2026-06-13
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone goal:** Превратить `apps/admin-app` из mock-прототипа в боевую staff-админку на реальном backend (одно-клубный срез по уже существующим доменам) и удалить `apps/admin-web`, перенеся его роль RBAC-reference.

**Locked decisions** (see PROJECT.md `## Key Decisions`): D-V30-BRANCH (single-club; multi-branch hide-for-future), D-V30-SCOPE-WIRE (wire-only; no new backend domains), D-V30-ADMINWEB-DELETE (delete admin-web; RBAC-reference re-home mechanics at Phase 100 plan), D-V30-VERSION (major bump; original v3.0 production-launch → v3.1+).

> **Scope principle:** every requirement below wires an admin-app screen to an *already-shipped* backend endpoint, or handles the integration/retirement plumbing. No new business domains, no multi-branch. Screens whose backend does not yet exist are **hidden-for-future** (FND-04), not built.

---

## v3.0 Requirements

### FND — Foundation & Integration

- [x] **FND-01**: `apps/admin-app` is part of the clubcore repo and builds/runs/tests there; the package-manager/workspace decision (Bun → pnpm vs standalone) is made at the Phase 100 plan; a dedicated CI job runs its `check` + `test` + `build`.
- [x] **FND-02**: admin-app talks to the real backend — the API client targets `VITE_API_BASE_URL`, sends the staff session cookie (`sz_*`) and an `X-CSRF-Token` on every mutating request, and routes a `401` back to login.
- [x] **FND-03**: each wired domain validates backend responses through a lazily-adopted per-domain zod contract layer (spike 010 Option A); the screen's mock `queryFn` is removed once the domain is live.
- [x] **FND-04**: deferred screens (Branches, Branch-Settings, System-Settings, ImportExport, Duplicates, clients/trainers Archive, Trash, Messages, Roles-management, Notifications-management) are hidden / gated as "coming soon" — not wired, not broken, not deleted (hide-for-future, PWA D-71-09 pattern).

### AUTH — Staff Authentication & RBAC

- [x] **AUTH-01**: a staff member logs in via the real `/api/v1/auth` (email/password); the session persists across a browser refresh and the CSRF token is captured for mutations.
- [x] **AUTH-02**: unauthenticated navigation redirects to `/login`; logout ends the session; Settings lists active sessions (`/auth/sessions`) and can revoke them.
- [x] **AUTH-03**: the UI reflects the staff role (owner vs reception) — owner-only screens/actions are hidden or disabled for reception, and a backend `403` surfaces as a friendly state, never a crash.

### CLI — Clients

- [x] **CLI-01**: the Clients list renders real `GET /api/v1/clients` with server-side search + the pagination envelope `{items,total,page,pageSize}`, including loading / error / empty states.
- [x] **CLI-02**: the Client detail screen renders real `GET /api/v1/clients/{id}` plus that client's memberships / visits / payments.
- [x] **CLI-03**: create + edit client persist via `POST` / `PATCH /api/v1/clients` (Zod-validated form, money in kopecks); soft-delete via `DELETE`.

### MEM — Memberships & Plans

- [x] **MEM-01**: the Plans/Абонементы screen lists real membership plans (`/membership-plans`) and PT-package plans (`/pt-package-plans`); create/edit are owner-only gated.
- [x] **MEM-02**: staff sells a membership or PT-package from the admin (cash) — `/memberships` + `/pt-packages` sell over the payment ledger with an `Idempotency-Key`.
- [x] **MEM-03**: staff manages a membership lifecycle — freeze / unfreeze / renew / cancel + refund (`/memberships/{id}/…`) with the freeze-days and renewal rules surfaced.

### SCH — Schedule & Bookings

- [x] **SCH-01**: the Schedule screen renders real trainer slots (`/trainer-slots`), recurring templates (`/recurring-templates`) and time-off (`/time-off`); create/edit are owner-only.
- [x] **SCH-02**: staff books / cancels / completes a PT booking against a slot (`/bookings`, `/pt-sessions`); race-safe conflicts surface as a clear state.

### TRN — Trainers & Payroll

- [x] **TRN-01**: the Trainers list + Trainer detail render real `/trainers` (catalog + bio/specialization).
- [x] **TRN-02**: trainer payroll — comp-config + accrual preview/run + pending→paid (`/payroll`) — is wired on the trainer detail / finance surface (owner-only).

### ATT — Attendance & Load

- [x] **ATT-01**: the Attendance screen renders real visits (`/visits` list) and supports reception check-in (`/visits/check-in`).
- [x] **ATT-02**: the Load screen renders the real hourly/daily visits aggregate (`/reports/visits`) — no mock NaN on empty buckets.

### FIN — Cashbox & Finance

- [x] **FIN-01**: the Cashbox screen renders the real cash ledger (`/payments`) with sell + refund records and daily totals; the refund flow is wired. *(Shift open/close + Z-report — see Future.)*
- [x] **FIN-02**: the Finance screen renders real revenue (`/reports/revenue`, net-of-refund, by method/subject) and online payments (`/online-payments`) read.

### RPT — Dashboard, Reports & Audit

- [x] **RPT-01**: the Dashboard (landing `/`) renders real KPI/aggregate data from `/reports/*` (revenue/clients/visits) and charts, with empty-data guards.
- [x] **RPT-02**: the Reports screen renders the four aggregate reports (revenue / clients / visits / trainers) with CSV export (`/reports/*.csv`, UTF-8 BOM).
- [x] **RPT-03**: the Audit screen renders the real owner-only audit log (`/audit-log`) with filters + stable pagination + CSV export.

### SET — Settings & Users

- [x] **SET-01**: Settings (profile) reads/edits the current staff profile + theme, and manages active sessions.
- [x] **SET-02**: the Users surface wires owner-only multi-user admin CRUD (`/api/v1/users`: invite / list / deactivate / soft-delete).

### ADMW — admin-web Retirement & RBAC Re-home

- [x] **ADMW-01**: `apps/admin-web` is removed from the repo (workspace entry, CI job, ESLint/import-linter zones, dangling references cleaned).
- [x] **ADMW-02**: the three-way RBAC-parity reference (`permissions.py` ↔ `can.ts` ↔ `registry.ts`) + the CISO-01 byte-guard is re-homed — the mechanic (parity → admin-app vs backend-only authority) is decided at the Phase 100 plan after reading the real coupling — and the chosen guard is green.
- [x] **ADMW-03**: the OpenAPI staff drift-gate + `@clubcore/api-client` codegen pipeline still pass after admin-web removal (no consumer left dangling).

### HND — OpenAPI Handoff & Milestone Verification

- [x] **HND-01**: the staff `openapi.json` + `schema.d.ts` stay byte-stable / contract unchanged (no new backend domains); the staff drift-gate is green and the full milestone gate (mypy --strict + lint-imports + pytest + admin-app `check`/`test` + Redocly) passes.

---

## Future Requirements

Deferred — need new backend or a later milestone. Tracked, not in this roadmap.

### Multi-branch (next milestone)
- **BRANCH-01**: Branches list + Branch detail + Branch-Settings + System-Settings — require branch / multi-tenancy in the backend (D-V30-BRANCH defers this).

### Staff-side domains needing new backend
- **IMPEX-01**: ImportExport — bulk client/data import + export backend.
- **DEDUP-01**: Duplicates detection + merge backend; generic cross-entity Archive / Trash management.
- **MSGADM-01**: staff Messages inbox — staff-side REST over the v2.5 `messaging` domain (today staff replies only via the Telegram bridge).
- **ROLES-01**: Roles management — an RBAC permission-management API (RBAC is currently static owner/reception).
- **NOTIFADM-01**: Notifications-management screen — a staff notification dispatch/log API (notifications today are event-driven cron + Telegram + email, no staff list/send surface).
- **CASHOPS-01**: Cashbox shift open/close + Z-report — a cash-shift entity (the ledger `/payments` exists; shift/Z-report does not).
- **GYMINFO-01**: Gym-info editor in admin — `PUT /gym` exists (owner-only, v2.4) but is bundled with the deferred System-Settings screen; could be pulled forward cheaply.

---

## Out of Scope

Explicitly excluded for v3.0. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-tenancy / branch architecture in backend | Backend is single-gym by design; introducing `tenant_id`/RLS for 3 admin screens is disproportionate (touches every domain + RBAC + migrations). Next milestone. (D-V30-BRANCH) |
| New business domains / endpoints on backend | v3.0 is wire-only — connect built screens to built endpoints. Screens without backend → hidden-for-future (FND-04). (D-V30-SCOPE-WIRE) |
| Editing `apps/admin-web` internals | It is being **deleted**, not maintained. (D-V30-ADMINWEB-DELETE) |
| Production deploy / launch (Kubernetes / Terraform / live ЮKassa leg / RU email-SMS deliverability / secrets + monitoring / `sportzal_csrf → clubcore_csrf` rename) | Pushed to v3.1+ (the original "v3.0 Production deploy" line). (D-V30-VERSION) |
| Pixel-for-pixel literal HTML port of the design templates | admin-app philosophy = treat the reference as a design-spec; clean responsive React with semantic tokens + shadcn primitives, not a verbatim HTML/CSS copy (admin-app `CLAUDE.md`). |

---

## Traceability

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 100 | Complete |
| FND-02 | Phase 100 | Complete |
| FND-03 | Phase 100 | Complete |
| FND-04 | Phase 100 | Complete |
| AUTH-01 | Phase 100 | Complete |
| AUTH-02 | Phase 100 | Complete |
| AUTH-03 | Phase 100 | Complete |
| CLI-01 | Phase 101 | Complete |
| CLI-02 | Phase 101 | Complete |
| CLI-03 | Phase 101 | Complete |
| MEM-01 | Phase 101 | Complete |
| MEM-02 | Phase 101 | Complete |
| MEM-03 | Phase 101 | Complete |
| SCH-01 | Phase 102 | Complete |
| SCH-02 | Phase 102 | Complete |
| TRN-01 | Phase 102 | Complete |
| TRN-02 | Phase 102 | Complete |
| ATT-01 | Phase 103 | Complete |
| ATT-02 | Phase 103 | Complete |
| FIN-01 | Phase 103 | Complete |
| FIN-02 | Phase 103 | Complete |
| RPT-01 | Phase 104 | Complete |
| RPT-02 | Phase 104 | Complete |
| RPT-03 | Phase 104 | Complete |
| SET-01 | Phase 104 | Complete |
| SET-02 | Phase 104 | Complete |
| ADMW-01 | Phase 105 | Complete |
| ADMW-02 | Phase 105 | Complete |
| ADMW-03 | Phase 105 | Complete |
| HND-01 | Phase 106 | Complete |

**Coverage:**
- v3.0 requirements: 30 total
- Mapped to phases: 30 (roadmap complete)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-13*
*Last updated: 2026-06-13 — roadmap created; all 30 requirements mapped to Phases 100-106*
