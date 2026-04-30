// FIXTURE: must trigger the VITE_API_MODE chokepoint rule —
// VITE_API_MODE may only be read inside src/shared/api/**.
// Run via scripts/assert-eslint-fixtures.mjs.
export const leaked = import.meta.env.VITE_API_MODE
