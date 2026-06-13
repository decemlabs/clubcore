import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { plansPageData } from '@/mocks/plans';
import type { PlansPageData } from './types';

/** Ключи запросов абонементов/тарифов. */
export const plansKeys = {
  all: ['plans'] as const,
  catalogue: ['plans', 'catalogue'] as const,
};

/**
 * Данные экрана «Абонементы и тарифы». Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function usePlans() {
  return useQuery({
    queryKey: plansKeys.catalogue,
    queryFn: () => mockResponse<PlansPageData>(plansPageData),
  });
}
