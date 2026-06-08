# Phase 96: Referral Domain Backend - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend referral domain: every client can mint a stable, idempotent personal
referral code + shareable deep-link; a friend can bind a referrer at onboarding
(idempotent, self-referral blocked); the owner configures bonus amounts via an
owner-only API. **Binding only** — actual reward crediting on first purchase is
Phase 97. No PWA UI in this phase (Phase 98). No staff/admin-web surface
(frozen).

Endpoints delivered:
- `GET /api/v1/client/referral/code` — mint/return stable code + share URL (require_client)
- `POST /api/v1/client/referral/capture` — bind referrer↔referee (require_client)
- `GET /api/v1/i/<code>` — public deep-link resolver
- `GET/PUT /api/v1/referral/config` — owner-only bonus amount config

</domain>

<decisions>
## Implementation Decisions

### Data Model & Code Generation
- **Code format:** 8-char uppercase Crockford base32 (excludes ambiguous 0/O/1/I/L) generated via `secrets`. ~40-bit entropy, human-shareable.
- **Storage model:** New `referrals` module with two tables:
  - `referral_codes` — one immutable row per client (`code` UNIQUE, `referrer_client_id` FK→clients RESTRICT). Code is permanent/бессрочный per REFER-01.
  - `referral_captures` — referrer↔referee binding (`referee_client_id` UNIQUE FK→clients, `referrer_client_id` FK→clients, `referral_code_id` FK). One referrer per referee enforced at schema level (partial/plain UNIQUE on referee_client_id).
- **Collision handling:** bounded retry loop — re-roll the code on UNIQUE violation (~3 attempts), same defensive pattern as promo_codes.
- **Module placement:** dedicated `app/modules/referrals/` (models/router/service/schemas/repository) — mirrors `loyalty` separation to avoid cross-module edges (D-20-MODULE). Router mounted under client prefix + a public router for `/i/<code>` + an owner router for `/referral/config` (gym dual/triple-router precedent).

### Endpoint Contracts & Responses
- **`GET /i/<code>` auth:** PUBLIC (unauthenticated) — the friend is not yet registered; it is the deep-link landing resolver. Mounted without `require_client()`.
- **`/i/<code>` response:** privacy-safe minimal payload — `{ valid: bool, referrerFirstName: str | null, welcomeBonusKopecks: int }`. NO PII, NO client_id, NO last name. Unknown/invalid code → `valid: false` (200, not 404) so the PWA can render a graceful "code not found" state. (Resolver returns 200 always; `capture` is where unknown code → 404.)
- **`GET /client/referral/code` response:** `{ code, shareUrl }` where `shareUrl = <PWA_BASE_URL>/i/<code>`. Base URL comes from server config (server-authoritative; PWA does not build the URL). Idempotent — second call returns the same code.
- **`POST /client/referral/capture` request body:** `{ code: string }` only. Referee identity comes from `require_client()` principal — NEVER from the body (D-20-IDOR / locked constraint).

### Owner Config & Error Semantics
- **Config storage:** singleton `referral_config` row (`referrer_bonus_kopecks`, `referee_welcome_kopecks`) — seed-initialized via migration, mirrors `gym` singleton pattern. Server is the single source of amounts (REFER-07).
- **Seed defaults:** referrer bonus 500 ₽ = `50000` kopecks; friend welcome 300 ₽ = `30000` kopecks. Owner-editable.
- **Owner auth:** `/referral/config` GET+PUT gated by `require_permission(Action, Resource)` with PUT also requiring `verify_csrf` (require_permission declared BEFORE verify_csrf so reception fails 403 first — RBAC-04 ordering). Reception → 403. Exact `gym` owner-router pattern.
- **Error semantics:**
  - Self-referral (resolved referrer == principal) → **422**.
  - `capture` with unknown code → **404**.
  - Second `capture` for the same referee → **no-op 200** (idempotent).
  - Referee already has a referrer → **no-op 200** (idempotent, first binding wins).

