import { request, type components } from '@sportzal/api-client'
import type {
  ClientsService,
  ClientsListQuery,
  ClientCreateInput,
  ClientUpdateInput,
} from '@/shared/api/contracts/clients'
import type { ClientId } from '@/entities/client'
import { unwrap } from './_envelope'
import {
  responseToClient,
  createInputToRequest,
  updateInputToRequest,
} from './_clientsAdapter'

type ClientResponse = components['schemas']['ClientResponse']

interface PaginatedClientResponse {
  items: ClientResponse[]
  total: number
  page: number
  pageSize: number
}

export const clients: ClientsService = {
  async list(query: ClientsListQuery) {
    const q: Record<string, string | number> = {
      page: query.page,
      pageSize: query.pageSize,
    }
    if (query.q) q.q = query.q
    const raw = unwrap<PaginatedClientResponse>(
      await request('get', '/api/v1/clients', { query: q }),
    )
    return { ...raw, items: raw.items.map(responseToClient) }
  },
  async get(id: ClientId) {
    const raw = unwrap<ClientResponse>(
      await request('get', '/api/v1/clients/{client_id}', { params: { client_id: id } }),
    )
    return responseToClient(raw)
  },
  async create(input: ClientCreateInput) {
    const raw = unwrap<ClientResponse>(
      await request('post', '/api/v1/clients', { body: createInputToRequest(input) }),
    )
    return responseToClient(raw)
  },
  async update(id: ClientId, input: ClientUpdateInput) {
    const raw = unwrap<ClientResponse>(
      await request('patch', '/api/v1/clients/{client_id}', {
        params: { client_id: id },
        body: updateInputToRequest(input),
      }),
    )
    return responseToClient(raw)
  },
  async remove(id: ClientId) {
    // 204 No Content -- pass through (no unwrap needed).
    await request('delete', '/api/v1/clients/{client_id}', {
      params: { client_id: id },
    })
  },
}
