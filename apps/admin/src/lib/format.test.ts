import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';
import { pluralRu, formatInt, formatRub, formatKopecks, formatTime, formatRelativeRu, mskTodayISO, mskDaysAgoISO } from './format';

/**
 * Нормализует разделители групп разрядов:
 *  U+00A0 (NBSP) и U+202F (NARROW NBSP) -> обычный пробел.
 * Не трогает \s в целом — только эти два кода.
 */
function normalizeNbsp(s: string): string {
  // Replace U+00A0 (NBSP) and U+202F (NARROW NBSP) with a regular space.
  // Using String.fromCharCode avoids literal irregular-whitespace chars in source.
  const nbsp = String.fromCharCode(0xa0);
  const nnbsp = String.fromCharCode(0x202f);
  return s.split(nbsp).join(' ').split(nnbsp).join(' ');
}

describe('pluralRu', () => {
  const forms: [string, string, string] = ['клиент', 'клиента', 'клиентов'];

  describe('форма «один»', () => {
    it('1 → клиент', () => expect(pluralRu(1, forms)).toBe('клиент'));
    it('21 → клиент', () => expect(pluralRu(21, forms)).toBe('клиент'));
    it('101 → клиент', () => expect(pluralRu(101, forms)).toBe('клиент'));
  });

  describe('форма «два-четыре»', () => {
    it('2 → клиента', () => expect(pluralRu(2, forms)).toBe('клиента'));
    it('3 → клиента', () => expect(pluralRu(3, forms)).toBe('клиента'));
    it('4 → клиента', () => expect(pluralRu(4, forms)).toBe('клиента'));
    it('22 → клиента', () => expect(pluralRu(22, forms)).toBe('клиента'));
  });

  describe('форма «пять»', () => {
    it('0 → клиентов', () => expect(pluralRu(0, forms)).toBe('клиентов'));
    it('5 → клиентов', () => expect(pluralRu(5, forms)).toBe('клиентов'));
    it('11 → клиентов (исключение: 11 mod 10 === 1, но 11 mod 100 === 11)', () =>
      expect(pluralRu(11, forms)).toBe('клиентов'));
    it('12 → клиентов', () => expect(pluralRu(12, forms)).toBe('клиентов'));
    it('14 → клиентов', () => expect(pluralRu(14, forms)).toBe('клиентов'));
    it('111 → клиентов', () => expect(pluralRu(111, forms)).toBe('клиентов'));
    it('112 → клиентов', () => expect(pluralRu(112, forms)).toBe('клиентов'));
  });
});

describe('formatInt', () => {
  it('1234567 → "1 234 567" (нормализованные NBSP)', () => {
    const result = normalizeNbsp(formatInt(1234567));
    expect(result).toBe('1 234 567');
  });
});

describe('formatRub', () => {
  it('содержит цифры и знак рубля', () => {
    const result = normalizeNbsp(formatRub(5000));
    expect(result).toContain('5');
    expect(result).toContain('₽');
  });

  it('нормализованный результат для 1234 содержит "1 234"', () => {
    const result = normalizeNbsp(formatRub(1234));
    expect(result).toContain('1 234');
  });
});

describe('formatKopecks', () => {
  it('делит копейки на 100 перед форматированием (500000 коп. → «5 000 ₽»)', () => {
    const result = normalizeNbsp(formatKopecks(500000));
    expect(result).toContain('5 000');
    expect(result).toContain('₽');
  });

  it('не равно formatRub от тех же копеек (нет 100× ошибки)', () => {
    expect(normalizeNbsp(formatKopecks(500000))).not.toEqual(normalizeNbsp(formatRub(500000)));
  });
});

describe('formatTime', () => {
  it('9:05 → "09:05" (ноль перед часом)', () => {
    const d = new Date(2026, 5, 12, 9, 5);
    expect(formatTime(d)).toBe('09:05');
  });

  it('14:30 → "14:30"', () => {
    const d = new Date(2026, 5, 12, 14, 30);
    expect(formatTime(d)).toBe('14:30');
  });
});

describe('formatRelativeRu (с фиктивным временем)', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('дата 2 часа назад → содержит "назад"', () => {
    const now = new Date(2026, 5, 12, 12, 0, 0);
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const twoHoursAgo = new Date(2026, 5, 12, 10, 0, 0);
    const result = formatRelativeRu(twoHoursAgo);
    expect(result).toMatch(/назад/);
  });
});

describe('mskTodayISO / mskDaysAgoISO (MSK-date helpers, CR-02)', () => {
  // These tests pin the system clock to a specific UTC time and assert that
  // the returned date reflects the Moscow calendar day (UTC+3), not the UTC day.

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('mskTodayISO — в 01:30 UTC (04:30 МСК) возвращает МОСКОВСКУЮ дату, не UTC', () => {
    // 2026-06-13 01:30 UTC = 2026-06-13 04:30 MSK → MSK date is 2026-06-13
    // UTC date would also be 2026-06-13, so test the critical window:
    // 2026-06-12 23:00 UTC = 2026-06-13 02:00 MSK → MSK is June 13, UTC is June 12
    vi.setSystemTime(new Date('2026-06-12T23:00:00.000Z'))
    const result = mskTodayISO()
    expect(result).toBe('2026-06-13') // MSK date, not UTC '2026-06-12'
  })

  it('mskTodayISO — в 22:00 UTC (01:00 МСК следующего дня) возвращает правильную MSK дату', () => {
    // 2026-06-12 22:00 UTC = 2026-06-13 01:00 MSK → MSK date is 2026-06-13
    vi.setSystemTime(new Date('2026-06-12T22:00:00.000Z'))
    const result = mskTodayISO()
    expect(result).toBe('2026-06-13')
  })

  it('mskTodayISO — формат YYYY-MM-DD', () => {
    vi.setSystemTime(new Date('2026-06-13T10:00:00.000Z'))
    const result = mskTodayISO()
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('mskDaysAgoISO(0) === mskTodayISO()', () => {
    vi.setSystemTime(new Date('2026-06-13T10:00:00.000Z'))
    expect(mskDaysAgoISO(0)).toBe(mskTodayISO())
  })

  it('mskDaysAgoISO(29) возвращает дату 29 дней назад по МСК', () => {
    // 2026-06-13 13:00 MSK → 29 days ago = 2026-05-15
    vi.setSystemTime(new Date('2026-06-13T10:00:00.000Z'))
    const result = mskDaysAgoISO(29)
    expect(result).toBe('2026-05-15')
  })
});
