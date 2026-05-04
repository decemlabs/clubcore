---
status: deferred
phase: 11-clients-http-shape-adapter
source: [11-02-PLAN.md, 11-E2E-RUNBOOK.md]
started: "2026-05-04T20:10:00Z"
updated: "2026-05-04T20:20:00Z"
deferred_until: "phase-12.1-clients-service-commit"
---

# Phase 11 — Human-Verify Outcome

## Summary

Phase 11's actual contract — closing INTEGRATION-CHECK F-01 (BLOCKER) and F-02 (BLOCKER)
in `apps/admin-web/src/shared/api/services/http/clients.ts` — is mechanically verified.
The runbook walkthrough (`11-E2E-RUNBOOK.md`, success criterion #4) is **deferred** because
auto-verification surfaced a backend commit defect that lives outside Phase 11's scope.

## What was verified automatically (curl + cookies, live API on :8000)

| Assertion | Result |
|---|---|
| `POST /auth/login` → 200, `sz_access` + `sz_refresh` + `sportzal_csrf` cookies set | ✓ |
| `POST /clients` minimal body (`lastName,firstName,middleName,phone`) → 201; response uses `birthday` (not `birthDate`); `lastName/firstName/middleName` separate | ✓ |
| `POST /clients` full body with `birthday:"1990-04-12"` + `email:"ivan@example.com"` → 201 | ✓ |
| `POST /clients` with stale `birthDate` key (pre-adapter shape) → backend 422 `extra_forbidden` (proves F-02 was real and adapter rename is correct) | ✓ |
| `POST /clients` with `email:""` (pre-adapter empty-string leak) → backend 422 (proves adapter empty-string omission is correct) | ✓ |
| `_clientsAdapter.test.ts` — 26/26 unit tests pass | ✓ |
| `apps/admin-web` full suite — 108/108 tests pass (4 new from Plan 11-02) | ✓ |
| `pnpm -F sportzal-adminka typecheck` exits 0 | ✓ |

## Why SC #4 cannot tick today (NOT a Phase 11 defect)

`apps/backend/app/modules/clients/service.py` does not call `await session.commit()` at any
write site. `apps/backend/app/core/database.py:145` `get_db` opens a session, yields, and
exits — without an explicit commit, SQLAlchemy auto-rolls-back the unit of work.

Symptom in live API logs:
```
INSERT INTO clients (...) RETURNING ...
[client_created] full_name='Тестов Тест Тестович'
status_code=201            ← FE/curl sees success
ROLLBACK                    ← row never persists
```

`apps/backend/app/modules/auth/service.py` has `await session.commit()` at every write
site (login, refresh, logout, telegram bind), which is why login + cookies work end-to-end
but every clients write evaporates at request exit.

This is a Phase 8 (clients module) regression. Phase 11 changes nothing on the backend
and is not the cause.

## Resolution path

Tracked as **Phase 12.1 — clients-service-commit-fix** in ROADMAP.md.
Once that phase lands, re-run the runbook (`11-E2E-RUNBOOK.md`) end-to-end and tick SC #4.
Until then, Phase 11 is accepted on the strength of the API-shape contract verification
above and the 108 unit tests.

## Sign-off

- [x] FE adapter contract (F-01) verified via API + 26 unit tests
- [x] FE request-mapper contract (F-02) verified via API negative tests + adapter unit tests
- [x] Optimistic-update hardening (F-01 belt-and-suspenders) verified via 4 new regression tests
- [x] Live E2E runbook authored (`11-E2E-RUNBOOK.md`)
- [ ] Live E2E walkthrough end-to-end — **deferred** to post-Phase-12.1
