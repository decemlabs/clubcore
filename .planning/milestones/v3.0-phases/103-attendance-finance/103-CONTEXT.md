# Phase 103: Attendance + Finance - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the admin-app **attendance** (visits list + check-in), **load** (visits
aggregate), **cashbox** (cash ledger), and **finance** (revenue report + online
payments) screens from mocks to the real backend over the P100 transport seam.
Reception checks in visits on real data; owner sees cashbox, revenue, and online
payments — all without mocks.

**In scope:** Attendance (GET /visits list + POST /visits check-in, reception+owner);
Load (/reports/visits aggregate, owner-only); Cashbox (GET /payments ledger +
client-side daily totals + refund rows read-only, owner-only); Finance
(/reports/revenue + online-payment method slice, owner-only); per-domain zod layers;
nav owner-only gating correction.

**Out of scope:** formal Reports page + CSV export (Phase 104); dashboard/audit-log/
settings/users (Phase 104); any new backend endpoints (wire-only). No cash-refund
ACTION (no `/payments` refund endpoint — refunds are membership/PT-scoped, wired P101).
</domain>

<decisions>
## Implementation Decisions

### Attendance (visits list + check-in)
- Attendance page renders the **real visits list `GET /api/v1/visits`** (paginated,
  date-filtered: `from`/`to`/`page`/`pageSize`) — reconcile the mock `useAttendance`
  shape to the real `VisitResponse` list (id/clientId/membershipId/checkedInAt/gymDate/
  channel/checkedInBy). Reception + owner (VIEW VISITS).
- **Check-in is `POST /api/v1/visits {clientId}`** (the roadmap's `/visits/check-in`
  prose is corrected — the real endpoint is `POST /visits`; body is sealed to `{clientId}`).
  Reception + owner (CHECK_IN VISITS, not owner-only). Server derives membership/gymDate/
  channel='reception'/checkedInBy.
- Handle the **3-stage 409 chain as distinct states**: `outside_gym_hours` → «Вне часов
  работы», `no_active_membership` → «Нет активного абонемента», `duplicate_checkin` →
  «Уже отмечен сегодня» (DB UNIQUE 1/day).
- **Optimistic** add to the visits list + rollback on 409 (admin-web FE-08 pattern);
  surface the specific 409 reason. No Idempotency-Key needed here.
- **Reuse the searchable client picker** (from the P102 booking modal) for selecting the
  client to check in. Optionally read `GET /visits/_meta` (gym hours, cacheable) to
  pre-validate.

### Owner-only nav gating (correction to P100)
- Load, Cashbox, and Finance all hit owner-only endpoints (`/reports/*` = VIEW REPORTS
  owner-only; global `/payments` = VIEW PAYMENTS owner-only). **Mark Load (Загруженность)
  + Cashbox (Касса) + Finance `ownerOnly: true` in `nav-items.ts`** (P100 only gated
  Финансы + Отчёты — extend it). **Attendance (Посещаемость) stays reception+owner.**
- can() resources: **`reports`** for Load + Finance-revenue; **`payments`** for Cashbox.
- Friendly **«Недостаточно прав»** Lock-EmptyState (P101 pattern) if an owner-only screen
  is reached directly by reception.

### Cashbox (cash ledger + refund rows) & online payments
- Cashbox = **`GET /api/v1/payments`** (owner-only), date-filtered (`receivedFrom`/
  `receivedTo`/`method`/`page`/`pageSize`), showing sell + refund rows (`amountKopecks`
  signed; `refundOf != null` = refund row). **Daily totals computed client-side** (SUM
  by gym/received date — no aggregate endpoint).
- **"Refund flow wired" = refund ROWS displayed read-only** in the ledger. The refund
  *action* lives on the membership/PT detail (P101 — `POST /memberships|pt-packages/{id}/refund`);
  there is NO `/payments` refund endpoint, so do NOT add a cashbox-refund action (would be
  fake). Document this limitation. (Optionally link a refund row → its membership.)
- **Online payments** (Finance criterion 4) = the **`method='online'` slice** of
  `/payments` + the revenue report `byMethod.online` breakdown. No dedicated
  online-payments endpoint.

### Load + Finance reports (no NaN)
- Load = **`GET /api/v1/reports/visits?fromDate&toDate`** → `{daily[], hourly[],
  averagePerDay, fromDate, toDate}`. Buckets are **SPARSE** (only non-zero). **Client-side
  fill all 24 hours / all calendar days in range with 0** so the heatmap/chart never shows
  NaN (criterion 2).
- Finance = **`GET /api/v1/reports/revenue?fromDate&toDate&groupBy=day|month`** →
  `buckets[{period, netKopecks(signed), byMethod{cash,online}, bySubjectKind{membership,
  pt_package}}]`. groupBy day|month toggle; format kopecks; empty-range safe.
- **Date-range picker per screen** (default ~last 30 days). Client-validate the **366-day
  cap** + `toDate ≥ fromDate` (backend 422s otherwise).
- **CSV export deferred to Phase 104** (its criteria own "all reports with CSV export").
- Flip each screen's `queryFn`→http; **keep mock files behind `VITE_API_MODE=mock`**;
  remove the dead default-mock branch.

