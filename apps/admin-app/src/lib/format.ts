import { format, formatDistanceToNowStrict } from 'date-fns';
import { ru } from 'date-fns/locale';

const RUB = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
});

export function formatRub(value: number): string {
  return RUB.format(value);
}

const INT = new Intl.NumberFormat('ru-RU');

export function formatInt(value: number): string {
  return INT.format(value);
}

export function formatDateRu(date: Date | string, pattern = 'd MMMM'): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return format(d, pattern, { locale: ru });
}

export function formatWeekdayLongRu(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return format(d, 'EEEE, d MMMM', { locale: ru });
}

export function formatRelativeRu(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return formatDistanceToNowStrict(d, { locale: ru, addSuffix: true });
}

export function formatTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
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
