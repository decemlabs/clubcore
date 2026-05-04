import { describe, it, expect } from 'vitest'
import type { components } from '@sportzal/api-client'
import {
  responseToClient,
  createInputToRequest,
  updateInputToRequest,
} from './_clientsAdapter'
import type { ClientCreateInput, ClientUpdateInput } from '@/shared/api/contracts/clients'

type ClientResponse = components['schemas']['ClientResponse']

function baseResponse(overrides: Partial<ClientResponse> = {}): ClientResponse {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    lastName: 'Иванов',
    firstName: 'Пётр',
    middleName: null,
    phone: '+71112223344',
    email: null,
    birthday: null,
    notes: null,
    createdAt: '2024-01-15T10:00:00Z',
    createdByUserId: '22222222-2222-4222-8222-222222222222',
    tags: [],
    updatedAt: '2024-01-15T10:00:00Z',
    ...overrides,
  }
}

describe('responseToClient', () => {
  it('composes fullName as "lastName firstName" when middleName is null', () => {
    const r = baseResponse({ lastName: 'Иванов', firstName: 'Пётр', middleName: null })
    const c = responseToClient(r)
    expect(c.fullName).toBe('Иванов Пётр')
    expect(c.fullName.endsWith(' ')).toBe(false)
  })

  it('composes fullName as "lastName firstName middleName" when middleName is present', () => {
    const r = baseResponse({ lastName: 'Иванов', firstName: 'Пётр', middleName: 'Иван' })
    const c = responseToClient(r)
    expect(c.fullName).toBe('Иванов Пётр Иван')
  })

  it('drops middleName="" (empty string) from fullName', () => {
    const r = baseResponse({ lastName: 'Иванов', firstName: 'Пётр', middleName: '' })
    const c = responseToClient(r)
    expect(c.fullName).toBe('Иванов Пётр')
  })

  it('trims pathological whitespace-only fullName parts', () => {
    const r = baseResponse({ lastName: ' ', firstName: 'Пётр', middleName: null })
    const c = responseToClient(r)
    // lastName=' ' is filter(Boolean)-truthy but trim() collapses it
    expect(c.fullName).toBe('Пётр')
  })

  it('maps birthday=null to birthDate=undefined', () => {
    const r = baseResponse({ birthday: null })
    const c = responseToClient(r)
    expect(c.birthDate).toBeUndefined()
  })

  it('maps birthday="1990-04-12" to birthDate="1990-04-12"', () => {
    const r = baseResponse({ birthday: '1990-04-12' })
    const c = responseToClient(r)
    expect(c.birthDate).toBe('1990-04-12')
  })

  it('maps birthday="" (empty string) to birthDate=undefined', () => {
    const r = baseResponse({ birthday: '' })
    const c = responseToClient(r)
    expect(c.birthDate).toBeUndefined()
  })

  it('maps email=null to email=undefined', () => {
    const r = baseResponse({ email: null })
    const c = responseToClient(r)
    expect(c.email).toBeUndefined()
  })

  it('preserves email when present', () => {
    const r = baseResponse({ email: 'a@b.ru' })
    const c = responseToClient(r)
    expect(c.email).toBe('a@b.ru')
  })

  it('maps notes=null to notes=undefined', () => {
    const r = baseResponse({ notes: null })
    const c = responseToClient(r)
    expect(c.notes).toBeUndefined()
  })

  it('passes through phone, id, createdAt verbatim', () => {
    const r = baseResponse({
      id: '33333333-3333-4333-8333-333333333333',
      phone: '+79998887766',
      createdAt: '2025-06-01T12:34:56Z',
    })
    const c = responseToClient(r)
    expect(c.id).toBe('33333333-3333-4333-8333-333333333333')
    expect(c.phone).toBe('+79998887766')
    expect(c.createdAt).toBe('2025-06-01T12:34:56Z')
  })

  it('silently ignores backend-only fields (gender, tags, emergencyContact, telegramUserId, createdByUserId, updatedAt)', () => {
    const r: ClientResponse = baseResponse({
      gender: 'male',
      tags: ['vip', 'morning'],
      emergencyContact: { name: 'Мама', phone: '+71110001122', relation: 'мать' },
      telegramUserId: 12345,
    })
    const c = responseToClient(r) as unknown as Record<string, unknown>
    expect('gender' in c).toBe(false)
    expect('tags' in c).toBe(false)
    expect('emergencyContact' in c).toBe(false)
    expect('telegramUserId' in c).toBe(false)
    expect('createdByUserId' in c).toBe(false)
    expect('updatedAt' in c).toBe(false)
  })

  it('does not set deletedAt (backend never returns soft-deleted rows)', () => {
    const r = baseResponse()
    const c = responseToClient(r) as unknown as Record<string, unknown>
    expect('deletedAt' in c).toBe(false)
  })
})

