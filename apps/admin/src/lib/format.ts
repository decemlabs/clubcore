import { format, formatDistanceToNowStrict, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale';

const RUB = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
});

export function formatRub(value: number): string {
  return RUB.format(value);
}

/**
 * Formats an integer-kopecks money value as RUB. Use this at every call site
 * that holds a `*Kopecks` value (the backend's money unit) — it divides by 100
 * before formatting. `formatRub` does NOT divide, so feeding it kopecks renders
 * 100× too high (5 000 ₽ stored as 500000 → «500 000 ₽»). (BUG-3)
 * @example formatKopecks(500000) // → «5 000 ₽»
 */
export function formatKopecks(kopecks: number): string {
  return RUB.format(kopecks / 100);
}

const INT = new Intl.NumberFormat('ru-RU');

export function formatInt(value: number): string {
  return INT.format(value);
}

// ---------------------------------------------------------------------------
// MSK-safe date helpers (CR-02 / WR-02)
// ---------------------------------------------------------------------------

/**
 * Returns today's date as 'YYYY-MM-DD' in the Europe/Moscow timezone.
 * Uses sv-SE locale which natively produces ISO yyyy-MM-dd format.
 * Avoids the UTC date-slip that occurs with toISOString().slice(0,10)
 * between 00:00–02:59 MSK (UTC+3).
 */
export function mskTodayISO(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' })
}

/**
 * Returns the date N days ago as 'YYYY-MM-DD' in the Europe/Moscow timezone.
 */
export function mskDaysAgoISO(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' })
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/**
 * Format a date or ISO date string using date-fns with Russian locale.
 * Date-only strings ('YYYY-MM-DD') are parsed via parseISO (local midnight)
 * per CLAUDE.md Dates convention: Never new Date(dateOnlyString) (DST risk).
 */
export function formatDateRu(date: Date | string, pattern = 'd MMMM'): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, pattern, { locale: ru });
}

export function formatWeekdayLongRu(date: Date | string): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'EEEE, d MMMM', { locale: ru });
}

export function formatRelativeRu(date: Date | string): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return formatDistanceToNowStrict(d, { locale: ru, addSuffix: true });
}

export function formatTime(date: Date | string): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'HH:mm');
}

/**
 * Возвращает инициалы из полного имени (первые буквы первых двух слов, в верхнем регистре).
 * Примеры: "Маша Костина" → "МК", "Иван" → "И", "" → "?".
 */
export function getInitials(fullName: string): string {
  const words = fullName.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  return words
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join('')
}

/** Русская плюрализация: forms = [один, два-четыре, пять]. */
export function pluralRu(n: number, forms: [string, string, string]): string {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}
