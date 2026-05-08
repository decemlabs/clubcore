import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { memberships } from './memberships'
import { resetDB, loadDB, saveDB } from './_db'
import { todayMSK } from '@/shared/i18n/date'
import type { Membership } from '@/entities/membership'

/**
 * DEBT-02 (Phase 24, plan 24-04) — mock service `?expiring=true&within=N`
 * parity tests.
 *
 * Backend repository applies `Membership.end_date <= today + (within - 1)`
 * inclusive (D-24-12 + PROJECT.md "Key Decisions"). The mock mirrors that
 * predicate (`cutoff = today + (within - 1)`), so a membership whose endDate
 * equals `today + (within - 1)` MUST be included; one at `today + within`
 * MUST be excluded.
 *
 * `query.within ?? 7` is the legacy FE-08 D-2 default — when `within` is
 * omitted, the result set must equal the within=7 result set (non-regression).
 */

function isoOffset(days: number): string {
  const today = new Date(todayMSK())
  today.setUTCDate(today.getUTCDate() + days)
  return today.toISOString().slice(0, 10)
}

function injectMembership(partial: Partial<Membership> & Pick<Membership, 'id' | 'endDate'>) {
  // loadDB returns a freshly-parsed snapshot — must call saveDB to persist
  // back to the versioned localStorage key (`sportzal:mock:v1`).
  const db = loadDB()
  const seed = db.memberships[0]
  if (!seed) throw new Error('mock DB has no memberships seed — cannot fabricate fixture')
  const fixture: Membership = {
    ...seed,
    id: partial.id,
    endDate: partial.endDate,
    status: partial.status ?? 'active',
    startDate: partial.startDate ?? isoOffset(-30),
  }
  db.memberships.push(fixture)
  saveDB(db)
}

describe('mock/memberships.list — DEBT-02 expiring + within parity', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  it('with expiring=true and no `within` defaults to the legacy 7-day window (FE-08 D-2 non-regression)', async () => {
    const omitted = await memberships.list({ page: 1, pageSize: 1000, expiring: true })
    const explicit7 = await memberships.list({
      page: 1,
      pageSize: 1000,
      expiring: true,
      within: 7,
    })
    // Same set, same total — within defaulting must equal explicit 7.
    expect(omitted.total).toBe(explicit7.total)
    expect(new Set(omitted.items.map((m) => m.id))).toEqual(
      new Set(explicit7.items.map((m) => m.id)),
    )
    // Every returned item is active and inside [today, today + 6].
    const todayStr = todayMSK()
    const cutoff = isoOffset(6) // within=7 -> +(7-1)=+6 inclusive
    for (const m of omitted.items) {
      expect(m.status).toBe('active')
      expect(m.endDate >= todayStr).toBe(true)
      expect(m.endDate <= cutoff).toBe(true)
    }
  })

  it('with expiring=true and within=14 includes items at today+13 and excludes items at today+14', async () => {
    const inWindow = 'fixture-debt02-in-window' as Membership['id']
    const outWindow = 'fixture-debt02-out-window' as Membership['id']
    injectMembership({ id: inWindow, endDate: isoOffset(13), status: 'active' })
    injectMembership({ id: outWindow, endDate: isoOffset(14), status: 'active' })

    const got = await memberships.list({
      page: 1,
      pageSize: 1000,
      expiring: true,
      within: 14,
    })
    const ids = new Set(got.items.map((m) => m.id))
    expect(ids.has(inWindow)).toBe(true)
    // Exclusive boundary — today + within is OUT (within=14 -> cap at today+13):
    expect(ids.has(outWindow)).toBe(false)
  })

  it('within=14 result set is a superset of within=7 (wider window cannot have fewer items)', async () => {
    const got14 = await memberships.list({ page: 1, pageSize: 1000, expiring: true, within: 14 })
    const got7 = await memberships.list({ page: 1, pageSize: 1000, expiring: true, within: 7 })
    expect(got14.items.length).toBeGreaterThanOrEqual(got7.items.length)
    const ids14 = new Set(got14.items.map((m) => m.id))
    for (const m of got7.items) {
      expect(ids14.has(m.id)).toBe(true)
    }
  })

  it('with expiring=false ignores `within` (no date predicate added)', async () => {
    const explicit7 = await memberships.list({
      page: 1,
      pageSize: 1000,
      expiring: false,
      within: 7,
    })
    const explicit30 = await memberships.list({
      page: 1,
      pageSize: 1000,
      expiring: false,
      within: 30,
    })
    // `within` is silently ignored when expiring=false — totals must match.
    expect(explicit7.total).toBe(explicit30.total)
  })

  it('with expiring=true forces status=active (non-active rows are excluded even if endDate is in window)', async () => {
    const cancelledInWindow = 'fixture-debt02-cancelled-in-window' as Membership['id']
    const expiredInWindow = 'fixture-debt02-expired-in-window' as Membership['id']
    injectMembership({ id: cancelledInWindow, endDate: isoOffset(2), status: 'cancelled' })
    injectMembership({ id: expiredInWindow, endDate: isoOffset(2), status: 'expired' })

    const got = await memberships.list({ page: 1, pageSize: 1000, expiring: true })
    const ids = new Set(got.items.map((m) => m.id))
    expect(ids.has(cancelledInWindow)).toBe(false)
    expect(ids.has(expiredInWindow)).toBe(false)
    for (const m of got.items) {
      expect(m.status).toBe('active')
    }
  })
})
