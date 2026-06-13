import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { trashData } from '@/mocks/trash';
import type { TrashData } from './types';

export const trashKeys = {
  all: ['trash'] as const,
};

/** Данные экрана «Корзина». */
export function useTrash() {
  return useQuery({
    queryKey: trashKeys.all,
    queryFn: () => mockResponse<TrashData>(trashData),
  });
}
