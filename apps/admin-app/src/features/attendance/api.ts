import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { attendanceData } from '@/mocks/attendance';
import type { AttendanceData } from './types';

/** Ключи запросов посещаемости. */
export const attendanceKeys = {
  all: ['attendance'] as const,
  summary: ['attendance', 'summary'] as const,
};

/**
 * Данные дашборда «Посещаемость». Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function useAttendance() {
  return useQuery({
    queryKey: attendanceKeys.summary,
    queryFn: () => mockResponse<AttendanceData>(attendanceData),
  });
}
