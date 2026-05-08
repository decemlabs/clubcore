/**
 * Mock service implementations (Faker-backed, in-memory DB, localStorage-persisted).
 *
 * Rules:
 * - Simulate latency (120–300ms) and a configurable failure rate.
 * - Enforce role access (reject with DomainError when `can(role, ...)` is false).
 * - Validate inputs with the same Zod schema the UI form uses.
 * - Never touched by UI/features directly — always flows through the services container.
 */
import { auth } from './auth'
import { clients } from './clients'
import { memberships } from './memberships'

export const services = { auth, clients, memberships } as const // visits added in 22-03
