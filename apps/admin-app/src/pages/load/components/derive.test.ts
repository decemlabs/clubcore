import { describe, expect, it } from 'vitest'
import { deriveDayOfWeek, derivePeakHour, deriveFrequency } from './derive'
import type { VisitsReportDailyBucket, VisitsReportHourlyBucket } from '@/features/reports/schemas'

/**
 * Минимальные фабрики фикстур — заполняем только поля, которые трогают функции.
 */
function makeDaily(entries: { date: string; count: number }[]): VisitsReportDailyBucket[] {
  return entries.map(({ date, count }) => ({ date, count }))
}

function makeHourly(counts: number[]): VisitsReportHourlyBucket[] {
  return counts.map((count, hour) => ({ hour, count }))
}

describe('deriveDayOfWeek', () => {
  it('пустой массив → 7 бакетов, avg=0, NaN не появляется', () => {
    const result = deriveDayOfWeek([])
    expect(result).toHaveLength(7)
    for (const bucket of result) {
      expect(bucket.total).toBe(0)
      expect(bucket.daysWithData).toBe(0)
      expect(bucket.avgPerWeekday).toBe(0)
      expect(Number.isNaN(bucket.avgPerWeekday)).toBe(false)
    }
  })

  it('один день → daysWithData=1, total=count, avg=count', () => {
    const result = deriveDayOfWeek(makeDaily([{ date: '2024-01-15', count: 10 }]))
    // 2024-01-15 is a Monday → weekday index 0 (Пн)
    const monday = result[0]!
    expect(monday.daysWithData).toBe(1)
    expect(monday.total).toBe(10)
    expect(monday.avgPerWeekday).toBe(10)
    // All other days remain zero
    for (const bucket of result.slice(1)) {
      expect(bucket.total).toBe(0)
      expect(bucket.avgPerWeekday).toBe(0)
    }
  })

  it('MSK weekday: 2024-01-15 = Пн (weekday=0)', () => {
    const result = deriveDayOfWeek(makeDaily([{ date: '2024-01-15', count: 5 }]))
    expect(result[0]!.weekday).toBe(0)
    expect(result[0]!.label).toBe('Пн')
    expect(result[0]!.total).toBe(5)
  })

  it('возвращает 7 бакетов с корректными метками Пн…Вс', () => {
    const result = deriveDayOfWeek([])
    const labels = result.map((b) => b.label)
    expect(labels).toEqual(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'])
  })

  it('несколько дней одного weekday → avg усредняется корректно', () => {
    // 2024-01-15 = Пн (count=10), 2024-01-22 = Пн (count=20)
    const result = deriveDayOfWeek(
      makeDaily([
        { date: '2024-01-15', count: 10 },
        { date: '2024-01-22', count: 20 },
      ]),
    )
    const monday = result[0]!
    expect(monday.daysWithData).toBe(2)
    expect(monday.total).toBe(30)
    expect(monday.avgPerWeekday).toBe(15)
  })
})

describe('derivePeakHour', () => {
  it('все нули → null', () => {
    const result = derivePeakHour(makeHourly([0, 0, 0]))
    expect(result).toBeNull()
  })

  it('пустой массив → null', () => {
    const result = derivePeakHour([])
    expect(result).toBeNull()
  })

  it('единственный ненулевой → возвращает его час', () => {
    const counts = Array.from({ length: 24 }, () => 0)
    counts[14] = 42
    const result = derivePeakHour(makeHourly(counts))
    expect(result).not.toBeNull()
    expect(result!.hour).toBe(14)
    expect(result!.count).toBe(42)
  })

  it('ничья → ранний час побеждает', () => {
    const counts = Array.from({ length: 24 }, () => 0)
    counts[9] = 15
    counts[18] = 15
    const result = derivePeakHour(makeHourly(counts))
    expect(result).not.toBeNull()
    expect(result!.hour).toBe(9)
    expect(result!.count).toBe(15)
  })
})

describe('deriveFrequency', () => {
  it('пустой массив → все 6 бакетов count=0', () => {
    const result = deriveFrequency([])
    expect(result).toHaveLength(6)
    for (const bucket of result) {
      expect(bucket.count).toBe(0)
    }
  })

  it('бакеты имеют ожидаемые метки с en-dash', () => {
    const result = deriveFrequency([])
    const labels = result.map((b) => b.label)
    expect(labels).toEqual(['0–4', '5–9', '10–14', '15–19', '20–24', '25+'])
  })

  it('день count=3 попадает в бакет 0–4', () => {
    const result = deriveFrequency(makeDaily([{ date: '2024-01-15', count: 3 }]))
    expect(result[0]!.label).toBe('0–4')
    expect(result[0]!.count).toBe(1)
    // остальные нули
    for (const bucket of result.slice(1)) {
      expect(bucket.count).toBe(0)
    }
  })

  it('день count=25 попадает в бакет 25+', () => {
    const result = deriveFrequency(makeDaily([{ date: '2024-01-15', count: 25 }]))
    expect(result[5]!.label).toBe('25+')
    expect(result[5]!.count).toBe(1)
  })

  it('день count=99 попадает в бакет 25+', () => {
    const result = deriveFrequency(makeDaily([{ date: '2024-01-15', count: 99 }]))
    expect(result[5]!.label).toBe('25+')
    expect(result[5]!.count).toBe(1)
  })

  it('count=4 → бакет 0–4, count=5 → бакет 5–9 (граница)', () => {
    const result = deriveFrequency(
      makeDaily([
        { date: '2024-01-15', count: 4 },
        { date: '2024-01-16', count: 5 },
      ]),
    )
    expect(result[0]!.count).toBe(1) // 0–4
    expect(result[1]!.count).toBe(1) // 5–9
  })
})
