/**
 * TDD tests for dashboard domain hooks (Phase 104-02 Task 1).
 * RED phase: written before api.ts is rewritten.
 *
 * Tests validate:
 * - useScheduleToday is exported (not useDashboard)
 * - useExpiringMemberships is exported
 * - useDashboard is NOT exported (mock removed)
 * - owner-only report hooks are re-exported from features/reports
 */
import { describe, expect, it } from 'vitest';
import * as dashboardApi from './api';

describe('dashboard api.ts exports (104-02)', () => {
  it('exports useScheduleToday', () => {
    expect(typeof dashboardApi.useScheduleToday).toBe('function');
  });

  it('exports useExpiringMemberships', () => {
    expect(typeof dashboardApi.useExpiringMemberships).toBe('function');
  });

  it('does NOT export useDashboard (mock removed)', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((dashboardApi as Record<string, unknown>)['useDashboard']).toBeUndefined();
  });

  it('re-exports useRevenueReport from features/reports', () => {
    expect(typeof dashboardApi.useRevenueReport).toBe('function');
  });

  it('re-exports useVisitsReport from features/reports', () => {
    expect(typeof dashboardApi.useVisitsReport).toBe('function');
  });

  it('re-exports useClientsReport from features/reports', () => {
    expect(typeof dashboardApi.useClientsReport).toBe('function');
  });

  it('re-exports useTrainersReport from features/reports', () => {
    expect(typeof dashboardApi.useTrainersReport).toBe('function');
  });
});
