import { describe, it, expect } from 'vitest'
import { applyOptimisticUpdate } from './hooks'
import type { Client, ClientId } from '@/entities/client'

const base = {
  id: '11111111-1111-4111-8111-111111111111' as ClientId,
  fullName: 'Иванов Пётр Иван',
  phone: '+79991112233',
  createdAt: '2026-01-01T00:00:00.000Z',
} as Client

describe('applyOptimisticUpdate', () => {
  it('rebuilds fullName when firstName changes (3-token mock parity)', () => {
    const result = applyOptimisticUpdate(base, { firstName: 'Сергей' })
    expect(result.fullName).toBe('Иванов Сергей Иван')
  })

  it('does not throw when current.fullName is undefined', () => {
    const broken = {
      ...base,
      fullName: undefined as unknown as string,
    } as Client
    const run = () => applyOptimisticUpdate(broken, { firstName: 'Сергей', lastName: 'Иванов' })
    expect(run).not.toThrow()
    expect(run().fullName).toBe('Иванов Сергей')
  })

  it('keeps fullName intact when no name field in input', () => {
    const trimmed = { ...base, fullName: 'Иванов Пётр' } as Client
    const result = applyOptimisticUpdate(trimmed, { phone: '+71112223344' })
    expect(result.fullName).toBe('Иванов Пётр')
    expect(result.phone).toBe('+71112223344')
  })

  it('omits empty-string optionals (email)', () => {
    const trimmed = { ...base, fullName: 'Иванов Пётр', email: 'old@example.com' } as Client
    const result = applyOptimisticUpdate(trimmed, { email: '' })
    expect(result.email).toBeUndefined()
  })
})
