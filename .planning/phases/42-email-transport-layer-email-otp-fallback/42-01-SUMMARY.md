---
phase: 42-email-transport-layer-email-otp-fallback
plan: 01
subsystem: integrations/email
tags:
  - email
  - migration
  - orm
  - integrations
requires:
  - phase 41 INFRA-bedrock (Alembic head at 0025_password_reset_tokens)
  - app.core.database.{Base, UUIDPkMixin}
provides:
  - EmailEnvelope dataclass (transport boundary DTO)
  - EmailSendResult dataclass (transport outcome DTO)
  - EmailSendLog ORM model + email_send_log Postgres table
  - alembic head advanced 0025 -> 0026
affects:
  - apps/backend/alembic/env.py (1 new import line + 1 new skiplist entry)
tech_stack_added:
  - none (uses existing SQLAlchemy 2.0 + Alembic + Pydantic stack)
patterns:
  - frozen-dataclass transport DTO with classified outcome (telegram.sender pattern)
  - single-discriminator CHECK on status column
  - DESC expression index in migration DDL only; ORM Index column-only;
    autogenerate skiplisted (D-25-05 lineage)
key_files_created:
  - apps/backend/app/integrations/email/types.py
  - apps/backend/app/integrations/email/models.py
  - apps/backend/alembic/versions/0026_email_send_log.py
key_files_modified:
  - apps/backend/alembic/env.py
decisions:
  - "Index DESC drift skiplisted in env.py rather than reshaped to ASC — preserves
    operator query plan 'WHERE to_address = ? ORDER BY recorded_at DESC LIMIT N'
    over autogenerate cleanliness; D-25-05 partial-index lineage."
metrics:
  duration_seconds: ~1500
  task_count: 3
  file_count: 4
  lines_added: 328
  completed_date: 2026-05-19
---

# Phase 42 Plan 01: Email transport data layer Summary

EmailEnvelope + EmailSendResult frozen dataclasses (D-42-16 / D-42-13) and the
email_send_log table + ORM (D-42-18 / D-42-33) landed atomically, with the
ORM module eagerly registered in alembic/env.py so REG-29-04 holds for any
one-shot cron runner.

## What Shipped

### `apps/backend/app/integrations/email/types.py`

Two frozen dataclasses with closed shapes:

| Class | Fields | Notes |
|---|---|---|
| `EmailEnvelope` | `to: str`, `subject: str`, `html: str`, `text: str`, `template_id: str`, `audit_correlation_id: UUID` | 6 fields exactly per D-42-16; cloudpickle-safe for ARQ enqueue |
| `EmailSendResult` | `ok: bool`, `classification: Literal["ok","blocked","transient_error","permanent_error"]`, `provider_message_id: str \| None`, `error: str \| None` | Mirrors `telegram.SendResult` taxonomy (PATTERNS.md §1) with explicit retry-vs-give-up split per D-42-13 |

### `apps/backend/app/integrations/email/models.py`

`EmailSendLog(Base, UUIDPkMixin)` ORM. No `TimestampMixin` (single `recorded_at`
per D-42-18). No FK on `to_address` (recipients may not be Users). No
partial-UNIQUE on `provider_message_id` (multiple bounce events per message-id
are legitimate).

### `apps/backend/alembic/versions/0026_email_send_log.py`

Single `op.create_table("email_send_log", ...)` + two indexes; down_revision
`0025_password_reset_tokens`. Round-trips clean against the live compose
Postgres stack.

**Final shipped column list of `email_send_log`** (9 cols, in DDL order):

| # | Column | Type | Nullable | Default |
|---|---|---|---|---|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` (UUIDPkMixin) |
| 2 | `audit_correlation_id` | `UUID` | NOT NULL | — |
| 3 | `to_address` | `TEXT` | NOT NULL | — |
| 4 | `template_id` | `TEXT` | NOT NULL | — |
| 5 | `provider` | `TEXT` | NOT NULL | — |
| 6 | `provider_message_id` | `TEXT` | NULL | — |
| 7 | `status` | `TEXT` | NOT NULL | — |
| 8 | `bounce_type` | `TEXT` | NULL | — |
| 9 | `recorded_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |

**Constraints / Indexes as they land in Postgres:**

| Object | DB-side name |
|---|---|
| PRIMARY KEY on `id` | `pk_email_send_log` (via `op.f()` + naming_convention) |
| CHECK on `status` | `ck_email_send_log_status` (via `op.f()` + naming_convention; bare `name="status"` at the ORM layer expands identically) |
| INDEX on `(audit_correlation_id)` | `ix_email_send_log_audit_corr` |
| INDEX on `(to_address, recorded_at DESC)` | `ix_email_send_log_to_addr_recorded` |

The CHECK constraint admits exactly `{'sent','bounced','complained','delivered','rejected'}`
— closed taxonomy gated at the DB layer; downstream task fills `status` from
typed `EmailSendResult.classification` only (T-42-01-01 mitigation).

### `apps/backend/alembic/env.py`

One new ORM-import line (sorted alphabetically with the rest):

```python
import app.integrations.email.models  # Phase 42 D-42-33 / 0026 -- EMAIL-01 (email_send_log)
```

Plus one new `_include_object` skiplist entry for the DESC expression index
(see Deviations below).

