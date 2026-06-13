import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { auditData } from '@/mocks/audit';
import type { AuditData } from './types';

export const auditKeys = {
  all: ['audit'] as const,
};

/** Данные экрана «Журнал действий». */
export function useAuditLog() {
  return useQuery({
    queryKey: auditKeys.all,
    queryFn: () => mockResponse<AuditData>(auditData),
  });
}
