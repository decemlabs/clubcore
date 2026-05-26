import { ApiError } from '@clubcore/api-client'

export class DomainError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly fields?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'DomainError'
  }
}

export type AppError = ApiError | DomainError

export function isDomainError(e: unknown): e is DomainError {
  return e instanceof DomainError
}

export function isAppError(e: unknown): e is AppError {
  return e instanceof ApiError || isDomainError(e)
}

export function appErrorCode(e: unknown): string | undefined {
  return isAppError(e) ? e.code : undefined
}

export { ApiError } from '@clubcore/api-client'
