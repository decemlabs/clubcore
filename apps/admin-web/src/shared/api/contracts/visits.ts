import type { Visit, VisitId } from '@/entities/visit'
import type { Pagination } from '@/entities/membership'

export interface VisitsListQuery {
  page: number
  pageSize: number
  clientId?: string
  from?: string // YYYY-MM-DD
  to?: string
}

export interface GymMeta {
  gymHoursStart: string // HH:MM
  gymHoursEnd: string // HH:MM
}

export interface VisitsService {
  list(query: VisitsListQuery): Promise<Pagination<Visit>>
  recentByClient(clientId: string, opts: { limit: number }): Promise<Visit[]>
  get(id: VisitId): Promise<Visit>
  checkIn(clientId: string): Promise<Visit>
  gymMeta(): Promise<GymMeta>
}

export type { Visit, VisitId, Pagination }
