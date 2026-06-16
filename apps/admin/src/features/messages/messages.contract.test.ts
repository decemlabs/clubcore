/**
 * Contract test: staff inbox real backend JSON × FE Zod StaffInboxSchema (Phase 117 Plan 02).
 *
 * Loads the captured ASGITransport response (GET /api/v1/messages/threads)
 * from the backend capture test and parses it with the REAL runtime schema that
 * the useThreads() hook uses.
 *
 * StaffInboxSchema is exported from api.ts (Task 2) so this test uses
 * the identical schema instance that runs in production — not a copy.
 *
 * Failure = backend serializer changed a field name (e.g. staff_unread_count vs staffUnreadCount)
 * without a matching FE Zod update.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { StaffInboxSchema } from './api'

const captured = JSON.parse(
  readFileSync(join(__dirname, 'capture/threads-list-response.json'), 'utf-8'),
) as unknown

describe('messages contract — real backend JSON × FE Zod schema', () => {
  it('parses captured staff inbox response with StaffInboxSchema', () => {
    expect(() => StaffInboxSchema.parse(captured)).not.toThrow()
    const result = StaffInboxSchema.parse(captured).data
    expect(Array.isArray(result.items)).toBe(true)
    expect(typeof result.total).toBe('number')
    // At least one thread exists (the seeded "Иван Захватов" thread).
    expect(result.items.length).toBeGreaterThan(0)
    const thread = result.items[0]
    expect(typeof thread?.id).toBe('string')
    expect(typeof thread?.clientId).toBe('string')
    expect(typeof thread?.staffUnreadCount).toBe('number')
  })
})
