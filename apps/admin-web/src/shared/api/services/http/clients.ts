import { request } from '@sportzal/api-client'
import type {
  ClientsService,
  ClientsListQuery,
  ClientCreateInput,
  ClientUpdateInput,
} from '@/shared/api/contracts/clients'
import type { Client, ClientId, Pagination } from '@/entities/client'
import { unwrap } from './_envelope'

export const clients: ClientsService = {
  async list(query: ClientsListQuery) {
    // Append query params to URL -- RequestInitWithBody has no `query` field.
    // The `as never` cast satisfies the openapi paths type while keeping the URL dynamic.
    const params = new URLSearchParams()
    if (query.q) params.set('q', query.q)
    params.set('page', String(query.page))
    params.set('pageSize', String(query.pageSize))
    return unwrap<Pagination<Client>>(
      await request('get', `/api/v1/clients?${params.toString()}` as never),
    )
  },
  async get(id: ClientId) {
    return unwrap<Client>(
      await request('get', '/api/v1/clients/{client_id}', { params: { client_id: id } } as never),
    )
  },
  async create(input: ClientCreateInput) {
    return unwrap<Client>(await request('post', '/api/v1/clients', { body: input }))
  },
  async update(id: ClientId, input: ClientUpdateInput) {
    return unwrap<Client>(
      await request('patch', '/api/v1/clients/{client_id}', {
        params: { client_id: id },
        body: input,
      } as never),
    )
  },
  async remove(id: ClientId) {
    // 204 No Content -- pass through (no unwrap needed).
    await request('delete', '/api/v1/clients/{client_id}', {
      params: { client_id: id },
    } as never)
  },
}
