import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'

export const DATE_FMT = 'dd.MM.yyyy'
export const TIME_FMT = 'HH:mm'
export const DATETIME_FMT = 'dd.MM.yyyy HH:mm'

export const MOSCOW_TZ = 'Europe/Moscow'

export const WEEK_STARTS_ON = 1 as const

function toDate(input: string | Date): Date {
  return typeof input === 'string' ? parseISO(input) : input
}

export function formatDate(input: string | Date): string {
  return format(toDate(input), DATE_FMT, { locale: ru, weekStartsOn: WEEK_STARTS_ON })
}

export function formatTime(input: string | Date): string {
  return format(toDate(input), TIME_FMT, { locale: ru, weekStartsOn: WEEK_STARTS_ON })
}

export function formatDateTime(input: string | Date): string {
  return format(toDate(input), DATETIME_FMT, { locale: ru, weekStartsOn: WEEK_STARTS_ON })
}

/**
 * Returns today's date in YYYY-MM-DD format pinned to Europe/Moscow timezone.
 * Uses sv-SE locale which produces ISO YYYY-MM-DD format natively.
 * Used by D-3 badge logic in MembershipsBlock (Phase 22 D-22-9).
 */
export function todayMSK(): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: MOSCOW_TZ }).format(new Date())
}
