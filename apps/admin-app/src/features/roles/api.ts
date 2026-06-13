import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { rolesData } from '@/mocks/roles';
import type { RolesData } from './types';

export const rolesKeys = {
  all: ['roles'] as const,
};

/** Данные экрана «Роли и права доступа». */
export function useRoles() {
  return useQuery({
    queryKey: rolesKeys.all,
    queryFn: () => mockResponse<RolesData>(rolesData),
  });
}
