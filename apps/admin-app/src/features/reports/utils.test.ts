/**
 * TDD tests for reports domain zero-fill utilities (Phase 103-01).
 * RED phase: written before utils.ts exists.
 */
import { describe, expect, it } from 'vitest';
import { fillHourlyBuckets, fillDailyBuckets, fillRevenueBuckets } from './utils';

describe('fillHourlyBuckets', () => {
  it('returns exactly 24 points for an empty array', () => {
    const result = fillHourlyBuckets([]);
    expect(result).toHaveLength(24);
  });

  it('returns hours 0 through 23 in order', () => {
    const result = fillHourlyBuckets([]);
    expect(result[0]?.hour).toBe(0);
    expect(result[23]?.hour).toBe(23);
  });

  it('zero-fills missing hours (no NaN)', () => {
    const result = fillHourlyBuckets([]);
    for (const bucket of result) {
      expect(bucket.count).toBe(0);
      expect(isNaN(bucket.count)).toBe(false);
    }
  });

  it('preserves data for existing hours', () => {
    const result = fillHourlyBuckets([{ hour: 9, count: 5 }]);
    expect(result).toHaveLength(24);
    expect(result[9]?.count).toBe(5);
  });

  it('zero-fills all other hours when one hour is provided', () => {
    const result = fillHourlyBuckets([{ hour: 9, count: 5 }]);
    for (const bucket of result) {
      if (bucket.hour !== 9) {
        expect(bucket.count).toBe(0);
      }
    }
  });

  it('handles multiple sparse hours correctly', () => {
    const result = fillHourlyBuckets([
      { hour: 0, count: 1 },
      { hour: 12, count: 10 },
      { hour: 23, count: 3 },
    ]);
    expect(result[0]?.count).toBe(1);
    expect(result[12]?.count).toBe(10);
    expect(result[23]?.count).toBe(3);
    expect(result[1]?.count).toBe(0);
  });
});

describe('fillDailyBuckets', () => {
  it('returns a bucket for every day in the range', () => {
    const result = fillDailyBuckets([], '2026-06-10', '2026-06-13');
    expect(result).toHaveLength(4);
  });

  it('zero-fills missing dates (no NaN)', () => {
    const result = fillDailyBuckets([], '2026-06-10', '2026-06-13');
    for (const bucket of result) {
      expect(bucket.count).toBe(0);
      expect(isNaN(bucket.count)).toBe(false);
    }
  });

  it('preserves count for provided date', () => {
    const result = fillDailyBuckets(
      [{ date: '2026-06-12', count: 3 }],
      '2026-06-10',
      '2026-06-13',
    );
    expect(result).toHaveLength(4);
    const jun12 = result.find((b) => b.date === '2026-06-12');
    expect(jun12?.count).toBe(3);
  });

  it('zero-fills other dates when one date has data', () => {
    const result = fillDailyBuckets(
      [{ date: '2026-06-12', count: 3 }],
      '2026-06-10',
      '2026-06-13',
    );
    for (const bucket of result) {
      if (bucket.date !== '2026-06-12') {
        expect(bucket.count).toBe(0);
      }
    }
  });

  it('includes all dates in correct order', () => {
    const result = fillDailyBuckets([], '2026-06-10', '2026-06-13');
    expect(result[0]?.date).toBe('2026-06-10');
    expect(result[1]?.date).toBe('2026-06-11');
    expect(result[2]?.date).toBe('2026-06-12');
    expect(result[3]?.date).toBe('2026-06-13');
  });

  it('handles single-day range', () => {
    const result = fillDailyBuckets([{ date: '2026-06-01', count: 7 }], '2026-06-01', '2026-06-01');
    expect(result).toHaveLength(1);
    expect(result[0]?.count).toBe(7);
  });
});

describe('fillRevenueBuckets', () => {
  const ZERO_METHODS = { cash: 0, online: 0 };
  const ZERO_SUBJECT = { membership: 0, pt_package: 0 };

  it('returns 3 buckets for a 3-day groupBy=day range', () => {
    const result = fillRevenueBuckets([], '2026-06-10', '2026-06-12', 'day');
    expect(result).toHaveLength(3);
  });

  it('zero-fills missing day buckets (no NaN)', () => {
    const result = fillRevenueBuckets([], '2026-06-10', '2026-06-12', 'day');
    for (const bucket of result) {
      expect(bucket.netKopecks).toBe(0);
      expect(isNaN(bucket.netKopecks)).toBe(false);
      expect(bucket.byMethod).toEqual(ZERO_METHODS);
      expect(bucket.bySubjectKind).toEqual(ZERO_SUBJECT);
    }
  });

  it('preserves sparse data for day groupBy', () => {
    const sparse = [
      {
        period: '2026-06-11',
        netKopecks: 5000,
        byMethod: { cash: 3000, online: 2000 },
        bySubjectKind: { membership: 4000, pt_package: 1000 },
      },
    ];
    const result = fillRevenueBuckets(sparse, '2026-06-10', '2026-06-12', 'day');
    const jun11 = result.find((b) => b.period === '2026-06-11');
    expect(jun11?.netKopecks).toBe(5000);
    expect(jun11?.byMethod.cash).toBe(3000);
  });

  it('returns 3 month buckets for Jan–Mar groupBy=month', () => {
    const result = fillRevenueBuckets([], '2026-01-01', '2026-03-31', 'month');
    expect(result).toHaveLength(3);
    expect(result[0]?.period).toBe('2026-01');
    expect(result[1]?.period).toBe('2026-02');
    expect(result[2]?.period).toBe('2026-03');
  });

  it('zero-fills missing month buckets (no NaN)', () => {
    const result = fillRevenueBuckets([], '2026-01-01', '2026-03-31', 'month');
    for (const bucket of result) {
      expect(bucket.netKopecks).toBe(0);
      expect(isNaN(bucket.netKopecks)).toBe(false);
      expect(bucket.byMethod).toEqual(ZERO_METHODS);
      expect(bucket.bySubjectKind).toEqual(ZERO_SUBJECT);
    }
  });

  it('preserves sparse month data', () => {
    const sparse = [
      {
        period: '2026-02',
        netKopecks: 100000,
        byMethod: { cash: 60000, online: 40000 },
        bySubjectKind: { membership: 80000, pt_package: 20000 },
      },
    ];
    const result = fillRevenueBuckets(sparse, '2026-01-01', '2026-03-31', 'month');
    const feb = result.find((b) => b.period === '2026-02');
    expect(feb?.netKopecks).toBe(100000);
    expect(result.find((b) => b.period === '2026-01')?.netKopecks).toBe(0);
    expect(result.find((b) => b.period === '2026-03')?.netKopecks).toBe(0);
  });
});
