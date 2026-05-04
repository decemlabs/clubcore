import { faker } from '@faker-js/faker'
import type { Client, ClientId } from '@/entities/client'

const STORAGE_KEY = 'sportzal:mock:v1'
const SEED_COUNT = 30

export interface DB {
  clients: Client[]
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

function seed(): DB {
  faker.seed(42)
  const clients: Client[] = Array.from({ length: SEED_COUNT }, generateClient)
  const db: DB = { clients }
  saveDB(db)
  return db
}

export function loadDB(): DB {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return seed()
    const parsed = JSON.parse(raw) as DB
    if (!parsed || !Array.isArray(parsed.clients)) return seed()
    return parsed
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
