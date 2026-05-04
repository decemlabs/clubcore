import type { Client, ClientId, Pagination } from '@/entities/client'

export interface ClientsListQuery {
  q?: string
  page: number
  pageSize: number
}

export interface ClientCreateInput {
  lastName: string
  firstName: string
  middleName?: string
  phone: string
  email?: string
  birthDate?: string // ISO yyyy-MM-dd
  notes?: string
}

export type ClientUpdateInput = Partial<ClientCreateInput>

export interface ClientsService {
  list(query: ClientsListQuery): Promise<Pagination<Client>>
  get(id: ClientId): Promise<Client>
  create(input: ClientCreateInput): Promise<Client>
  update(id: ClientId, input: ClientUpdateInput): Promise<Client>
  remove(id: ClientId): Promise<void>
}

export type { Client, ClientId, Pagination }
