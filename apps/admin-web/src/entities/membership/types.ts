import type { Brand } from '@/shared/lib/brand'

export type MembershipId = Brand<string, 'MembershipId'>
export type MembershipPlanId = Brand<string, 'MembershipPlanId'>
export type MembershipStatus = 'active' | 'expired' | 'cancelled' | 'frozen'

export interface FreezePeriod {
  id: string
  startedAt: string // ISO datetime
  startedBy: string // user ID (mock uses role string as proxy)
  endedAt: string | null
  endedBy: string | null
}

export interface MembershipPlan {
  id: MembershipPlanId
  name: string
  durationDays: number
  priceKopecks: number
  freezeDaysLimit: number
  active: boolean
  createdAt: string // ISO datetime
  updatedAt: string
}

export interface Membership {
  id: MembershipId
  clientId: string
  planId: MembershipPlanId
  planNameSnapshot: string
  durationDaysSnapshot: number
  priceKopecksSnapshot: number
  startDate: string // ISO yyyy-MM-dd
  endDate: string // ISO yyyy-MM-dd, INCLUSIVE
  status: MembershipStatus
  paidAt?: string | null
  notes?: string | null
  cancelledAt?: string | null
  cancelReason?: string | null
  freezeDaysLimitSnapshot: number
  freezeDaysUsed: number
  freezeDaysRemaining: number
  currentFreezePeriod: FreezePeriod | null
  previousMembershipId?: string | null
  createdAt: string
  updatedAt: string
}

// Pagination envelope (locked-not-discussed)
export interface Pagination<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}
