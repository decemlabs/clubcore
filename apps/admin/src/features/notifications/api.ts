import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { notificationsData } from '@/mocks/notifications';
import type { NotificationsData } from './types';

export const notificationsKeys = {
  all: ['notifications'] as const,
};

/** Данные экрана «Уведомления и сообщения». */
export function useNotifications() {
  return useQuery({
    queryKey: notificationsKeys.all,
    queryFn: () => mockResponse<NotificationsData>(notificationsData),
  });
}
