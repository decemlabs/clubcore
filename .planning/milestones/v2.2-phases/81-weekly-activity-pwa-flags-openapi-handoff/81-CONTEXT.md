# Phase 81: Weekly Activity + PWA Flag Flips + OpenAPI Handoff - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

The v2.2 finale. Three strands: (1) a new `GET /client/activity/weekly` endpoint returning the
current Moscow week's per-day workout counts; (2) flipping the two already-built-but-hidden PWA
feature flags ON (`weeklyActivity` bars wired to the new endpoint; `linkedCard` CardSheet wired to
the Phase-79 payment-method endpoints) + removing the per-booking «Авто-оплата тренировок» toggle +
the ФЗ-376 consent disclosure UI; (3) the OpenAPI handoff — byte-stable regen of `openapi.json` +
`schema.d.ts` with all v2.2 client-portal paths, staff contract byte-identical, CI drift gates green.
WACT-01, WACT-02, PAYM-05, HND-01. Everything client-side under `require_client()`; staff contract frozen.

</domain>

<decisions>
## Implementation Decisions

### Weekly Activity Endpoint (`GET /client/activity/weekly`)
- Returns exactly 7 zero-filled objects for Mon–Sun of the **current** week in Europe/Moscow.
- `COUNT(*)` grouped by the `visits.gym_date` STORED generated column (`(checked_in_at AT TIME ZONE 'Europe/Moscow')::date`), filtered `gym_date BETWEEN <monday> AND <sunday>`. NEVER `DATE(checked_in_at)`.
- `minutes` is always `null` (no duration column in schema); `workouts` = per-day count.
- Response: 7-element array ordered Mon→Sun, each `{ date (ISO), workouts: int, minutes: null }`.
- IDOR-safe: `client_id` from `require_client()` principal only; raw-SQL read (D-54-08).

### TZ Correctness & Determinism
- Week anchor computed from `now()` in Europe/Moscow, Monday start.
- Golden TZ test (v1.8 VER-02 pattern): a visit with `checked_in_at = 21:30 UTC` has `gym_date` = the **next** Moscow calendar day and must land in that day's bucket.
- Zero-fill is app-side: the DB returns only days with visits; the service fills all 7 days (`workouts:0, minutes:null` for missing days).
- Empty week → all 7 days `workouts:0` (never a `[]` response).

### PWA Flag Flips + CardSheet + Consent UI
- Flip `PROFILE_FEATURE_FLAGS.weeklyActivity → true` (ProfileScreen.jsx ~line 26); wire the already-built (hidden) activity-bars card (~line 268) to `GET /client/activity/weekly` via a new TanStack Query hook in `clientQueries.ts`.
- Flip `linkedCard → true` in BOTH `PROFILE_FEATURE_FLAGS` (ProfileScreen.jsx ~line 29) and `SETTINGS_FEATURE_FLAGS` (SettingsScreen.jsx ~line 16); wire the "Привязанная карта •••• 4821" row + CardSheet to the Phase-79 `GET/DELETE/PATCH /client/payment-method` + `/autopay` endpoints.
- Remove the per-booking «Авто-оплата тренировок» toggle (anti-feature — double-billing vs PT-package credit model; locked v2.2 decision).
- ФЗ-376 consent UI: the CardSheet autopay-enable action shows the disclosure (списываемая сумма / периодичность / способ отмены) and sends `consent_acknowledged: true` to the Phase-79 PATCH `/autopay`; disabling needs no consent. (Phase 79 deliberately deferred the disclosure copy to this PWA work.)

### OpenAPI Handoff (HND-01)
- Regenerate `apps/backend/openapi.json` via `uv run python -m scripts.export_openapi`.
- Regenerate `packages/api-client/src/schema.d.ts` via `pnpm --filter @clubcore/api-client codegen` (openapi-typescript).
- Both byte-stable; commit both. Assert the **staff** contract is byte-identical — only new `Client-Portal`-tagged paths (`/client/payment-method*`, `/client/booking/{id}/reschedule`, `/client/activity/weekly`) are added.
- CI drift gates (`git diff --exit-code apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts`) must be green; Redocly lint passes.

### Claude's Discretion
- Exact endpoint response Pydantic model naming, the weekly-window SQL phrasing, the activity-hook + CardSheet component-internal state, and the consent disclosure exact wording (follow ФЗ-376 substance + existing PWA copy tone).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/backend/app/modules/visits/models.py` — `gym_date` STORED column (the grouping key) + `uq_visits_client_id_gym_date`.
- `apps/backend/app/modules/client_portal/router.py` + `service.py` — pattern for IDOR-safe raw-SQL client reads; add the activity endpoint here.
- Phase-79 endpoints `GET/DELETE/PATCH /client/payment-method` (+ `/autopay`) — the CardSheet wiring targets.
- PWA: `ProfileScreen.jsx` (`PROFILE_FEATURE_FLAGS`, hidden activity-bars card ~line 268), `SettingsScreen.jsx` (`SETTINGS_FEATURE_FLAGS`, hidden card row ~line 294), `clientQueries.ts` (TanStack Query hooks — add `useClientWeeklyActivity` + payment-method hooks), the per-booking autopay toggle to remove.
- `apps/backend/scripts/export_openapi.py` (`uv run python -m scripts.export_openapi`); `packages/api-client` `codegen` script.

### Established Patterns
- Golden TZ test precedent: v1.8 VER-02 (`tests/unit/visits/test_schemas.py` and similar) — assert Moscow-day bucketing.
- CI drift gates in `.github/workflows/ci.yml` (openapi.json L90-94; schema.d.ts L159-162); Redocly lint L211-225.
- Client read = raw SQL (D-54-08), no cross-module ORM imports.

### Integration Points
- New endpoint registered in `client_portal/router.py`.
- PWA hooks in `clientQueries.ts` consumed by ProfileScreen (bars) + Settings/CardSheet (card).
- Handoff: regen both generated artifacts and commit; CI drift gates enforce byte-stability.

</code_context>

<specifics>
## Specific Ideas

- Group strictly on the `gym_date` STORED column — the whole point of the golden TZ test is that 21:30 UTC rolls into the next Moscow day.
- `minutes` is `null` everywhere (no duration data); don't fabricate it.
- Staff contract MUST remain byte-identical in `openapi.json` — only client-portal paths are additive (the v2.0/v2.2 invariant).
- The activity-bars card and card row already EXIST behind flags — this is flip + wire, not rebuild.
- ФЗ-376 disclosure is a real compliance element: amount + periodicity + cancellation method must be shown before autopay enable.

</specifics>

<deferred>
## Deferred Ideas

- A formal UI-SPEC was intentionally skipped (user accepted): the activity-bars card and card row already exist behind feature flags; this phase is flip + wire + a well-specified ФЗ-376 disclosure. Plan carries concrete PWA + consent acceptance criteria instead.
- `charge_expiring_autopay` ARQ cron (real recurring charges) → v2.3 (APAY-01..03).
- Workout `minutes`/type per day → needs a future duration column; out of scope.

</deferred>
