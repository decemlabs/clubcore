/**
 * TDD tests for ClientsReportSchema + TrainersReportSchema (Phase 104-01 Task 2).
 * RED phase: written before schemas are extended.
 */
import { describe, expect, it } from 'vitest';
import { ClientsReportSchema, TrainersReportSchema } from './schemas';
import { reportsQueryKeys as reportsQueryKeysExtended } from './keys';

describe('ClientsReportSchema', () => {
  it('parses a full clients report response', () => {
    const raw = {
      data: {
        activeCount: 120,
        expiringCount: 15,
        newClientsCount: 8,
        withinDays: 30,
      },
    };
    const result = ClientsReportSchema.parse(raw).data;
    expect(result.activeCount).toBe(120);
    expect(result.expiringCount).toBe(15);
    expect(result.newClientsCount).toBe(8);
    expect(result.withinDays).toBe(30);
  });

  it('requires all four numeric fields', () => {
    expect(() => ClientsReportSchema.parse({ data: { activeCount: 1 } })).toThrow();
  });
});

describe('TrainersReportSchema', () => {
  const sampleTrainer = {
    trainerId: 'abc',
    trainerNameSnapshot: 'Иван',
    sessionCount: 10,
    cancelledSessionCount: 1,
    totalHours: 5.5,
    uniqueClientCount: 3,
    utilizationPct: 0.6,
    revenueKopecks: 50000,
    avgRevenuePerSession: 5000,
    totalAccruedKopecks: 50000,
    totalPaidKopecks: 40000,
  };
  const meta = {
    fromDate: '2026-06-01',
    toDate: '2026-06-30',
    revenueAttributionNote: 'Revenue attributed to pt_packages.trainer_id.',
  };

  it('parses a trainers report with the flat data.trainers[] shape', () => {
    const result = TrainersReportSchema.parse({ data: { trainers: [sampleTrainer], ...meta } }).data;
    expect(result.trainers).toHaveLength(1);
    expect(result.trainers[0]?.trainerId).toBe('abc');
    expect(result.trainers[0]?.trainerNameSnapshot).toBe('Иван');
    expect(result.trainers[0]?.revenueKopecks).toBe(50000);
  });

  it('parses an empty trainers array', () => {
    const result = TrainersReportSchema.parse({ data: { trainers: [], ...meta } }).data;
    expect(result.trainers).toHaveLength(0);
  });

  it('tolerates null utilizationPct and avgRevenuePerSession (trainer with no sessions)', () => {
    const idle = { ...sampleTrainer, utilizationPct: null, avgRevenuePerSession: null };
    const result = TrainersReportSchema.parse({ data: { trainers: [idle], ...meta } }).data;
    expect(result.trainers[0]?.utilizationPct).toBeNull();
    expect(result.trainers[0]?.avgRevenuePerSession).toBeNull();
  });
});

// reportsQueryKeys extension — keys test
// NOTE: reportsQueryKeys is imported from './keys'; this import will fail RED until added.
describe('reportsQueryKeysExtended', () => {
  it('clients key differs per query object', () => {
    const q1 = { fromDate: '2025-01-01', toDate: '2025-01-31' };
    const q2 = { fromDate: '2025-02-01', toDate: '2025-02-28' };
    expect(reportsQueryKeysExtended.clients(q1)).not.toEqual(reportsQueryKeysExtended.clients(q2));
  });

  it('trainers key differs per query object', () => {
    const q = { fromDate: '2025-01-01', toDate: '2025-01-31' };
    const q2 = { fromDate: '2025-02-01', toDate: '2025-02-28' };
    expect(reportsQueryKeysExtended.trainers(q)).not.toEqual(reportsQueryKeysExtended.trainers(q2));
  });
});
