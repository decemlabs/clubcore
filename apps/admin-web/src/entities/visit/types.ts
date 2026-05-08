export type VisitId = string & { readonly __brand: 'VisitId' }
export type VisitChannel = 'reception' | 'telegram_bot'

export interface Visit {
  id: VisitId
  clientId: string
  membershipId: string
  checkedInAt: string // ISO datetime UTC
  gymDate: string // YYYY-MM-DD Europe/Moscow
  channel: VisitChannel
  checkedInBy?: string | null // user UUID; null for telegram_bot
  createdAt: string
}