### Capture Timing & Validation
- Capture allowed **any time before the referee's first subscription purchase**. Phase 96 stores the binding; payout is gated in Phase 97 on `payment.succeeded`.
- If the referee already purchased before capturing: the binding is still **stored** (no Phase-96 error). Phase 97's first-purchase + one-bonus-per-referee gate naturally prevents a payout. Phase 96 stays purely about binding.
- Self-referral detection: compare the resolved `referrer_client_id` to the `require_client()` principal id → 422 if equal.

### Claude's Discretion
- Exact column names, index names (follow NAMING_CONVENTION + literal-name-in-migration discipline already used by loyalty/promo_codes), migration numbering (next after 0066), and schema field casing.
- Internal service decomposition and repository method signatures.
- Crockford base32 alphabet constant location.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/loyalty/` — append-only ledger module; `service.py` exposes caller-owns-txn flush-only primitives (`accrue_welcome_bonus`, `owner_grant_loyalty`) reused in Phase 97. Mount pattern (dedicated `loyalty_router` under `/api/v1/client`) is the template for the referral client router.
- `app/modules/gym/router.py` — dual-router (client_router + owner_router) pattern with `require_permission(Action, Resource)` + `verify_csrf` and RBAC-04 ordering. Template for `/referral/config`.
- `app/modules/promo_codes/` — code-bearing model with partial-UNIQUE-in-migration discipline (`uq_promo_codes_code_alive`); collision/retry reference for code generation.
- `app/core/dependencies.py:1240` — `require_client()` IDOR-safe client gate; `require_permission`, `verify_csrf`, `ClientPrincipal`, `CurrentUser`.
- `app/core/audit.py` — `LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]]` (line 275) is the runtime source of truth; new events MUST be registered here before first callsite (INFRA-15). `loyalty_accrued` (line 462) is the structural precedent.
- `app/core/schemas.py` — `ResponseEnvelope`, `envelope()`; `app/core/pagination.py` — `PageQuery`, `PaginatedData`.
- `app/core/database.py` — `Base`, `UUIDPkMixin`, `get_db`.

### Established Patterns
- Single-temporal-column discipline (`created_at` server_default, no TimestampMixin) for append-only/event rows — mirror loyalty_ledger.
- FK `ondelete="RESTRICT"` with explicit `name="fk_..._clients"`.
- CheckConstraint `name=` takes a BARE suffix; partial UNIQUE indexes declared in migration with literal names (not as ORM Index).
- No try/except in routers — AppError subclasses bubble to `_app_error_handler` in `app/main.py`.
- Response envelope wrapping via `envelope(result)`; camelCase response fields.
- Migrations live in `apps/backend/alembic/versions/`; latest is `0066_message_attachments.py` — referral migrations start at 0067.

### Integration Points
- New routers mounted in `app/api/v1/router.py` (mirror loyalty_router separation at v1/router.py:101-103) — one client-prefixed router, one public router for `/i/<code>`, one owner router for `/referral/config`.
- Audit events `referral_code_generated` and `referral_captured` registered in `LOCKED_AUDIT_EVENTS` (app/core/audit.py) and any payload typing in `app/core/audit_payloads.py` before callsite.
- `PWA_BASE_URL` (or equivalent) read from app settings/config for `shareUrl` construction.

</code_context>

<specifics>
## Specific Ideas

- Crockford base32 alphabet (no 0/O/1/I/L) for human-shareable, low-misread codes.
- `/i/<code>` returns 200 with `valid: false` for unknown codes (graceful PWA landing), distinct from `capture`'s 404 on unknown code.
- Seed defaults: 500 ₽ referrer / 300 ₽ friend welcome.

</specifics>

<deferred>
## Deferred Ideas

- Gamification tiers ("5 friends → free month"), count-up "Уже накоплено" visuals — backend deferred (Future Requirements).
- Owner referral analytics (conversion, top referrers) — after admin-web unfreeze.
- Nudge/reminder for friends who clicked but didn't pay ("Ждём" status).
- Same-device / same-phone anti-abuse heuristics beyond self-referral id check.
- `referral_config_updated` audit event — not required this phase (only code_generated + captured are mandated by success criteria).

</deferred>
