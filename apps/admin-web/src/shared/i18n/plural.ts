const RU_PLURAL_RULES = new Intl.PluralRules('ru-RU')

export interface PluralForms {
  one: string
  few: string
  many: string
  other?: string
}

/**
 * Russian 3-form pluralization via Intl.PluralRules.
 * Examples (n / form):
 *   1 → one     (1 клиент)
 *   2..4, 22..24 → few   (2 клиента)
 *   0, 5..20, 11..14, 25..30 → many  (5 клиентов)
 */
export function plural(n: number, forms: PluralForms): string {
  const cat = RU_PLURAL_RULES.select(n) as keyof PluralForms
  return forms[cat] ?? forms.other ?? forms.many
}
