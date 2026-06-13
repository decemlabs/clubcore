import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { messagesData } from '@/mocks/messages';
import type { MessagesData } from './types';

/** Ключи запросов сообщений. */
export const messagesKeys = {
  all: ['messages'] as const,
  inbox: ['messages', 'inbox'] as const,
};

/**
 * Данные инбокса сообщений. Пока резолвит мок; при появлении backend
 * меняется только queryFn — страница не трогается.
 */
export function useMessages() {
  return useQuery({
    queryKey: messagesKeys.inbox,
    queryFn: () => mockResponse<MessagesData>(messagesData),
  });
}
