/**
 * TDD tests for reports schemas (Phase 104-01 Task 2 + Phase 115-03 Task 1).
 * Covers ClientsReportSchema, TrainersReportSchema (existing),
 * and LoadNowSchema, CohortRetentionSchema, VisitAnomalySchema, AtRiskSchema (new).
 */
import { describe, expect, it } from 'vitest';
import {
  ClientsReportSchema,
  TrainersReportSchema,
  LoadNowSchema,
  CohortRetentionSchema,
  VisitAnomalySchema,
  AtRiskSchema,
} from './schemas';
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

// ---------------------------------------------------------------------------
// Phase 115-03 — new advanced analytics schemas (RED phase)
// ---------------------------------------------------------------------------

describe('LoadNowSchema', () => {
  const validResponse = {
    data: {
      count: 5,
      asOf: '2026-06-15T14:30:00Z',
      windowMinutes: 120,
    },
  };

  it('parses a valid load/now response (matching real wire shape)', () => {
    const result = LoadNowSchema.parse(validResponse).data;
    expect(result.count).toBe(5);
    expect(result.asOf).toBe('2026-06-15T14:30:00Z');
    expect(result.windowMinutes).toBe(120);
  });

  it('parses zero count (no one in gym)', () => {
    const result = LoadNowSchema.parse({ data: { ...validResponse.data, count: 0 } }).data;
    expect(result.count).toBe(0);
  });

  it('rejects negative count', () => {
    expect(() =>
      LoadNowSchema.parse({ data: { ...validResponse.data, count: -1 } }),
    ).toThrow();
  });

  it('rejects non-integer count', () => {
    expect(() =>
      LoadNowSchema.parse({ data: { ...validResponse.data, count: 1.5 } }),
    ).toThrow();
  });

  it('rejects zero windowMinutes (must be positive)', () => {
    expect(() =>
      LoadNowSchema.parse({ data: { ...validResponse.data, windowMinutes: 0 } }),
    ).toThrow();
  });
});

describe('CohortRetentionSchema', () => {
  const validCohort = {
    cohortMonth: '2026-01',
    label: 'янв 2026',
    months: [
      { offset: 0, retentionPct: 100 },
      { offset: 1, retentionPct: 72.5 },
      { offset: 2, retentionPct: null },
    ],
  };
  const validResponse = {
    data: {
      cohorts: [validCohort],
      maxOffset: 2,
    },
  };

  it('parses the nested cohort shape from 115-01-SUMMARY (authoritative wire)', () => {
    const result = CohortRetentionSchema.parse(validResponse).data;
    expect(result.cohorts).toHaveLength(1);
    expect(result.cohorts[0]?.cohortMonth).toBe('2026-01');
    expect(result.cohorts[0]?.label).toBe('янв 2026');
    expect(result.cohorts[0]?.months).toHaveLength(3);
    expect(result.cohorts[0]?.months[0]?.offset).toBe(0);
    expect(result.cohorts[0]?.months[0]?.retentionPct).toBe(100);
    expect(result.cohorts[0]?.months[2]?.retentionPct).toBeNull();
    expect(result.maxOffset).toBe(2);
  });

  it('parses empty cohorts array (no data case)', () => {
    const result = CohortRetentionSchema.parse({ data: { cohorts: [], maxOffset: 0 } }).data;
    expect(result.cohorts).toHaveLength(0);
    expect(result.maxOffset).toBe(0);
  });

  it('tolerates null retentionPct in a month entry', () => {
    const withNull = { ...validCohort, months: [{ offset: 0, retentionPct: null }] };
    const result = CohortRetentionSchema.parse({ data: { cohorts: [withNull], maxOffset: 0 } }).data;
    expect(result.cohorts[0]?.months[0]?.retentionPct).toBeNull();
  });
});

