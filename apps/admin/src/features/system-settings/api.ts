import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { systemSettingsData } from '@/mocks/system-settings';
import type { SystemSettingsData } from './types';

export const systemSettingsKeys = {
  all: ['system-settings'] as const,
};

/** Данные страницы «Настройки системы». При появлении backend меняется только queryFn. */
export function useSystemSettings() {
  return useQuery({
    queryKey: systemSettingsKeys.all,
    queryFn: () => mockResponse<SystemSettingsData>(systemSettingsData),
  });
}
