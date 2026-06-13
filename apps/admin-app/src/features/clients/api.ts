import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { clientsPageData } from '@/mocks/clients';
import { clientDetail } from '@/mocks/client-detail';
import type { ClientsPageData } from './types';
import type { ClientDetail } from './detail';

/** Ключи запросов клиентов (стабильные, для инвалидации). */
export const clientsKeys = {
  all: ['clients'] as const,
  list: ['clients', 'list'] as const,
  detail: (id: string) => ['clients', 'detail', id] as const,
};

/**
 * Данные страницы «Клиенты» (сводка, вкладки-фильтры, список, пагинация).
 * Пока резолвит мок; при появлении backend меняется только queryFn — страница не трогается.
 */
export function useClients() {
  return useQuery({
    queryKey: clientsKeys.list,
    queryFn: () => mockResponse<ClientsPageData>(clientsPageData),
  });
}

/**
 * Детальная карточка клиента по id. Пока есть один подробный профиль-мок —
 * резолвим его независимо от id; при появлении backend queryFn получит id.
 */
export function useClient(id: string) {
  return useQuery({
    queryKey: clientsKeys.detail(id),
    queryFn: () => mockResponse<ClientDetail>(clientDetail),
  });
}
