import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { settingsData } from '@/mocks/settings';
import type { SettingsData } from './types';

/** Ключи запросов настроек. */
export const settingsKeys = {
  all: ['settings'] as const,
};

/**
 * Данные экрана «Настройки». Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function useSettings() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: () => mockResponse<SettingsData>(settingsData),
  });
}
