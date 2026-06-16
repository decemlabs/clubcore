/**
 * Format integer kopeck amount to ru-RU RUB string (e.g. 150000 → "1 500 ₽").
 * Uses NBSPs via Intl.NumberFormat; mirrors admin-web money.ts convention.
 *
 * @param {number} kopecks - Integer amount in kopecks
 * @returns {string}
 */
export function formatMoney(kopecks) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(kopecks / 100);
}

export function monthName(m) {
  return ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'][m] || '';
}

/**
 * Format an ISO date-only string "YYYY-MM-DD" as a Russian long date "27 ноября 2026".
 * Parses by splitting on '-' — NEVER calls new Date(dateOnlyString) (DST risk, CLAUDE.md).
 * Returns '' on falsy or malformed input so the caller can guard.
 *
 * @param {string} isoDateOnly - ISO date string "YYYY-MM-DD"
 * @returns {string}
 */
export function formatRuDate(isoDateOnly) {
  if (!isoDateOnly) return '';
  const parts = isoDateOnly.split('-');
  if (parts.length !== 3) return '';
  const year = parts[0];
  const monthIndex = parseInt(parts[1], 10) - 1; // 0-based
  const day = parseInt(parts[2], 10);
  const GENITIVE_MONTHS = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ];
  const monthStr = GENITIVE_MONTHS[monthIndex];
  if (!monthStr || !day || !year) return '';
  return `${day} ${monthStr} ${year}`;
}

export function addHour(time) {
  const [h, m] = time.split(':').map(Number);
  const nh = (h + 1) % 24;
  return `${String(nh).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
