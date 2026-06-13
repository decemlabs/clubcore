import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { branchesData } from '@/mocks/branches';
import type { Branch, BranchesData } from './types';

export const branchesKeys = {
  all: ['branches'] as const,
  list: ['branches', 'list'] as const,
  detail: (id: string) => ['branches', 'detail', id] as const,
};

/** Список филиалов + сетевая сводка. */
export function useBranches() {
  return useQuery({
    queryKey: branchesKeys.list,
    queryFn: () => mockResponse<BranchesData>(branchesData),
  });
}

/** Один филиал по id (для детальной страницы настроек). */
export function useBranch(id: string) {
  return useQuery({
    queryKey: branchesKeys.detail(id),
    queryFn: () => mockResponse<Branch | undefined>(branchesData.branches.find((b) => b.id === id)),
  });
}
