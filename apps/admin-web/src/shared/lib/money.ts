const RUB_FORMATTER = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/**
 * Format an integer in minor units (kopecks) as a Russian RUB currency string.
 * Includes NBSP (\u00A0) between groups and before the currency symbol per ru-RU.
 *
 * @example formatMoney(123456) // "1 234,56 ₽" (with NBSPs)
 */
export function formatMoney(minor: number): string {
  return RUB_FORMATTER.format(minor / 100)
}
