/**
 * Статический индекс для глобального поиска (⌘K-палитра). Синхронно собирается из
 * мок-данных клиентов/тренеров/тарифов — палитре нужен мгновенный поиск без loading,
 * поэтому читаем массивы напрямую, а не через TanStack-хуки. Когда появится бэкенд,
 * это станет debounce-запросом к /search, а форма SearchResult останется прежней.
 */
import { clientsPageData } from '@/mocks/clients';
import { trainersPageData } from '@/mocks/trainers';
import { plansPageData } from '@/mocks/plans';
import type { ClientStatus } from '@/features/clients/types';
import { ROUTES } from '@/app/routes';

export type SearchKind = 'client' | 'trainer' | 'tariff';

export interface SearchResult {
  id: string;
  kind: SearchKind;
  title: string;
  /** Подпись под названием. */
  sub: string;
  /** Маршрут перехода. */
  to: string;
  /** Инициалы для аватара (клиенты/тренеры). */
  initials?: string;
  /** Цвет аватара (hex/градиент из данных). */
  color?: string;
  /** Доп. строки для поиска (телефон и т.п.). */
  keywords?: string;
}

const CLIENT_STATUS_LABEL: Record<ClientStatus, string> = {
  active: 'активен',
  expiring: 'истекает',
  frozen: 'заморожен',
  lead: 'лид',
  expired: 'истёк',
};

const clients: SearchResult[] = clientsPageData.clients.map((c) => {
  const plan = c.plan ? `«${c.plan.name}» · ` : '';
  return {
    id: `client-${c.id}`,
    kind: 'client',
    title: c.name,
    sub: `${c.phone} · ${plan}${CLIENT_STATUS_LABEL[c.status]}`,
    to: ROUTES.client(c.id),
    initials: c.initials,
    color: c.color,
    keywords: `${c.phone} ${c.plan?.name ?? ''}`,
  };
});

const trainers: SearchResult[] = trainersPageData.trainers.map((t) => ({
  id: `trainer-${t.id}`,
  kind: 'trainer',
  title: t.name,
  sub: t.specialization,
  to: ROUTES.trainer(t.id),
  initials: t.initials,
  color: t.avatarColor,
}));

const tariffs: SearchResult[] = plansPageData.tariffs.map((tariff) => ({
  id: `tariff-${tariff.id}`,
  kind: 'tariff',
  title: tariff.name,
  sub: `${tariff.sumLabel} · ${tariff.tag}`,
  to: ROUTES.plans,
}));

export const searchIndex: SearchResult[] = [...clients, ...trainers, ...tariffs];

/** Заголовки групп палитры по типу. */
export const SEARCH_GROUP_LABEL: Record<SearchKind, string> = {
  client: 'Клиенты',
  trainer: 'Тренеры',
  tariff: 'Абонементы',
};

/** Для футера палитры — «Поиск по N клиентам · M тренерам». */
export const searchTotals = {
  clients: clientsPageData.totalCount,
  trainers: trainersPageData.summary.total,
};
