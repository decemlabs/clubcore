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
    // Append query params to URL -- RequestInitWithBody has no `query` field.
    // The `as never` cast satisfies the openapi paths type while keeping the URL dynamic.
    const params = new URLSearchParams()
    if (query.q) params.set('q', query.q)
    params.set('page', String(query.page))
    params.set('pageSize', String(query.pageSize))
    const raw = unwrap<PaginatedClientResponse>(
      await request('get', `/api/v1/clients?${params.toString()}` as never),
    )
    return { ...raw, items: raw.items.map(responseToClient) }
  },
  async get(id: ClientId) {
    const raw = unwrap<ClientResponse>(
      await request('get', '/api/v1/clients/{client_id}', { params: { client_id: id } } as never),
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
      } as never),
    )
    return responseToClient(raw)
  },
  async remove(id: ClientId) {
    // 204 No Content -- pass through (no unwrap needed).
    await request('delete', '/api/v1/clients/{client_id}', {
      params: { client_id: id },
    } as never)
  },
}
