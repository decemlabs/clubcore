/**
 * Payroll domain query key factory (Phase 102-04 TRN-02).
 */
export const payrollKeys = {
  all: ['payroll'] as const,

  configs: () => [...payrollKeys.all, 'configs'] as const,
  config: (trainerId: string) => [...payrollKeys.configs(), trainerId] as const,

  previews: () => [...payrollKeys.all, 'preview'] as const,
  preview: (trainerId: string, period: { periodStart: string; periodEnd: string }) =>
    [...payrollKeys.previews(), trainerId, period] as const,

  accrualsList: () => [...payrollKeys.all, 'accruals'] as const,
  accruals: (trainerId: string) => [...payrollKeys.accrualsList(), trainerId] as const,
} as const;