### Claude's Discretion
- `features/{attendance,load,cashbox,finance,reports}` layout (api+schemas+keys),
  bucket-fill utility, daily-totals computation, date-range picker component, and test
  organization — following P100/P101/P102 exemplars (esp. the existing `features/visits`
  + `features/payments` from P101, which this phase extends).
</decisions>

<code_context>
## Existing Code Insights (verified — wire camelCase via Pydantic aliases)

### Backend endpoints
- **Visits**: `GET /api/v1/visits` (params clientId?/from?/to?/page/pageSize → {items,total,
  page,pageSize}; VIEW VISITS reception+owner); `POST /api/v1/visits {clientId}` (CHECK_IN
  reception+owner; 409 chain outside_gym_hours→no_active_membership→duplicate_checkin;
  server-derived membershipId/gymDate/channel/checkedInBy); `GET /visits/_meta`
  (gymHoursStart/End, cacheable). VisitResponse: id/clientId/membershipId/checkedInAt/
  gymDate/channel/checkedInBy/createdAt.
- **reports/visits** (OWNER-ONLY): `GET /api/v1/reports/visits?fromDate&toDate` →
  `{daily[{date,count}], hourly[{hour,count}], averagePerDay, fromDate, toDate}` — SPARSE
  buckets; 366-day cap; toDate<fromDate→422.
- **reports/revenue** (OWNER-ONLY): `GET /api/v1/reports/revenue?fromDate&toDate&groupBy`
  → `{buckets[{period, netKopecks, byMethod{cash,online}, bySubjectKind{membership,
  pt_package}}], fromDate, toDate, groupBy}`.
- **payments** (global OWNER-ONLY): `GET /api/v1/payments?page&pageSize&subjectKind?&
  subjectId?&receivedByUserId?&receivedFrom?&receivedTo?` → {items,total,page,pageSize}.
  PaymentResponse: id/subjectKind/subjectId/amountKopecks(signed)/method(cash|online)/
  receivedAt/receivedByUserId/refundOf(nullable)/auditLogId. Scoped reception endpoints:
  `/payments/by-client/{id}`, `/payments/by-membership/{id}` (already used P101).
- **online payments**: no dedicated endpoint → method='online' rows in /payments.
- Response envelope `{data:…}`; error `{code,message,fields?}`; all dates MSK (gymDate is a
  STORED generated column). reports .csv variants exist (deferred to P104).

### admin-app current (files to flip — apps/admin-app/src/)
- `features/attendance/{api.ts,types.ts}` (`useAttendance`) + `mocks/` → wire to GET /visits + POST /visits.
- `features/load/{api.ts,types.ts}` (`useLoad`) → /reports/visits (hourly+daily, fill zeros).
- `features/cashbox/{api.ts,types.ts}` (`useCashbox`) → GET /payments + client-side totals.
- `features/finance/{api.ts,types.ts}` (`useFinance`) → /reports/revenue + payments(method=online).
- **NEW** `features/reports/` (revenue + visits report schemas/keys) — shared by Load/Finance.
- Pages call hooks → swap is transparent: `pages/{attendance,load,cashbox,finance}/`.
- **EXTEND existing (P101):** `features/visits/` (useClientVisits) + `features/payments/`
  (usePaymentsByClient) — keep as-is, add list/check-in/global-payments hooks.
- **Exemplars:** `features/{clients,memberships,bookings,payroll}/{api.ts,schemas.ts}`
  (staffRequest + Schema.parse(raw).data + query-key factory + can()-gating; optimistic
  onMutate/rollback from memberships freeze + bookings race-handling for check-in 409).
- Nav: `src/layouts/AppLayout/nav-items.ts` — add ownerOnly to Загруженность/Касса/Финансы.
- can() resources: `visits` (reception+owner), `reports` (owner-only), `payments` (owner-only).

### admin-web analog
- `features/visits/` (CheckInPage with FE-08 optimistic check-in + 409 handling, useCheckIn/
  useGymMeta/useRecentVisitsByClient) — the porting analog for the check-in flow. No
  reports/cashbox/finance in admin-web → P100-P102 admin-app patterns are the exemplar.
</code_context>

<specifics>
## Specific Ideas

- Check-in real endpoint is `POST /visits {clientId}` — NOT `/visits/check-in` (roadmap prose corrected).
- 3 distinct 409 reasons must render as distinct Russian states (anti-confusion).
- Cashbox refund = display rows only; no cash-refund action (no backend endpoint).
- Report buckets are sparse → client-side zero-fill to avoid NaN (criterion 2).
- 3 of 4 screens are owner-only — nav gating corrected accordingly.
- All money integer kopecks; all dates MSK; format with existing helpers.
</specifics>

<deferred>
## Deferred Ideas

- Formal Reports page + CSV export for all reports → Phase 104.
- Dashboard / audit-log / settings / users → Phase 104.
- Cash-refund action on cashbox — N/A (no backend endpoint; refunds are membership/PT-scoped, P101).
- /reports/clients + /reports/trainers (Earnings) → Phase 104.
</deferred>
