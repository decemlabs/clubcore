/**
 * TDD tests for ClientsReportSchema + TrainersReportSchema (Phase 104-01 Task 2).
 * RED phase: written before schemas are extended.
 */
import { describe, expect, it } from 'vitest';
import { ClientsReportSchema, TrainersReportSchema, reportsQueryKeysExtended } from './schemas';

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
  it('parses a trainers report with rows', () => {
    const raw = {
      data: {
        rows: [
          {
            trainerId: 'abc',
            name: 'Иван',
            sessionCount: 10,
            totalHours: 5.5,
            uniqueClients: 3,
            utilizationPct: 0.6,
            totalRevenueKopecks: 50000,
          },
        ],
      },
    };
    const result = TrainersReportSchema.parse(raw).data;
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]?.trainerId).toBe('abc');
    expect(result.rows[0]?.totalRevenueKopecks).toBe(50000);
  });

  it('parses an empty rows array', () => {
    const result = TrainersReportSchema.parse({ data: { rows: [] } }).data;
    expect(result.rows).toHaveLength(0);
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
