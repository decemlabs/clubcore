import type { Client, ClientSort, ClientSortKey } from './types';

export const DEFAULT_DIR: Record<ClientSortKey, ClientSort['dir']> = {
  name: 'asc',
  expires: 'asc',
  visits: 'desc',
  last: 'desc',
};

export function compare(a: Client, b: Client, sort: ClientSort): number {
  const m = sort.dir === 'asc' ? 1 : -1;
  switch (sort.key) {
    case 'name':
      return a.name.localeCompare(b.name, 'ru') * m;
    case 'visits':
      return (a.visits.month - b.visits.month) * m;
    case 'last':
      return (a.lastVisit.rank - b.lastVisit.rank) * m;
    case 'expires': {
      const av = a.expiry?.daysLeft;
      const bv = b.expiry?.daysLeft;
      // Лиды (без срока) — всегда в конце, независимо от направления.
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av - bv) * m;
    }
  }
}