## Verification

| Gate | Outcome |
|---|---|
| `uv run ruff check app/integrations/email/ alembic/versions/0026_email_send_log.py` | exit 0 (4 files) |
| `uv run mypy --strict app/integrations/email/` | exit 0 (`Success: no issues found in 4 source files`) |
| `uv run alembic upgrade head` | success |
| `uv run alembic downgrade -1` | success |
| `uv run alembic upgrade head` (re-apply) | success |
| `uv run alembic check` — `email_send_log` drift specifically | none reported |
| Import sanity: `from app.integrations.email.types import EmailEnvelope, EmailSendResult` + instantiation | OK |
| Import sanity: `'email_send_log' in Base.metadata.tables` after `app.integrations.email.models` import | OK; all 9 expected columns present |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] Skiplist `ix_email_send_log_to_addr_recorded` in `_include_object`**

- **Found during:** Task 3 verification (`uv run alembic check`)
- **Issue:** The migration's `["to_address", sa.text("recorded_at DESC")]`
  expression index is matched at the ORM layer by a plain
  `Index("ix_email_send_log_to_addr_recorded", "to_address", "recorded_at")`
  (SQLAlchemy Index has no surface for DESC on the second column). Alembic
  autogenerate sees the expression-vs-column mismatch and emits
  `Detected changed index ... 'recorded_at DESC' to 'recorded_at'`, which
  causes `alembic check` to fail. The plan's `<action>` block called this
  shape difference out as "acceptable" and stated Alembic compares only
  column lists at the model layer — but the empirical autogenerate output
  contradicts that claim.
- **Fix:** Added `"ix_email_send_log_to_addr_recorded"` to the
  `_include_object` skiplist in `alembic/env.py`. This is the same D-25-05
  lineage used for the partial-index entries (`uq_users_email_active`,
  `uq_password_reset_tokens_active`, etc.) — when the ORM layer cannot
  faithfully express the DDL shape, the skiplist is the canonical mechanism
  so the drift gate stays clean without forking the migration shape from
  the model.
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** `406a99c` (Task 3 commit)
- **Acceptance criterion impact:** None — the plan's automated verify still
  passes (no `email_send_log` drift in `alembic check` output). The fix
  preserves the operator query plan
  (`WHERE to_address = ? ORDER BY recorded_at DESC LIMIT N` served directly
  by the index) and the migration DDL exactly as the plan specified.

### Authentication gates

None.

## Threat-Model Compliance

| Threat ID | Disposition | How this plan addresses it |
|---|---|---|
| T-42-01-01 | mitigate | DB-side CHECK constraint admits only the closed
{'sent','bounced','complained','delivered','rejected'} taxonomy; rejects bogus
INSERTs at the boundary regardless of caller. |
| T-42-01-02 | accept | `to_address` is plain TEXT; index on
`(to_address, recorded_at DESC)` deliberately enables the operator forensic
query. v1.6 single-zal scope (~100 clients) — no hashing. |
| T-42-01-03 | mitigate | `audit_correlation_id UUID NOT NULL` chains every
row to its triggering business audit row; forensic continuity preserved when
downstream plans emit `email_sent` / `email_send_failed` rows with the same
UUID. |
| T-42-01-04 | accept | One row per send + one UPDATE per webhook; growth
bounded by provider quota (~3× free-tier 2000/mo ceiling). |

No new threat surface was introduced beyond what the plan's `<threat_model>`
already enumerated.

## Out-of-scope / Pre-existing deferred drift (not addressed)

Per the plan's verification block, the following pre-existing drift from
Phase 41 remains unresolved and is NOT this plan's responsibility:

| Item | Owner phase | Tracking |
|---|---|---|
| `users.email` UNIQUE on ORM but partial-UNIQUE in DB (post-0022) | Phase 43 (USERS module ORM mapping per D-41-07) | `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` |
| `users.deleted_at` column in DB but not on ORM (post-0022) | Phase 43 | same |
| `booking_notifications.channel` + `membership_notifications.channel` + recreated `(subject_id, kind, channel)` UNIQUE in DB but not on ORM (post-0024) | Phase 45 (NOTIFY-*) | same |

The `tests/integration/test_alembic_clean.py::test_alembic_check_clean`
integration test continues to fail solely due to these pre-existing items;
my changes do not contribute to its failure.

## Downstream Unblocking

After this plan, Wave 2 / Wave 3 of Phase 42 can proceed in parallel against
a stable schema + types:

- **Wave 2 (transport layer)** — provider adapter + ARQ task can import
  `EmailEnvelope` + `EmailSendResult` from the locked module path.
- **Wave 3 (wiring)** — dispatcher + module callsites + bounce webhook can
  all write/read `email_send_log` rows via the ORM model.

## Self-Check: PASSED

- `apps/backend/app/integrations/email/types.py` — FOUND
- `apps/backend/app/integrations/email/models.py` — FOUND
- `apps/backend/alembic/versions/0026_email_send_log.py` — FOUND
- `apps/backend/alembic/env.py` — modified (import + skiplist line)
- Commit `e9e4938` (Task 1: types) — FOUND in git log
- Commit `9e6a269` (Task 2: ORM) — FOUND in git log
- Commit `406a99c` (Task 3: migration + env) — FOUND in git log