describe('VisitAnomalySchema', () => {
  const validPoint = {
    date: '2026-06-01',
    count: 15,
    isAnomaly: true,
    direction: 'spike' as const,
    label: '1 июн',
  };
  const validResponse = {
    data: {
      points: [validPoint, { ...validPoint, isAnomaly: false, direction: null, date: '2026-06-02', label: '2 июн' }],
      windowDays: 14,
      sigmaThreshold: 2.0,
      anomalyCount: 1,
    },
  };

  it('parses the anomaly shape from 115-01-SUMMARY (authoritative wire)', () => {
    const result = VisitAnomalySchema.parse(validResponse).data;
    expect(result.points).toHaveLength(2);
    expect(result.points[0]?.date).toBe('2026-06-01');
    expect(result.points[0]?.isAnomaly).toBe(true);
    expect(result.points[0]?.direction).toBe('spike');
    expect(result.points[1]?.direction).toBeNull();
    expect(result.windowDays).toBe(14);
    expect(result.sigmaThreshold).toBe(2.0);
    expect(result.anomalyCount).toBe(1);
  });

  it('parses empty points array (no data)', () => {
    const result = VisitAnomalySchema.parse({
      data: { points: [], windowDays: 14, sigmaThreshold: 2.0, anomalyCount: 0 },
    }).data;
    expect(result.points).toHaveLength(0);
    expect(result.anomalyCount).toBe(0);
  });

  it('accepts drop direction', () => {
    const drop = { ...validPoint, direction: 'drop' as const };
    const result = VisitAnomalySchema.parse({
      data: { ...validResponse.data, points: [drop] },
    }).data;
    expect(result.points[0]?.direction).toBe('drop');
  });

  it('rejects unknown direction values', () => {
    const bad = { ...validPoint, direction: 'unknown' };
    expect(() =>
      VisitAnomalySchema.parse({ data: { ...validResponse.data, points: [bad] } }),
    ).toThrow();
  });
});

describe('AtRiskSchema', () => {
  const validItem = {
    clientId: 'uuid-123',
    name: 'Иванов Иван',
    membershipType: 'Безлимит на 30 дней',
    lastVisitDate: '2026-06-01',
    daysSinceVisit: 14,
    lastVisitLabel: '14 дней назад',
  };
  const validResponse = {
    data: {
      count: 1,
      items: [validItem],
      thresholdDays: 14,
    },
  };

  it('parses the at-risk shape from 115-01-SUMMARY (authoritative wire)', () => {
    const result = AtRiskSchema.parse(validResponse).data;
    expect(result.count).toBe(1);
    expect(result.items).toHaveLength(1);
    expect(result.items[0]?.clientId).toBe('uuid-123');
    expect(result.items[0]?.name).toBe('Иванов Иван');
    expect(result.items[0]?.membershipType).toBe('Безлимит на 30 дней');
    expect(result.items[0]?.lastVisitDate).toBe('2026-06-01');
    expect(result.items[0]?.daysSinceVisit).toBe(14);
    expect(result.items[0]?.lastVisitLabel).toBe('14 дней назад');
    expect(result.thresholdDays).toBe(14);
  });

  it('tolerates null lastVisitDate for never-visited clients', () => {
    const neverVisited = { ...validItem, lastVisitDate: null };
    const result = AtRiskSchema.parse({ data: { ...validResponse.data, items: [neverVisited] } }).data;
    expect(result.items[0]?.lastVisitDate).toBeNull();
  });

  it('parses empty items array (zero-risk case)', () => {
    const result = AtRiskSchema.parse({ data: { count: 0, items: [], thresholdDays: 14 } }).data;
    expect(result.count).toBe(0);
    expect(result.items).toHaveLength(0);
  });
});

// Phase 115-03 query keys
describe('reportsQueryKeys — Phase 115 advanced analytics keys', () => {
  it('cohort key includes query param', () => {
    const q1 = { cohortMonths: 6 };
    const q2 = { cohortMonths: 12 };
    expect(reportsQueryKeysExtended.cohort(q1)).not.toEqual(reportsQueryKeysExtended.cohort(q2));
  });

  it('anomaly key includes query param', () => {
    const q1 = { fromDate: '2026-01-01', toDate: '2026-03-31' };
    const q2 = { fromDate: '2026-02-01', toDate: '2026-04-30' };
    expect(reportsQueryKeysExtended.anomaly(q1)).not.toEqual(reportsQueryKeysExtended.anomaly(q2));
  });

  it('atRisk key is stable (no params)', () => {
    expect(reportsQueryKeysExtended.atRisk()).toEqual(reportsQueryKeysExtended.atRisk());
  });

  it('loadNow key is stable (no params)', () => {
    expect(reportsQueryKeysExtended.loadNow()).toEqual(reportsQueryKeysExtended.loadNow());
  });
});
