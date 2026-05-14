import { faker } from '@faker-js/faker'
import type { Client, ClientId } from '@/entities/client'
import type { Membership, MembershipId, MembershipPlan, MembershipPlanId, MembershipStatus, FreezePeriod } from '@/entities/membership'
import type { Trainer } from '@/entities/trainer'
import type { Visit, VisitId, VisitChannel } from '@/entities/visit'

const STORAGE_KEY = 'sportzal:mock:v1'
const SEED_COUNT = 30
const PLAN_COUNT = 8
const MEMBERSHIP_COUNT = 40
const VISIT_COUNT = 150

export interface DB {
  clients: Client[]
  memberships: Membership[]
  plans: MembershipPlan[]
  trainers: Trainer[]
  visits: Visit[]
}

function generateClient(): Client {
  const lastName = faker.person.lastName()
  const firstName = faker.person.firstName()
  const middleName = faker.helpers.maybe(() => faker.person.middleName(), { probability: 0.6 })
  const fullName = [lastName, firstName, middleName].filter(Boolean).join(' ')
  // E.164 RU phone: +7 followed by 10 digits
  const phone = `+7${faker.string.numeric(10)}`
  const email = faker.helpers.maybe(() => faker.internet.email().toLowerCase(), { probability: 0.7 })
  const birthDate = faker.helpers.maybe(
    () => faker.date.birthdate({ min: 18, max: 75, mode: 'age' }).toISOString().slice(0, 10),
    { probability: 0.8 },
  )
  const createdAt = faker.date.recent({ days: 365 }).toISOString()
  return {
    id: faker.string.uuid() as ClientId,
    fullName,
    phone,
    email,
    birthDate,
    createdAt,
  }
}

const DURATION_OPTIONS = [30, 90, 180, 365] as const

function generatePlan(): MembershipPlan {
  const durationDays = faker.helpers.arrayElement(DURATION_OPTIONS)
  const priceKopecks = faker.number.int({ min: 200_000, max: 2_500_000 })
  // freezeDaysLimit: 1 week per month of plan duration (sensible default per D-28-05)
  const freezeDaysLimit = Math.round(durationDays / 7)
  return {
    id: faker.string.uuid() as MembershipPlanId,
    name: `${faker.word.adjective()} ${durationDays}-дневный абонемент`,
    durationDays,
    priceKopecks,
    freezeDaysLimit,
    active: faker.datatype.boolean({ probability: 0.85 }),
    createdAt: faker.date.recent({ days: 365 }).toISOString(),
    updatedAt: faker.date.recent({ days: 30 }).toISOString(),
  }
}

function generateMembership(clients: Client[], plans: MembershipPlan[]): Membership {
  const client = faker.helpers.arrayElement(clients)
  const plan = faker.helpers.arrayElement(plans)
  const startDate = faker.date.recent({ days: 400 })
  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + plan.durationDays - 1) // INCLUSIVE
  const today = new Date()
  let status: MembershipStatus
  if (endDate < today) {
    status = faker.helpers.weightedArrayElement([
      { value: 'expired' as const, weight: 7 },
      { value: 'cancelled' as const, weight: 3 },
    ])
  } else {
    status = 'active'
  }
  const cancelledAt =
    status === 'cancelled'
      ? faker.date.between({ from: startDate, to: today }).toISOString()
      : null
  const cancelReason =
    status === 'cancelled' ? faker.helpers.maybe(() => faker.lorem.sentence(), { probability: 0.6 }) ?? null : null
  const freezeDaysLimitSnapshot = plan.freezeDaysLimit
  const freezeDaysUsed = 0
  const freezeDaysRemaining = freezeDaysLimitSnapshot
  const currentFreezePeriod: FreezePeriod | null = null
  return {
    id: faker.string.uuid() as MembershipId,
    clientId: client.id,
    planId: plan.id as MembershipPlanId,
    planNameSnapshot: plan.name,
    durationDaysSnapshot: plan.durationDays,
    priceKopecksSnapshot: plan.priceKopecks,
    startDate: startDate.toISOString().slice(0, 10),
    endDate: endDate.toISOString().slice(0, 10),
    status,
    paidAt: faker.helpers.maybe(() => startDate.toISOString(), { probability: 0.8 }) ?? null,
    notes: faker.helpers.maybe(() => faker.lorem.sentence(), { probability: 0.3 }) ?? null,
    cancelledAt,
    cancelReason,
    freezeDaysLimitSnapshot,
    freezeDaysUsed,
    freezeDaysRemaining,
    currentFreezePeriod,
    previousMembershipId: null,
    createdAt: startDate.toISOString(),
    updatedAt: faker.date.recent({ days: 14 }).toISOString(),
  }
}

