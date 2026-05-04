// FIXTURE: must trigger the no-raw-fetch rule —
// fetch() may only be called inside src/shared/api/services/http/**.
// Run via scripts/assert-eslint-fixtures.mjs.
export const leaked = fetch('/api/v1/clients')
