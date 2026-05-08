import { faker } from '@faker-js/faker'
import type { Client, ClientId } from '@/entities/client'
import type { Membership, MembershipId, MembershipPlan, MembershipPlanId, MembershipStatus } from '@/entities/membership'

const STORAGE_KEY = 'sportzal:mock:v1'
const SEED_COUNT = 30
const PLAN_COUNT = 8
const MEMBERSHIP_COUNT = 40

export interface DB {
  clients: Client[]
  memberships: Membership[]
  plans: MembershipPlan[]
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
  return {
    id: faker.string.uuid() as MembershipPlanId,
    name: `${faker.word.adjective()} ${durationDays}-дневный абонемент`,
    durationDays,
    priceKopecks,
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
    createdAt: startDate.toISOString(),
    updatedAt: faker.date.recent({ days: 14 }).toISOString(),
  }
}

function seed(): DB {
  faker.seed(42)
  const clients: Client[] = Array.from({ length: SEED_COUNT }, generateClient)
  const plans: MembershipPlan[] = Array.from({ length: PLAN_COUNT }, generatePlan)
  const memberships: Membership[] = Array.from({ length: MEMBERSHIP_COUNT }, () =>
    generateMembership(clients, plans),
  )
  const db: DB = { clients, memberships, plans }
  saveDB(db)
  return db
}

export function loadDB(): DB {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return seed()
    const parsed = JSON.parse(raw) as Partial<DB>
    if (!parsed || !Array.isArray(parsed.clients)) return seed()
    // Additive migration: if memberships/plans are missing from stored data, seed them
    if (!Array.isArray(parsed.memberships) || !Array.isArray(parsed.plans)) {
      faker.seed(42)
      const clients = Array.from({ length: SEED_COUNT }, generateClient)
      const plans = Array.from({ length: PLAN_COUNT }, generatePlan)
      const memberships = Array.from({ length: MEMBERSHIP_COUNT }, () =>
        generateMembership(clients, plans),
      )
      const full: DB = {
        clients: parsed.clients,
        memberships: parsed.memberships ?? memberships,
        plans: parsed.plans ?? plans,
      }
      saveDB(full)
      return full
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
