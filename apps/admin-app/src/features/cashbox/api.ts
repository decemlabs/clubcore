import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { cashboxData } from '@/mocks/cashbox';
import type { CashboxData } from './types';

/** Ключи запросов кассы. */
export const cashboxKeys = {
  all: ['cashbox'] as const,
  shift: ['cashbox', 'shift'] as const,
};

/**
 * Данные кассы (открытая смена). Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function useCashbox() {
  return useQuery({
    queryKey: cashboxKeys.shift,
    queryFn: () => mockResponse<CashboxData>(cashboxData),
  });
}