describe('createInputToRequest', () => {
  it('emits all 7 keys when full input is provided, with key "birthday" not "birthDate"', () => {
    const input: ClientCreateInput = {
      lastName: 'Иванов',
      firstName: 'Пётр',
      middleName: 'Иван',
      phone: '+71112223344',
      email: 'a@b.ru',
      birthDate: '1990-04-12',
      notes: 'VIP',
    }
    const out = createInputToRequest(input) as Record<string, unknown>
    expect(out).toEqual({
      lastName: 'Иванов',
      firstName: 'Пётр',
      middleName: 'Иван',
      phone: '+71112223344',
      email: 'a@b.ru',
      birthday: '1990-04-12',
      notes: 'VIP',
    })
    expect('birthDate' in out).toBe(false)
  })

  it('emits only required keys {lastName, firstName, phone} when optional fields are absent', () => {
    const input: ClientCreateInput = {
      lastName: 'Иванов',
      firstName: 'Пётр',
      phone: '+71112223344',
    }
    const out = createInputToRequest(input) as Record<string, unknown>
    expect(out).toEqual({
      lastName: 'Иванов',
      firstName: 'Пётр',
      phone: '+71112223344',
    })
    expect(Object.keys(out)).toHaveLength(3)
  })

  it('omits optional fields whose value is the empty string', () => {
    const input: ClientCreateInput = {
      lastName: 'A',
      firstName: 'B',
      phone: '+71112223344',
      email: '',
      birthDate: '',
      middleName: '',
      notes: '',
    }
    const out = createInputToRequest(input)
    expect(out).toEqual({ lastName: 'A', firstName: 'B', phone: '+71112223344' })
  })

  it('never produces the substring "birthDate" in JSON output', () => {
    const input: ClientCreateInput = {
      lastName: 'A',
      firstName: 'B',
      phone: '+71112223344',
      birthDate: '1991-02-03',
    }
    const out = createInputToRequest(input)
    expect(JSON.stringify(out)).not.toContain('"birthDate"')
    expect(JSON.stringify(out)).toContain('"birthday"')
  })

  it('never sends null for any field (only omits)', () => {
    const input: ClientCreateInput = {
      lastName: 'A',
      firstName: 'B',
      phone: '+71112223344',
      email: '',
      birthDate: '',
      notes: '',
      middleName: '',
    }
    const out = createInputToRequest(input)
    expect(JSON.stringify(out)).not.toContain('null')
  })
})

describe('updateInputToRequest', () => {
  it('returns {} for empty input', () => {
    const out = updateInputToRequest({})
    expect(out).toEqual({})
  })

  it('returns only the fields that were present', () => {
    const input: ClientUpdateInput = { firstName: 'Сергей' }
    const out = updateInputToRequest(input)
    expect(out).toEqual({ firstName: 'Сергей' })
  })

  it('renames birthDate → birthday and never emits a "birthDate" key', () => {
    const input: ClientUpdateInput = { birthDate: '1991-02-03' }
    const out = updateInputToRequest(input) as Record<string, unknown>
    expect(out).toEqual({ birthday: '1991-02-03' })
    expect('birthDate' in out).toBe(false)
  })

  it('omits empty-string optional fields (not sent as null)', () => {
    const input: ClientUpdateInput = { email: '' }
    const out = updateInputToRequest(input)
    expect(out).toEqual({})
    expect(JSON.stringify(out)).not.toContain('null')
  })

  it('omits empty-string birthDate per Phase 8 D-01 (omit, do NOT send null)', () => {
    const input: ClientUpdateInput = { birthDate: '' }
    const out = updateInputToRequest(input)
    expect(out).toEqual({})
  })

  it('omits empty-string middleName and notes', () => {
    const input: ClientUpdateInput = { middleName: '', notes: '' }
    const out = updateInputToRequest(input)
    expect(out).toEqual({})
  })

  it('omits required-on-create keys (lastName/firstName/phone) when absent (Partial semantics)', () => {
    const input: ClientUpdateInput = { notes: 'updated' }
    const out = updateInputToRequest(input) as Record<string, unknown>
    expect(out).toEqual({ notes: 'updated' })
    expect('lastName' in out).toBe(false)
    expect('firstName' in out).toBe(false)
    expect('phone' in out).toBe(false)
  })

  it('passes through non-empty lastName/firstName/phone when provided', () => {
    const input: ClientUpdateInput = {
      lastName: 'Петров',
      firstName: 'Иван',
      phone: '+79998887766',
    }
    const out = updateInputToRequest(input)
    expect(out).toEqual({
      lastName: 'Петров',
      firstName: 'Иван',
      phone: '+79998887766',
    })
  })
})
