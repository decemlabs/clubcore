---
status: partial
phase: 86-gym-info-cms
source: [86-VERIFICATION.md]
started: 2026-06-06
updated: 2026-06-06
---

## Current Test

[awaiting human testing — deferred during autonomous run per operator-pending-verify-autodefer]

## Tests

### 1. End-to-end render on fresh docker stack (Success Criterion 3)
steps: `docker compose up`, run migrations (`alembic upgrade head`), open client-pwa, navigate to GymInfoSheet
expected: Sheet renders "Мой зал · Тверская", address, weekly hours, amenities (8), rules (5), contacts — all from the DB row seeded by migration 0059 (not data/gym.js)
result: [pending]

### 2. Open/closed badge time-dependent behavior in browser
steps: Open GymInfoSheet when Moscow time is known (inside vs outside gym hours)
expected: "Сейчас открыто" (chip-accent) during open hours; "Закрыто" (chip-danger) outside; today's row listed first; derivation uses Europe/Moscow
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
