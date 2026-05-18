# Phase 41: INFRA Bedrock + Anti-Oracle Scaffold - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `41-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 41-infra-bedrock-anti-oracle-scaffold
**Areas discussed:** User ORM ownership, Reset-token storage scaffolding, actor_email_snapshot capture mechanism, LOCKED_EMAIL_TEMPLATES initial content

---

## User ORM ownership (open conflict #5)

| Option | Description | Selected |
|--------|-------------|----------|
| Path A — hoist to app/core/models.py | Mechanical sed pass; both auth and users co-own User reads/writes; no Protocol indirection. Touches every test import. | |
| Path B — UserLookup Protocol slot | Lower-risk, mirrors existing 5-slot pattern. But users module needs direct ORM write access anyway, so Protocol illusion only covers reads. | |
| Path A with auth re-export shim | Hoist to core/models.py + keep `from app.core.models import User` re-exported in app/modules/auth/models.py for one milestone. Remove shim in v1.7. Limits test churn to deprecation warnings. | ✓ |

**User's choice:** Path A with auth keeping a re-export shim
**Notes:** Staged migration over the one-commit mechanical sed pass. Indicates preference for low-blast-radius refactors on shared foundations.

### Follow-up — file location

| Option | Description | Selected |
|--------|-------------|----------|
| New app/core/models.py (User only) | One model per file at core level; audit_models.py stays audit-specific. | ✓ |
| Append to app/core/audit_models.py | Co-locates with audit_log FK target; conflates two unrelated concerns. | |
| app/core/identity_models.py | Pre-names a category for future identity-domain hoists. YAGNI. | |

**User's choice:** New `app/core/models.py` (User only)
**Notes:** Clean separation; future hoists decided case-by-case.

---

## Reset-token storage scaffolding (open conflict #2)

| Option | Description | Selected |
|--------|-------------|----------|
| Decide now — DB table, Alembic 0025 in Phase 41 | Mirrors refresh_tokens discipline; SVC001 atomic-consume RETURNING SQL works as-is; audit_correlation_id natively attaches; doesn't conflict with invitation tokens. Phase 44 ships zero migrations. | ✓ |
| Defer to Phase 44 — itsdangerous stateless | Phase 41 ships no token migration. Couples reset-token revocation to password_changed_at globally — collides with USERS-03 invitation flow. | |
| Defer to Phase 44 discuss — leave open | Phase 41 carries only INFRA-38/39 + NOTIFY-06. Phase 44 picks DB vs stateless. Cost: schema lands one phase late. | |

**User's choice:** Decide now — DB table, lands as Alembic 0025 in Phase 41
**Notes:** Bedrock-up-front principle preserved. SVC001 + atomic-consume RETURNING aligns with existing project invariants.

### Follow-up — token table shape

| Option | Description | Selected |
|--------|-------------|----------|
| One unified `password_reset_tokens` table with `purpose` column | Single table; partial-UNIQUE `(user_id, purpose) WHERE consumed_at IS NULL`; TTL per purpose at SELECT layer; one cleanup cron; RESET-04 INSERT-only invariant lives in users.service. | ✓ |
| Two tables — password_reset_tokens + user_invitations | Distinct invariants per row shape; two cleanup crons; RESET-04 obvious from row shape. Doubles migration bundle surface. | |
| One table named `auth_tokens` (forward-rename) | Same shape as option 1 but speculative naming. Violates YAGNI. | |

**User's choice:** One unified `password_reset_tokens` table with `purpose` column
**Notes:** Table name retained for grep continuity; not renamed despite holding invitations too.

---

## actor_email_snapshot capture mechanism (INFRA-39)

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Explicit `audit.emit(actor_email_snapshot=...)` kwarg | 70 mechanical callsite edits + permanent code-review rule. AST-greppable but one missed callsite = silent NULL forever. | |
| (b) Internal lookup inside `emit()` | Zero callsite churn; one cheap SELECT per emit (SA identity map cache makes it free when User in session). Requires raw SQL by table name to avoid import. | |
| (c) ContextVar middleware — ActorContext | Mirrors RequestIdMiddleware pattern. Middleware sets actor on request entry; audit.emit reads it. ARQ tasks set via on_job_start. No callsite churn, no DB query. | |
| Hybrid: (c) primary + (a) override | ContextVar default + explicit kwarg overrides for batch/background contexts. Most flexible. | ✓ |

**User's choice:** Hybrid — (c) ContextVar primary + (a) explicit override
**Notes:** Reuses existing ContextVar precedent (Phase 14 RequestIdMiddleware, Phase 18 ARQ on_job_start structlog binds). Override path matters for batch reconciliation jobs.

---

## LOCKED_EMAIL_TEMPLATES initial content (INFRA-36)

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-register all 14 v1.6 template identifiers up-front | Mirrors INFRA-34 / INFRA-15 discipline. Downstream phases 42/44/45 ship template content; constant names already locked → zero AST-gate churn. | ✓ |
| Ship empty frozenset + AST gate only | Phase 41 lands gate machinery; each phase extends frozenset as templates land. Cost: reintroduces the churn INFRA-15 banned. | |
| Pre-register only Phase-42 templates | Compromise. Gate exercised end-to-end via first real dispatcher call; defers 13 identifiers. Partial churn. | |

**User's choice:** Pre-register all 14 v1.6 template identifiers up-front
**Notes:** Bedrock-first project philosophy is load-bearing — INFRA-15 discipline preserved.

### Follow-up — entry shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single template-id (frozenset[str]) | Mirrors LOCKED_AUDIT_EVENTS exactly. Each id resolves to (subject, html, text) record inside per-domain email_templates.py registry. Dispatcher signature: `send_email(template_id, **vars)`. | ✓ |
| Triple (subject_const, html_const, text_const) | Higher defense-in-depth (subject can't drift from body) but heavier surface; cohesion already structurally enforced by per-domain registry. | |

**User's choice:** Single template-id (frozenset[str])
**Notes:** Symmetry with LOCKED_AUDIT_EVENTS preferred over marginal triple-cohesion guarantee.

---

## Claude's Discretion

- Exact Pydantic field types/names inside each of the 11 new payload schemas (INFRA-35 leaves field shape to implementor, with `extra='forbid'` + `audit_correlation_id: UUID | None` as constraints).
- Internal ARQ task signature for the future `dispatch_email` job — Phase 42 owns this; Phase 41 only declares the Protocol slot.
- Migration file docstring wording.
- Exact `xfail` reason string in `test_password_reset_no_oracle.py`.
- Whether `users.deleted_at` gets a dedicated index (recommend no — partial-UNIQUE already covers the predicate).

## Deferred Ideas

- `email_send_log` table — Phase 42 (EMAIL-07 bounce webhook). Migration 0026.
- `payment_receipts` idempotency table — Phase 45 (NOTIFY-11). Migration 0027.
- Shim removal for `User` import path — DEFER-41-shim queued for v1.7 backlog.
- Cleanup cron for `password_reset_tokens` — Phase 44.
- `actor_display_name` formatting (full vs first-name + last-initial) — Phase 43 discuss-phase concern.
- Owner sign-off rows for email templates — recorded at VER-14 (Phase 46) against the 15 constant names locked in Phase 41.
- DMARC subdomain layout (`mail.sportzal.ru` vs alternate) — Phase 42 EMAIL-05.
- Email-verify flow policy (trust-owner-entered vs click-to-verify) — open conflict #7, Phase 43.
- `notifications` module placeholder vs resurrect — open conflict #3, Phase 45.
- Template engine (Jinja2 SandboxedEnvironment vs `Final[str]` f-strings) — open conflict #4, Phase 42.
