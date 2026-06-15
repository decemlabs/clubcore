# Requirements: clubcore — v3.2 Admin — Wire the Rest

**Defined:** 2026-06-15
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

> **Scope basis:** prioritized by backend-readiness (probed 2026-06-15). Most items are FE-wiring over an already-shipped backend (promo_codes v2.0, messaging v2.5, reports/visits, csv_export). Expensive full-stack (multi-branch, notifications-hub, persisted-RBAC) is explicitly deferred. Phase numbering continues from **112**.

## v1 Requirements

### Refunds (P0 — operational money gap)

- [x] **REF-01**: Owner can refund an arbitrary recorded payment (cash / non-membership / non-PT) from Cashbox or Finance, with a reason; the refund is recorded and the ledger/cashbox reflects it (removes the READ-ONLY `T-103-03-FAKEREFUND` stub).

### Team Management (P0 — access gap)

- [x] **TEAM-01**: Owner can change the role (owner ↔ reception) of an existing staff user from the Team/Settings screen, with the change persisted and audited; reception cannot.

### Promo Codes (P1 — backend ready)

- [x] **PROMO-01**: Owner can create, edit, and deactivate/archive promo codes (percentage or fixed, with limits) via the Plans page, persisted to the existing `promo_codes` backend.
- [x] **PROMO-02**: The Plans «Скидки и акции» section lists real promo codes from the backend (replacing the mock cards).

### Attendance & Load Analytics (P1 — on existing reports)

- [x] **ANL-01**: Owner sees real attendance analytics widgets driven by the existing `reports/visits` aggregate — hourly heatmap, hour-curve, day-of-week, peak, frequency, and duration.
- [x] **ANL-02**: Owner sees cohort / anomaly / risk-list attendance widgets backed by new aggregate report queries.
- [x] **ANL-03**: Owner sees current live load ("сейчас в зале") on the Load page, backed by a new `reports/load/now` endpoint.
- [x] **ANL-04**: Dashboard activity feed, top-trainer KPIs, and the Plans sales chart render real data from existing read endpoints (audit log / visits / payments).

### Data Export (P2 — backend csv_export ready)

- [x] **EXP-01**: Owner can export payments to CSV (RFC-4180 + BOM) over a date range.
- [x] **EXP-02**: Owner can export attendance/visits to CSV over a date range.

### Staff Messaging (P2 — messaging module ready)

- [x] **MSG-01**: Staff sees a chat inbox of client↔gym threads (list + unread), backed by new staff-side REST over the existing messaging module.
- [x] **MSG-02**: Staff can open a thread and send/reply to a client message; messages persist and the client PWA receives them.

### Handoff (closes the milestone)

- [x] **HND-01**: OpenAPI (`openapi.json` + `schema.d.ts`) regenerated additively for the new v3.2 routes (refund, role-change, promo CRUD, analytics, exports, staff-messages) with a `_v32Checks` forward-guard; full milestone gate green; **≥1 contract test per new domain parses a REAL backend response** (closes the v3.0/v3.1 mock↔real drift lesson).

## v2 Requirements (deferred — future milestones)

### Communications / Notifications
- **NOTIF-HUB-01**: Notification center, templates, broadcast campaigns, delivery reports (new domain — XL).
- **SEARCH-01**: Global cross-entity search / command palette (new `/search` endpoint).
- **MSG-03**: Client-card notes tab (small `client_notes` model).

### Self-serve admin
- **IMP-01**: Import wizard (clients/payments/attendance) — multipart, mapping, transactional upsert (L).
- **TRASH-01**: Trash — list/restore/purge soft-deleted entities (L).
- **SEC-01**: Settings security — 2FA enable, API keys, webhooks, payment-provider config UI (L).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Plans create/edit forms (membership + PT) | **Already shipped in v3.1 / Phase 107** (PlanFormModal); verified in browser UAT — not re-scoped. |
| Multi-branch (Branches CRUD, per-branch settings) | XL breaking schema change (branch_id FK across 7+ tables); contradicts the single-club Core Value. → separate **v4 Multi-Club** milestone, only if a 2nd gym appears. |
| Persisted RBAC / roles editor | XL; breaks the CISO-01 byte-parity frozen-contract invariant. Two hardcoded roles (owner/reception) suffice; TEAM-01 covers the real need. |
| Notifications Hub / broadcasts | XL new domain; Telegram bot + existing dispatcher cover current needs. |
| Production deploy / hardening (k8s, live ЮKassa leg, RU email/SMS deliverability, secrets, monitoring) | Separate ops milestone; out of "admin completeness". |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REF-01 | 112 | Complete |
| TEAM-01 | 112 | Complete |
| PROMO-01 | 113 | Complete |
| PROMO-02 | 113 | Complete |
| ANL-01 | 114 | Complete |
| ANL-02 | 115 | Complete |
| ANL-03 | 115 | Complete |
| ANL-04 | 115 | Complete |
| EXP-01 | 116 | Complete |
| EXP-02 | 116 | Complete |
| MSG-01 | 116 | Complete |
| MSG-02 | 116 | Complete |
| HND-01 | 117 | Complete |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-15*
*Last updated: 2026-06-15 after v3.2 milestone definition*
