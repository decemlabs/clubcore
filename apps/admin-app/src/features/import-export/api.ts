import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { importExportData } from '@/mocks/import-export';
import type { ImportExportData } from './types';

export const importExportKeys = {
  all: ['import-export'] as const,
};

/** Данные экрана «Импорт / Экспорт». */
export function useImportExport() {
  return useQuery({
    queryKey: importExportKeys.all,
    queryFn: () => mockResponse<ImportExportData>(importExportData),
  });
}
