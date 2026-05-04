import type { Brand } from '@/shared/lib/brand'

export type ClientId = Brand<string, 'ClientId'>

export interface Client {
  id: ClientId
  fullName: string
  phone: string
  email?: string
  birthDate?: string // ISO yyyy-MM-dd; never `Date` in domain
  notes?: string
  createdAt: string // ISO datetime
  deletedAt?: string // soft-delete sentinel from Phase 8 backend
}

export interface Pagination<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}
