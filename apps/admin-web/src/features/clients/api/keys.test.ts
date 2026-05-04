import { describe, it, expect } from 'vitest'
import { clientsKeys } from './keys'
import type { ClientId } from '@/entities/client'

describe('clientsKeys factory', () => {
  it('exposes the root namespace', () => {
    expect(clientsKeys.all).toEqual(['clients'])
  })

  it('builds the lists key under the root namespace', () => {
    expect(clientsKeys.lists()).toEqual(['clients', 'list'])
  })

  it('builds the list key with the filter object as the last segment', () => {
    const key = clientsKeys.list({ q: 'foo', page: 1, pageSize: 20 })
    expect(key).toEqual(['clients', 'list', { q: 'foo', page: 1, pageSize: 20 }])
  })

  it('produces distinct keys for different filters', () => {
    const a = clientsKeys.list({ q: 'a', page: 1, pageSize: 20 })
    const b = clientsKeys.list({ q: 'b', page: 1, pageSize: 20 })
    expect(a).not.toEqual(b)
  })

  it('builds detail keys keyed by ClientId', () => {
    const id = '11111111-1111-4111-8111-111111111111' as ClientId
    expect(clientsKeys.detail(id)).toEqual(['clients', 'detail', id])
  })
})
