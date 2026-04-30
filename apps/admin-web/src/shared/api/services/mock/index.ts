/**
 * Mock service implementations (Faker-backed, in-memory DB, localStorage-persisted).
 *
 * Populated per-domain in later phases. Phase 1 ships an empty container so
 * the swap seam type-checks.
 *
 * Rules:
 * - Simulate latency (120–300ms) and a configurable failure rate.
 * - Enforce role access (reject with DomainError when `can(role, ...)` is false).
 * - Validate inputs with the same Zod schema the UI form uses.
 * - Never touched by UI/features directly — always flows through the services container.
 */
export const services = {} as const