function generateVisit(clients: Client[], memberships: Membership[]): Visit {
  const client = faker.helpers.arrayElement(clients)
  const clientMemberships = memberships.filter((m) => m.clientId === client.id)
  const membership =
    clientMemberships.length > 0
      ? faker.helpers.arrayElement(clientMemberships)
      : memberships[0]! // fallback to first membership if client has none
  // Generate a date within the last 60 days
  const daysAgo = faker.number.int({ min: 0, max: 60 })
  const checkedInAt = new Date()
  checkedInAt.setDate(checkedInAt.getDate() - daysAgo)
  // Randomize time within gym hours (07:00-23:00)
  checkedInAt.setHours(faker.number.int({ min: 7, max: 22 }), faker.number.int({ min: 0, max: 59 }))
  // gymDate: YYYY-MM-DD in Europe/Moscow
  const gymDate = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow' }).format(checkedInAt)
  const channel: VisitChannel = faker.helpers.weightedArrayElement([
    { value: 'reception' as const, weight: 8 },
    { value: 'telegram_bot' as const, weight: 2 },
  ])
  return {
    id: faker.string.uuid() as VisitId,
    clientId: client.id,
    membershipId: membership.id,
    checkedInAt: checkedInAt.toISOString(),
    gymDate,
    channel,
    checkedInBy: channel === 'telegram_bot' ? null : faker.string.uuid(),
    createdAt: checkedInAt.toISOString(),
  }
}

function seed(): DB {
  faker.seed(42)
  const clients: Client[] = Array.from({ length: SEED_COUNT }, generateClient)
  const plans: MembershipPlan[] = Array.from({ length: PLAN_COUNT }, generatePlan)
  const memberships: Membership[] = Array.from({ length: MEMBERSHIP_COUNT }, () =>
    generateMembership(clients, plans),
  )
  const visits: Visit[] = Array.from({ length: VISIT_COUNT }, () =>
    generateVisit(clients, memberships),
  )
  const db: DB = { clients, memberships, plans, trainers: [], visits }
  saveDB(db)
  return db
}

export function loadDB(): DB {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return seed()
    const parsed = JSON.parse(raw) as Partial<DB>
    if (
      !parsed ||
      !Array.isArray(parsed.clients) ||
      !Array.isArray(parsed.memberships) ||
      !Array.isArray(parsed.plans) ||
      !Array.isArray(parsed.visits)
    ) {
      // WR-09: re-seed the entire DB instead of trying to additively migrate.
      // The previous additive branches kept stored `clients` while regenerating
      // memberships/visits — but the regenerated rows reference fresh client
      // UUIDs that don't exist in the kept stored clients, breaking joins
      // (byClient, recent visits). It's a dev-mode mock store; seeding fresh
      // is simpler and correct.
      return seed()
    }
    // D-31-23: within-version migration — add trainers array if missing from older payload.
    if (!Array.isArray(parsed.trainers)) {
      parsed.trainers = []
    }
    return parsed as DB
  } catch {
    return seed()
  }
}

export function saveDB(db: DB): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db))
  } catch {
    /* noop — storage full or disabled; mock continues with stale state */
  }
}

export function resetDB(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* noop */
  }
}

export const SEEDED_COUNT = SEED_COUNT
export const MOCK_STORAGE_KEY = STORAGE_KEY
