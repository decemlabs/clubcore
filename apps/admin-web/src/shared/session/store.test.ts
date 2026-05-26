import { describe, expect, it, beforeEach } from 'vitest'
import { SESSION_STORAGE_KEY, useSessionStore } from './store'

describe('session store', () => {
  beforeEach(() => {
    // setup.ts already best-effort clears localStorage; just reset store state
    useSessionStore.setState({ role: 'owner' })
  })

  it('uses the versioned persist key', () => {
    expect(SESSION_STORAGE_KEY).toBe('clubcore:session:v2')
  })

  it('defaults role to owner', () => {
    expect(useSessionStore.getState().role).toBe('owner')
  })

  it('setRole updates state and persists only `role`', async () => {
    useSessionStore.getState().setRole('reception')
    expect(useSessionStore.getState().role).toBe('reception')

    // flush persist write
    await Promise.resolve()
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY)
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw as string) as { state: Record<string, unknown> }
    expect(parsed.state).toEqual({ role: 'reception' })
    // setRole must NOT be persisted
    expect(parsed.state).not.toHaveProperty('setRole')
  })
})
