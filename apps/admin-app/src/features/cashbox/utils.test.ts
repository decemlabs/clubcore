/**
 * TDD tests for computeDailyTotals (Phase 103-03).
 *
 * Behavior under test:
 *   - Groups payments by MSK date, sums SIGNED amountKopecks
 *   - Empty array → empty array (no NaN)
 *   - Refund on same date subtracts from total
 *   - Results sorted ascending by date
 */
import { describe, it, expect } from 'vitest';
import { computeDailyTotals } from './utils';
import type { PaymentData } from '@/features/payments/schemas';

function makePayment(overrides: Partial<PaymentData> & { receivedAt: string; amountKopecks: number }): PaymentData {
  return {
    id: 'test-id',
    subjectKind: 'membership',
    subjectId: 'sub-1',
    method: 'cash',
    receivedByUserId: 'user-1',
    refundOf: null,
    auditLogId: null,
    ...overrides,
  };
}

describe('computeDailyTotals', () => {
  it('returns empty array for empty input (no NaN)', () => {
    const result = computeDailyTotals([]);
    expect(result).toEqual([]);
  });

  it('groups single payment into one daily total', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-10T10:00:00', amountKopecks: 500_000 }),
    ];
    const result = computeDailyTotals(items);
    expect(result).toHaveLength(1);
    expect(result.at(0)).toEqual({ date: '2026-06-10', totalKopecks: 500_000 });
  });

  it('sums signed amounts: +500000 sale and -200000 refund on same date → 300000', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-10T09:00:00', amountKopecks: 500_000 }),
      makePayment({ receivedAt: '2026-06-10T11:00:00', amountKopecks: -200_000, refundOf: 'orig-id' }),
    ];
    const result = computeDailyTotals(items);
    expect(result).toHaveLength(1);
    expect(result.at(0)).toEqual({ date: '2026-06-10', totalKopecks: 300_000 });
  });

  it('produces negative total when refunds exceed sales', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-12T08:00:00', amountKopecks: 100_000 }),
      makePayment({ receivedAt: '2026-06-12T09:00:00', amountKopecks: -300_000, refundOf: 'orig-id' }),
    ];
    const result = computeDailyTotals(items);
    expect(result).toHaveLength(1);
    expect(result.at(0)?.totalKopecks).toBe(-200_000);
  });

  it('separates payments on different dates into distinct totals', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-10T10:00:00', amountKopecks: 100_000 }),
      makePayment({ receivedAt: '2026-06-11T10:00:00', amountKopecks: 200_000 }),
    ];
    const result = computeDailyTotals(items);
    expect(result).toHaveLength(2);
    expect(result.at(0)?.date).toBe('2026-06-10');
    expect(result.at(1)?.date).toBe('2026-06-11');
  });

  it('returns results sorted ascending by date', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-12T10:00:00', amountKopecks: 300_000 }),
      makePayment({ receivedAt: '2026-06-10T10:00:00', amountKopecks: 100_000 }),
      makePayment({ receivedAt: '2026-06-11T10:00:00', amountKopecks: 200_000 }),
    ];
    const result = computeDailyTotals(items);
    expect(result.map((r) => r.date)).toEqual(['2026-06-10', '2026-06-11', '2026-06-12']);
  });

  it('sums multiple payments on the same date correctly', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-10T08:00:00', amountKopecks: 100_000 }),
      makePayment({ receivedAt: '2026-06-10T12:00:00', amountKopecks: 150_000 }),
      makePayment({ receivedAt: '2026-06-10T15:00:00', amountKopecks: 50_000 }),
    ];
    const result = computeDailyTotals(items);
    expect(result).toHaveLength(1);
    expect(result.at(0)?.totalKopecks).toBe(300_000);
  });

  it('totalKopecks is never NaN', () => {
    const items = [
      makePayment({ receivedAt: '2026-06-10T10:00:00', amountKopecks: 0 }),
    ];
    const result = computeDailyTotals(items);
    expect(result.at(0)?.totalKopecks).not.toBeNaN();
  });
});
