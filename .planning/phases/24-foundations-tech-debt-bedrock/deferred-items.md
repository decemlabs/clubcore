# Phase 24 — Deferred Items

Items discovered during plan execution that are out of scope for the current plan and should be addressed in a follow-up.

## Pre-existing admin-web typecheck failures (discovered during 24-04)

Verified on master at commit `dfa3072` (the Task-1 commit of 24-04, which only touches backend files). `pnpm typecheck` reports 3 errors that pre-date 24-04:

- `src/features/memberships/components/SellMembershipDialog.tsx:99:57` — `Argument of type 'string | null' is not assignable to parameter of type 'string'.` Not introduced by 24-04 (no admin-web edits in Task 1, and identical error appears with Task 2 stashed).
- `src/features/visits/components/CheckInPage.test.tsx:83:5` — `Type 'object | undefined' is not assignable to type 'Membership | undefined'.` Test fixture shape drift; pre-existing.
- `src/features/visits/components/RecentVisitsBlock.test.tsx:46:56` — `Conversion of type '{ data: never[]; isPending: false; ... }' to type 'UseQueryResult<Visit[], Error>' may be a mistake.` Test mock object missing TanStack Query result shape; pre-existing.

**Disposition:** These are out-of-scope for 24-04 (DEBT-02 mock/http parity). Recommend a small follow-up plan in v1.3 (e.g. inside Phase 28 FE-13 typecheck pass, or a dedicated tech-debt micro-plan) to fix the three errors. Files modified by 24-04 (`mock/memberships.ts`, `http/memberships.ts`, `contracts/memberships.ts`, the new test file) are typecheck-clean.
