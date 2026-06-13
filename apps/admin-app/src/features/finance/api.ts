import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { financeData } from '@/mocks/finance';
import type { FinanceData } from './types';

export const financeKeys = {
  all: ['finance'] as const,
};

/** Данные экрана «Финансы». */
export function useFinance() {
  return useQuery({
    queryKey: financeKeys.all,
    queryFn: () => mockResponse<FinanceData>(financeData),
  });
}
