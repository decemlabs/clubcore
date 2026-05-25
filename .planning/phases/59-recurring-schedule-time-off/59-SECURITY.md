---
phase: 59
slug: recurring-schedule-time-off
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-25
---

# Phase 59 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env → config | `RECURRING_SLOT_HORIZON_DAYS` read from container env; controls generation volume | operator-set integer |
| migration → live schema | 0042 DDL alters `trainer_availability_slots` (used by booking FK) | schema mutation |
| client → API | owner request body (trainer_id, day/time windows, time-off window, ?force) | untrusted input |
| cron → audit log | system-generated `slot_published` carries NULL author across D-09 hard-fail validation | author-less audit payload |
| schedule → bookings | force-cascade cancellation via raw `sa.text()` UPDATE (no import edge, D-38-11) | cross-module mutation |
| cron actor → DB | cron has no human identity; bulk-inserts slots | author-less rows |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-59-01 | Tampering | LOCKED_AUDIT_EVENTS | mitigate | 4 events pre-registered in frozenset (89→93); AST gate rejects unregistered emits — `audit.py:422-431`, `test_audit_taxonomy.py:239` | closed |
| T-59-02 | DoS | recurring_slot_horizon_days | accept | Operator env var only (default 56); no untrusted path; generation bounded `now()..now()+HORIZON` + ON CONFLICT — `config.py:110` | closed |
| T-59-03 | Tampering/Integrity | created_by_user_id nullable | mitigate | `op.alter_column(nullable=True)` + read path widened to `UUID\|None`; downgrade guard blocks reversal if NULL rows exist — `0042.py:184-227`, `models.py:93`, `schemas.py:116` | closed |
| T-59-04 | DoS (dup rows) | trainer_availability_slots | mitigate | `UNIQUE(trainer_id, start_time)` backs ON CONFLICT DO NOTHING — `0042.py:194-198`, `models.py:146-151` | closed |
| T-59-05 | Integrity | day_of_week/time/window | mitigate | CHECK constraints (0..6, end>start, valid_until>=valid_from, block_end>block_start) — `0042.py:99-112,165-168` | closed |
| T-59-06 | Tampering | RecurringSlotTemplateCreate | mitigate | Pydantic `Field(ge=0,le=6)` + end>start + valid-window validators (double gate w/ CHECK) — `schemas.py:182-198` | closed |
| T-59-07 | Tampering | TimeOffCreate | mitigate | tz-aware field validator + block_end>block_start model validator — `schemas.py:234-244` | closed |
| T-59-08 | Integrity (read crash) | SlotResponse null author | mitigate | `created_by_user_id: UUID\|None` + None-safe audit stringify — `schemas.py:116`, `service.py:386-388` | closed |
| T-59-09 | Elevation + DoS | time-off create+?force / SlotPublishedPayload | mitigate | `require_permission(CREATE, SCHEDULE_SLOTS)` OWNER_ONLY (force AND non-force) + payload `UUID\|None=None` for D-09 gate — `router.py:470`, `audit_payloads.py:367` | closed |
| T-59-10 | Repudiation / silent data loss | force-cascade booking cancel | mitigate | 409-without-force hard gate (no silent cancel); each cascade emits `booking_cancelled` audit + DM — `service.py:899,981-1005,1067` | closed |
| T-59-11 | IDOR | trainer_id param | mitigate | Overlap SELECT scoped `WHERE trainer_id=:tid`; FK RESTRICT — `service.py:885`, `0042.py:65-69,140-144` | closed |
| T-59-12 | Tampering | overlap detection | mitigate | Single-UoW commit; `InternalConsistencyError` on 0-row RETURNING rolls back whole txn — `service.py:963-970,1067` | closed |
| T-59-13 | DoS (row explosion) | bulk INSERT | mitigate | `pg_insert().on_conflict_do_nothing(['trainer_id','start_time']).returning(id)`; bounded window — `repository.py:590-591`, `service.py:1297` | closed |
| T-59-14 | Spoofing / actor assumption | NULL created_by_user_id | mitigate | Cron emits `slot_published` with `created_by_user_id=None`, no require_permission path; read path widened — `generate_recurring_slots.py:68`, `service.py:1375` | closed |
| T-59-15 | Integrity (DST drift) | expansion arithmetic | mitigate | `ZoneInfo("Europe/Moscow")` + `.astimezone(UTC)`; golden test (2026-03-30 10:00 MSK → 07:00 UTC); no naive timedelta — `service.py:1155,1203-1225` | closed |
| T-59-16 | Integrity (generate into blocked window) | time-off skip | mitigate | Python-side `list_active_time_off_for_trainers` pre-filter; only clean rows inserted — `repository.py:510-536`, `service.py:1310-1342` | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-59-01 | T-59-02 | `RECURRING_SLOT_HORIZON_DAYS` is an operator-set env var with no untrusted-user path; generation is bounded by the horizon predicate and ON CONFLICT DO NOTHING prevents row duplication. A misconfigured huge value affects only operator-owned generation volume. | Andre (owner) | 2026-05-25 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-25 | 16 | 16 | 0 | gsd-security-auditor (sonnet) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-25
