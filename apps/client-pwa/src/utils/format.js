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

export function addHour(time) {
  const [h, m] = time.split(':').map(Number);
  const nh = (h + 1) % 24;
  return `${String(nh).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
