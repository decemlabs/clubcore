// FIXTURE: must trigger `import/no-restricted-paths` Pattern α zone (Phase 22 D-22-12).
// This fixture is in eslint.config.js `ignores: ['src/__fixtures/**']` so it does NOT fail CI.
// The verify-pattern-alpha.sh script un-ignores it temporarily (by copying it into
// src/features/clients/__test__/) and asserts the rule fires.

import { MembershipsBlock } from '@/features/memberships'
import { RecentVisitsBlock } from '@/features/visits'

export const illegal = { MembershipsBlock, RecentVisitsBlock }
