import type {
  Membership,
  MembershipId,
  MembershipPlan,
  MembershipPlanId,
  Pagination,
} from '@/entities/membership'

export interface MembershipsListQuery {
  page: number
  pageSize: number
  clientId?: string
  expiring?: boolean // DEBT-02: forwarded to backend (Phase 24); both impls share semantics
  within?: number // DEBT-02: 1..30, defaults to 7 server-side; ignored when expiring is false
}

export interface MembershipPlansListQuery {
  page?: number
  pageSize?: number
  active?: boolean
}

export interface MembershipCreateInput {
  clientId: string
  planId: MembershipPlanId
  paidAt?: string
  notes?: string
}

export interface MembershipPlanCreateInput {
  name: string
  durationDays: number
  priceKopecks: number
  active?: boolean
}

export interface MembershipPlanUpdateInput {
  name?: string
  priceKopecks?: number
  active?: boolean
}

export interface MembershipsService {
  list(query: MembershipsListQuery): Promise<Pagination<Membership>>
  byClient(clientId: string): Promise<Pagination<Membership>>
  get(id: MembershipId): Promise<Membership>
  create(input: MembershipCreateInput): Promise<Membership>
  cancel(id: MembershipId, reason?: string): Promise<Membership>
  // Plans (the catalog) — co-located on the same service per D-22-7
  listPlans(query: MembershipPlansListQuery): Promise<Pagination<MembershipPlan>>
  getPlan(id: MembershipPlanId): Promise<MembershipPlan>
  createPlan(input: MembershipPlanCreateInput): Promise<MembershipPlan>
  updatePlan(id: MembershipPlanId, input: MembershipPlanUpdateInput): Promise<MembershipPlan>
  deletePlan(id: MembershipPlanId): Promise<void>
}
