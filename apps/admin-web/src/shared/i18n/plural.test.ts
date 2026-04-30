import { describe, expect, it } from 'vitest'
import { plural } from './plural'

const forms = { one: 'клиент', few: 'клиента', many: 'клиентов' }

describe('plural() — Russian 3-form', () => {
  it('selects "one" for 1, 21, 101', () => {
    expect(plural(1, forms)).toBe('клиент')
    expect(plural(21, forms)).toBe('клиент')
    expect(plural(101, forms)).toBe('клиент')
  })

  it('selects "few" for 2..4, 22..24', () => {
    for (const n of [2, 3, 4, 22, 23, 24]) {
      expect(plural(n, forms)).toBe('клиента')
    }
  })

  it('selects "many" for 0, 5..20, 11..14, 25', () => {
    for (const n of [0, 5, 11, 12, 13, 14, 20, 25]) {
      expect(plural(n, forms)).toBe('клиентов')
    }
  })
})
