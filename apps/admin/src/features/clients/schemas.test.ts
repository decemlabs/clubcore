/**
 * Clients domain zod contract tests (Phase 101 CLI-01, CLI-03).
 *
 * Pure zod parse assertions — no network, no React.
 * Validates that schemas correctly accept and reject client wire shapes.
 */
import { describe, it, expect } from 'vitest'
import {
  ClientSchema,
  ClientsListResponseSchema,
  ClientCreateSchema,
  ClientUpdateSchema,
} from './schemas'
import { filterToQuery } from './query'

const validClient = {
  id: '00000000-0000-0000-0000-000000000001',
  lastName: 'Иванова',
  firstName: 'Мария',
  middleName: null,
  phone: '+79991234567',
  email: null,
  birthday: null,
  gender: null,
  tags: ['vip', 'morning'],
  notes: null,
  telegramUserId: null,
  createdAt: '2024-01-15T10:00:00Z',
}

// ---------------------------------------------------------------------------
// ClientsListResponseSchema
// ---------------------------------------------------------------------------

describe('ClientsListResponseSchema', () => {
  it('parses a valid list response and exposes .data.items typed as ClientData', () => {
    const result = ClientsListResponseSchema.parse({
      data: {
        items: [validClient],
        total: 1,
        page: 1,
        pageSize: 25,
      },
    })
    expect(result.data.items[0]?.id).toBe('00000000-0000-0000-0000-000000000001')
    expect(result.data.total).toBe(1)
    expect(result.data.page).toBe(1)
    expect(result.data.pageSize).toBe(25)
  })

  it('rejects a response missing total', () => {
    expect(() =>
      ClientsListResponseSchema.parse({
        data: { items: [validClient], page: 1, pageSize: 25 },
      }),
    ).toThrow()
  })

  it('parses empty items list', () => {
    const result = ClientsListResponseSchema.parse({
      data: { items: [], total: 0, page: 1, pageSize: 25 },
    })
    expect(result.data.items).toHaveLength(0)
    expect(result.data.total).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// ClientSchema
// ---------------------------------------------------------------------------

describe('ClientSchema', () => {
  it('parses a minimal client (nullable fields absent)', () => {
    const result = ClientSchema.parse(validClient)
    expect(result.lastName).toBe('Иванова')
    expect(result.firstName).toBe('Мария')
  })

  it('accepts optional fields when provided', () => {
    const rich = {
      ...validClient,
      email: 'maria@example.ru',
      birthday: '1990-03-14',
      gender: 'female' as const,
      tags: ['yoga'],
      notes: 'Тренируется по утрам',
      telegramUserId: '123456789',
    }
    const result = ClientSchema.parse(rich)
    expect(result.email).toBe('maria@example.ru')
    expect(result.gender).toBe('female')
    expect(result.tags).toEqual(['yoga'])
  })

  it('rejects an unknown gender enum value', () => {
    expect(() =>
      ClientSchema.parse({ ...validClient, gender: 'other' }),
    ).toThrow()
  })
})

// ---------------------------------------------------------------------------
// ClientCreateSchema — phone
// ---------------------------------------------------------------------------

describe('ClientCreateSchema — phone validation', () => {
  it('rejects a phone starting with 8 (non-E.164)', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '89991234567',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.phone?.[0]).toContain('+7XXXXXXXXXX')
    }
  })

  it('accepts a valid +7 phone number', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Иванова',
      firstName: 'Мария',
      phone: '+79991234567',
    })
    expect(result.success).toBe(true)
  })

  it('rejects an empty phone', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '',
    })
    expect(result.success).toBe(false)
  })

  it('accepts international numbers matching E.164', () => {
    // +1 (US)
    const result = ClientCreateSchema.safeParse({
      lastName: 'Смит',
      firstName: 'Джон',
      phone: '+12125550123',
    })
    expect(result.success).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// ClientCreateSchema — tags
// ---------------------------------------------------------------------------

describe('ClientCreateSchema — tags validation', () => {
  it('rejects a tag longer than 32 characters', () => {
    const longTag = 'a'.repeat(33)
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      tags: [longTag],
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.tags).toBeDefined()
    }
  })

  it('rejects a 17th tag (max 16 tags)', () => {
    const tags = Array.from({ length: 17 }, (_, i) => `tag${i}`)
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      tags,
    })
    expect(result.success).toBe(false)
  })

  it('accepts exactly 16 tags', () => {
    const tags = Array.from({ length: 16 }, (_, i) => `tag${i}`)
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      tags,
    })
    expect(result.success).toBe(true)
  })

  it('accepts valid cyrillic and latin tags', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      tags: ['vip', 'утро', 'tag-name', 'tag_2'],
    })
    expect(result.success).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// ClientCreateSchema — notes
// ---------------------------------------------------------------------------

describe('ClientCreateSchema — notes validation', () => {
  it('rejects notes longer than 4096 characters', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      notes: 'a'.repeat(4097),
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.notes?.[0]).toContain('4096')
    }
  })

  it('accepts notes exactly at 4096 characters', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      notes: 'a'.repeat(4096),
    })
    expect(result.success).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// ClientCreateSchema — email
// ---------------------------------------------------------------------------

describe('ClientCreateSchema — email validation', () => {
  it('accepts empty string email (cleared field)', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      email: '',
    })
    expect(result.success).toBe(true)
  })

  it('accepts a valid email', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      email: 'user@example.ru',
    })
    expect(result.success).toBe(true)
  })

  it('rejects an invalid email format (non-empty)', () => {
    const result = ClientCreateSchema.safeParse({
      lastName: 'Тест',
      firstName: 'Тест',
      phone: '+79991234567',
      email: 'notanemail',
    })
    expect(result.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// ClientUpdateSchema — partial
// ---------------------------------------------------------------------------

describe('ClientUpdateSchema', () => {
  it('accepts an empty object (all fields optional)', () => {
    const result = ClientUpdateSchema.safeParse({})
    expect(result.success).toBe(true)
  })

  it('accepts a partial update with only lastName', () => {
    const result = ClientUpdateSchema.safeParse({ lastName: 'Новая' })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.lastName).toBe('Новая')
      expect(result.data.firstName).toBeUndefined()
    }
  })

  it('still validates phone when provided', () => {
    const result = ClientUpdateSchema.safeParse({ phone: '8999' })
    expect(result.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// filterToQuery
// ---------------------------------------------------------------------------

describe('filterToQuery', () => {
  it('omits q when length < 2', () => {
    const q = filterToQuery({ q: 'а' })
    expect('q' in q).toBe(false)
  })

  it('includes q when length >= 2', () => {
    const q = filterToQuery({ q: 'Ив' })
    expect(q['q']).toBe('Ив')
  })

  it('maps sort recent:desc to created_at_desc', () => {
    const q = filterToQuery({ sort: 'recent:desc' })
    expect(q['sort']).toBe('created_at_desc')
  })

  it('maps sort name:asc to last_name_asc', () => {
    const q = filterToQuery({ sort: 'name:asc' })
    expect(q['sort']).toBe('last_name_asc')
  })

  it('omits undefined filters', () => {
    const q = filterToQuery({ page: 1, pageSize: 25 })
    expect(Object.keys(q)).toEqual(['page', 'pageSize'])
  })

  it('includes hasTelegram boolean when provided', () => {
    const q = filterToQuery({ hasTelegram: true })
    expect(q['hasTelegram']).toBe(true)
  })
})
