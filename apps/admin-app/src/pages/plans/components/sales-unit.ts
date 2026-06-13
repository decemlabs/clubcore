import type { SegmentedOption } from '@/components/ui/Segmented';

/** Единица измерения графика продаж: штуки или рубли. */
export type SalesUnit = 'count' | 'rub';

export const SALES_UNIT_OPTIONS: SegmentedOption<SalesUnit>[] = [
  { value: 'count', label: 'Шт.' },
  { value: 'rub', label: '₽' },
];
