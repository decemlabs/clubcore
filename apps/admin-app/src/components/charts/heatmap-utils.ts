/** Типы и цветовые карты тепловой карты интенсивности (вынесено ради react-refresh). */

export type HeatLevel = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 'over' | 'closed';

export interface HeatCellData {
  level: HeatLevel;
  now?: boolean;
  title?: string;
  /** Текст внутри ячейки (опц.). */
  text?: string;
}
export interface HeatRowData {
  label: string;
  weekend?: boolean;
  cells: HeatCellData[];
}

/** Изумрудная шкала интенсивности (поверх surface-3). */
const LEVEL_BG: Record<number, string> = {
  0: 'bg-surface-3',
  1: 'bg-[color-mix(in_oklab,var(--primary)_14%,var(--surface-3))]',
  2: 'bg-[color-mix(in_oklab,var(--primary)_28%,var(--surface-3))]',
  3: 'bg-[color-mix(in_oklab,var(--primary)_46%,var(--surface-3))]',
  4: 'bg-[color-mix(in_oklab,var(--primary)_66%,var(--surface-3))]',
  5: 'bg-primary',
  6: 'bg-primary-deep',
};

const CLOSED_BG =
  'bg-[repeating-linear-gradient(45deg,var(--surface-2)_0_4px,var(--surface-3)_4px_8px)] border border-dashed border-border';

/** CSS-класс фона ячейки по уровню. */
export function cellClass(level: HeatLevel): string {
  if (level === 'over') return 'bg-danger text-white';
  if (level === 'closed') return CLOSED_BG;
  return LEVEL_BG[level] ?? 'bg-surface-3';
}

/** Свотчи шкалы для легенды (0…6). */
export const HEAT_SCALE: number[] = [0, 1, 2, 3, 4, 5, 6];
