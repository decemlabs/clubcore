/**
 * Clients list query type + filter-to-querystring mapper (Phase 101 CLI-01).
 *
 * `ClientsListQuery` mirrors the backend GET /api/v1/clients query parameters
 * (camelCase per Pydantic alias_generator).
 *
 * `filterToQuery` converts the UI filter state to a Record suitable for
 * `staffRequest` `init.query`. Rules:
 *  - Drops undefined keys.
 *  - Drops `q` when length < 2 (backend treats q < 2 as None).
 *  - Maps UI sort preset keys to backend enum values:
 *      'recent:desc' → 'created_at_desc'
 *      'name:asc'    → 'last_name_asc'
 */

export interface ClientsListQuery {
  q?: string;
  gender?: 'male' | 'female';
  tag?: string;
  hasTelegram?: boolean;
  createdFrom?: string;
  createdTo?: string;
  sort?: 'recent:desc' | 'name:asc';
  page?: number;
  pageSize?: number;
}

const SORT_MAP: Record<string, string> = {
  'recent:desc': 'created_at_desc',
  'name:asc': 'last_name_asc',
};

export function filterToQuery(filter: ClientsListQuery): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};

  // q: only include when >= 2 chars
  if (filter.q !== undefined && filter.q.length >= 2) {
    out['q'] = filter.q;
  }

  if (filter.gender !== undefined) out['gender'] = filter.gender;
  if (filter.tag !== undefined) out['tag'] = filter.tag;
  if (filter.hasTelegram !== undefined) out['hasTelegram'] = filter.hasTelegram;
  if (filter.createdFrom !== undefined) out['createdFrom'] = filter.createdFrom;
  if (filter.createdTo !== undefined) out['createdTo'] = filter.createdTo;

  if (filter.sort !== undefined) {
    const mapped = SORT_MAP[filter.sort];
    if (mapped) out['sort'] = mapped;
  }

  if (filter.page !== undefined) out['page'] = filter.page;
  if (filter.pageSize !== undefined) out['pageSize'] = filter.pageSize;

  return out;
}
