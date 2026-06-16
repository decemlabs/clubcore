import { describe, expect, it } from 'vitest';
import type { Client } from './types';
import { compare } from './sort';

/**
 * Минимальная фикстура Client: заполняем только поля, которые трогает compare.
 * Остальные обязательные поля задаём реалистичными заглушками.
 */
function makeClient(overrides: {
  id?: string;
  name?: string;
  visitsMonth?: number;
  lastVisitRank?: number;
  expiryDaysLeft?: number | null;
}): Client {
  const {
    id = 'c1',
    name = 'Тест',
    visitsMonth = 0,
    lastVisitRank = 0,
    expiryDaysLeft = 0,
  } = overrides;
  return {
    id,
    initials: name.slice(0, 2),
    color: '#aaa',
    name,
    phone: '+7 000 000-00-00',
    tenure: '1 мес',
    status: 'active',
    plan: {
      name: 'Месячный',
      type: 'monthly',
      fillPct: 50,
      tone: 'normal',
      daysLabel: '15 / 30 дней',
    },
    expiry:
      expiryDaysLeft == null
        ? null
        : {
            top: '1 авг',
            sub: 'через 1 день',
            urgency: 'normal',
            daysLeft: expiryDaysLeft,
          },
    visits: {
      value: String(visitsMonth),
      strong: visitsMonth > 0,
      month: visitsMonth,
    },
    trainer: null,
    lastVisit: {
      top: 'Сегодня',
      sub: '10:00',
      rank: lastVisitRank,
    },
  };
}

describe('compare: name', () => {
  it('asc: Анна < Борис', () => {
    const a = makeClient({ name: 'Анна' });
    const b = makeClient({ name: 'Борис' });
    expect(compare(a, b, { key: 'name', dir: 'asc' })).toBeLessThan(0);
  });

  it('desc: Борис > Анна (знак меняется)', () => {
    const a = makeClient({ name: 'Анна' });
    const b = makeClient({ name: 'Борис' });
    expect(compare(a, b, { key: 'name', dir: 'desc' })).toBeGreaterThan(0);
  });

  it('asc: одинаковые имена → 0', () => {
    const a = makeClient({ name: 'Анна' });
    const b = makeClient({ name: 'Анна' });
    expect(compare(a, b, { key: 'name', dir: 'asc' })).toBe(0);
  });

  it('asc: ё/е не бросает исключение', () => {
    const a = makeClient({ name: 'Ёлка' });
    const b = makeClient({ name: 'Елена' });
    expect(() => compare(a, b, { key: 'name', dir: 'asc' })).not.toThrow();
  });
});

describe('compare: visits', () => {
  it('asc: 3 визита < 10 визитов', () => {
    const a = makeClient({ visitsMonth: 3 });
    const b = makeClient({ visitsMonth: 10 });
    expect(compare(a, b, { key: 'visits', dir: 'asc' })).toBeLessThan(0);
  });

  it('desc: 10 визитов > 3 визита (знак меняется)', () => {
    const a = makeClient({ visitsMonth: 3 });
    const b = makeClient({ visitsMonth: 10 });
    expect(compare(a, b, { key: 'visits', dir: 'desc' })).toBeGreaterThan(0);
  });

  it('asc: равные визиты → 0', () => {
    const a = makeClient({ visitsMonth: 5 });
    const b = makeClient({ visitsMonth: 5 });
    expect(compare(a, b, { key: 'visits', dir: 'asc' })).toBe(0);
  });
});

describe('compare: expires', () => {
  it('оба null → 0 (лиды равны)', () => {
    const a = makeClient({ expiryDaysLeft: null });
    const b = makeClient({ expiryDaysLeft: null });
    expect(compare(a, b, { key: 'expires', dir: 'asc' })).toBe(0);
  });

  it('a=null → 1 при asc (лид в конце)', () => {
    const a = makeClient({ expiryDaysLeft: null });
    const b = makeClient({ expiryDaysLeft: 5 });
    expect(compare(a, b, { key: 'expires', dir: 'asc' })).toBe(1);
  });

  it('a=null → 1 при desc (лид всегда в конце)', () => {
    const a = makeClient({ expiryDaysLeft: null });
    const b = makeClient({ expiryDaysLeft: 5 });
    expect(compare(a, b, { key: 'expires', dir: 'desc' })).toBe(1);
  });

  it('b=null → -1 при asc (b-лид в конце)', () => {
    const a = makeClient({ expiryDaysLeft: 5 });
    const b = makeClient({ expiryDaysLeft: null });
    expect(compare(a, b, { key: 'expires', dir: 'asc' })).toBe(-1);
  });

  it('b=null → -1 при desc (b-лид всегда в конце)', () => {
    const a = makeClient({ expiryDaysLeft: 5 });
    const b = makeClient({ expiryDaysLeft: null });
    expect(compare(a, b, { key: 'expires', dir: 'desc' })).toBe(-1);
  });

  it('asc: daysLeft 3 < daysLeft 10', () => {
    const a = makeClient({ expiryDaysLeft: 3 });
    const b = makeClient({ expiryDaysLeft: 10 });
    expect(compare(a, b, { key: 'expires', dir: 'asc' })).toBeLessThan(0);
  });

  it('desc: daysLeft 3 > daysLeft 10 (знак меняется)', () => {
    const a = makeClient({ expiryDaysLeft: 3 });
    const b = makeClient({ expiryDaysLeft: 10 });
    expect(compare(a, b, { key: 'expires', dir: 'desc' })).toBeGreaterThan(0);
  });
});
