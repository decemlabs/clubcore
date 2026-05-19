# Phase 43: Multi-User Admin Module — Discussion Log

**Mode:** `--auto` (autonomous resolution — all gray areas auto-selected with recommended defaults)
**Date:** 2026-05-19
**Phase:** 43-multi-user-admin-module
**Areas analyzed:** Email-verify policy, Schema migration shape, Module structure, Endpoint behaviour, `/auth/refresh` extension, Invitation email content, `UserSessionInvalidator` wiring, RBAC + audit traceability, Test surface, Plan packaging

> **Audit trail only.** Do not use as input to planning, research, or execution agents — see `43-CONTEXT.md` for the canonical decisions consumed downstream.

---

## Auto-Selected Decisions (rationale recap)

### Area: Email-verify policy (open conflict #7)
- **Q:** Trust owner-entered email vs separate click-to-verify before invitation accept?
- **Selected:** Trust + lazy verify via invitation accept (D-43-01)
- **Rationale:** Operator turnover is rare (1–3/year single-gym); invitation accept already proves email control; extra round-trip not justified.

### Area: `actor_display_name` formatting (deferred from Phase 41)
- **Q:** first-name + last-initial vs full name vs no field?
- **Selected:** No new field — `actor_email_snapshot` (Phase 41 D-41-09) is sufficient (D-43-03/04)
- **Rationale:** Pre-registered payloads in `audit_payloads.py:510-598` do not carry the field; v1.8 read API will join live `users.full_name`.

### Area: Schema migration shape
- **Q:** Single migration vs split per-column? Explicit `status` column vs derived `password_hash IS NULL`?
- **Selected:** Single migration 0030 + explicit `status` column + drop `password_hash NOT NULL` (D-43-05..08)
- **Rationale:** Mirrors v1.0–v1.5 single-feature-delta convention; explicit status is debuggable; sentinel-string for password rejected.

### Area: Module structure
- **Q:** Mirror clients/ layout vs minimal subset?
- **Selected:** Full 7-file mirror minus models.py (D-43-09)
- **Rationale:** `User` lives in `core/models.py` per Phase 41 D-41-01; everything else inherits clients/ pattern.

### Area: POST /users on existing pending_invitation user
- **Q:** Idempotent re-invite vs require explicit revoke+delete first?
- **Selected:** Idempotent re-invite (D-43-13 second bullet)
- **Rationale:** Bounce-recovery is the dominant onboarding failure path; explicit dance is operator-hostile.

### Area: `?include_invite_link=true` query param
- **Q:** Ship in Phase 43 vs defer to v1.7?
- **Selected:** Ship in Phase 43, owner-only, audit-logged with `link_copied: bool` payload field (D-43-14)
- **Rationale:** Phase 42 circuit breaker (D-42-14) acknowledges email transport CAN fail; copy-paste fallback is the only onboarding path during outage.

### Area: `/auth/refresh` extension scope
- **Q:** Extend refresh path only vs also extend `require_user` access-token path?
- **Selected:** Refresh path only — same-SELECT join on `is_active=true AND deleted_at IS NULL` (D-43-20/21)
- **Rationale:** 5-min access token TTL is acceptable; per-request user SELECT for `require_user` would tax every authenticated endpoint.

### Area: `UserSessionInvalidator` registration discipline
- **Q:** Double-wire (compose root + worker on_startup) vs single-wire?
- **Selected:** Single-wire — `app/main.py:create_app()` only (D-43-27)
- **Rationale:** No ARQ consumer; double-wiring would create idle registration the parity test would flag as inconsistent on any future worker-side consumer attempt without a parallel main.py update.

### Area: `USER_INVITATION_EMAIL` content location
- **Q:** `app/modules/users/email_templates.py` (per D-39-02) vs `integrations/email/copy.py`?
- **Selected:** `app/modules/users/email_templates.py` (D-43-22)
- **Rationale:** Per-domain template ownership invariant (D-39-02 v1.5 lineage) + REQUIREMENTS RESET-03 explicit file path.

### Area: Test discipline
- **Q:** Mock audit emit + ContextVar in tests vs real audit emit through real ContextVar?
- **Selected:** Real audit emit + real ContextVar via authenticated `httpx.AsyncClient` (D-43-34)
- **Rationale:** Phase 42 CR-01 lesson — kwargs-nested mock-only tests masked a regression that real audit_log queries caught.

### Area: Plan packaging
- **Q:** Single omnibus plan vs wave-structured multi-plan?
- **Selected:** ~14 plans across 4 waves (D-43-35)
- **Rationale:** Phase 42 16-plan precedent — wave structure enables parallel execution after migration round-trip [BLOCKING] checkpoint.

### Area: Migration ordering
- **Q:** Ship 0030 with or without [BLOCKING] alembic round-trip checkpoint?
- **Selected:** With explicit [BLOCKING] checkpoint on plan 43-01 (D-43-36)
- **Rationale:** Phase 42 4-15 / 4-16 precedent; round-trip clean is the only safe way to unblock Wave 2 code-side plans.

---

## Conflicts Resolved at This Phase

| Source | Conflict | Resolution |
|---|---|---|
| `.planning/research/SUMMARY.md` #7 | Email-verify policy for owner-added accounts (trust vs click-to-verify) | D-43-01: trust + lazy verify via invitation accept |
| Phase 41 deferred-items.md | `actor_display_name` formatting | D-43-03/04: no field — `actor_email_snapshot` suffices |
| REQUIREMENTS USERS-03 (P2) | `?include_invite_link=true` ship-or-defer | D-43-14: ship as owner-only escape hatch for transport outages |

---

## Scope Creep Captured (Deferred)

- Re-send verification email + owner-triggered re-verify ladder → v1.7
- Audit-log read API → v1.8
- Owner-managed administrative password reset for another user → out of scope v1.6 (revoke + re-invite covers it)
- `?status=invited_expired` auto-expiry sweeping → v1.7 (CHECK constraint extension)
- Activity log surfacing in operator list ("last seen") → v1.8 audit-read

---

## Claude's Discretion (planner refines)

- Russian wording of `USER_INVITATION_EMAIL` subject + html + text (owner-copy-lock — drafted at plan time, owner signs off at plan SUMMARY per D-27 lineage)
- Internal helper function naming in `service.py`
- Migration docstring wording
- Whether `deactivated_by_user_id` is indexed (recommend: no)
- Whether `UserListItemResponse.invitationExpiresAt` is `None` or omitted for active rows (recommend: `None` for stable wire shape)

---

## External Research

None performed in this `--auto` session — `.planning/research/PITFALLS.md` + `.planning/research/FEATURES.md` + Phase 41/42 CONTEXT.md + REQUIREMENTS.md provided sufficient ground truth for every gray area.
