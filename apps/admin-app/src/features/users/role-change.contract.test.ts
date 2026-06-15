/**
 * Contract test: role-change real backend JSON × FE Zod UsersListResponseSchema (Phase 117 Plan 02).
 *
 * Loads the captured ASGITransport response (GET /api/v1/users after a role change)
 * from the backend capture test and parses it with the REAL runtime schema that
 * the useUsers() hook uses.
 *
 * The PATCH /api/v1/users/{id}/role returns 204 No Content (no JSON body).
 * The captured fixture is the list response (the real wire shape for user items).
 *
 * Failure = the backend serializer changed a field name without a matching FE Zod update.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { UsersListResponseSchema } from './schemas'

const captured = JSON.parse(
  readFileSync(join(__dirname, 'capture/role-change-response.json'), 'utf-8'),
) as unknown

describe('role-change contract — real backend JSON × FE Zod schema', () => {
  it('parses captured users list response with UsersListResponseSchema', () => {
    expect(() => UsersListResponseSchema.parse(captured)).not.toThrow()
    const result = UsersListResponseSchema.parse(captured).data
    expect(Array.isArray(result.items)).toBe(true)
    expect(typeof result.total).toBe('number')
    // At least one item exists (the seeded owner).
    expect(result.items.length).toBeGreaterThan(0)
    // The updated user's role is 'owner' after role change.
    const updatedUser = result.items.find((u) => u.role === 'owner')
    expect(updatedUser).toBeDefined()
  })
})
