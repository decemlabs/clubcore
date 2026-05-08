import { request, type components } from '@sportzal/api-client'
import type { VisitsService, VisitsListQuery } from '@/shared/api/contracts/visits'
import type { VisitId } from '@/entities/visit'
import { unwrap } from './_envelope'
import { responseToVisit, responseToGymMeta } from './_visitsAdapter'

type PaginatedVisitResponse = components['schemas']['PaginatedData_VisitResponse_']

export const visits: VisitsService = {
  async list(query: VisitsListQuery) {
    const q: Record<string, string | number> = {
      page: query.page,
      pageSize: query.pageSize,
    }
    if (query.clientId) q.clientId = query.clientId
    if (query.from) q['from_'] = query.from // backend uses from_ (Python reserved word)
    if (query.to) q.to = query.to
    const raw = unwrap<PaginatedVisitResponse>(
      await request('get', '/api/v1/visits', { query: q }),
    )
    return { ...raw, items: raw.items.map(responseToVisit) }
  },

  async recentByClient(clientId: string, { limit }: { limit: number }) {
    const raw = unwrap<PaginatedVisitResponse>(
      await request('get', '/api/v1/visits', { query: { clientId, page: 1, pageSize: limit } }),
    )
    return raw.items.map(responseToVisit)
  },

  async get(id: VisitId) {
    const raw = unwrap<components['schemas']['VisitResponse']>(
      await request('get', '/api/v1/visits/{visit_id}', { params: { visit_id: id } }),
    )
    return responseToVisit(raw)
  },

  async checkIn(clientId: string) {
    const raw = unwrap<components['schemas']['VisitResponse']>(
      await request('post', '/api/v1/visits', { body: { clientId } }),
    )
    return responseToVisit(raw)
  },

  async gymMeta() {
    const raw = unwrap<components['schemas']['VisitsMetaResponse']>(
      await request('get', '/api/v1/visits/_meta'),
    )
    return responseToGymMeta(raw)
  },
}
