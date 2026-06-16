import { cn } from '@/lib/cn';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export type SegmentedVariant = 'default' | 'mini';

const VARIANT: Record<
  SegmentedVariant,
  { root: string; button: string; active: string; inactive: string }
> = {
  // Крупный сегмент-контрол (переключатель периодов в шапке и т.п.).
  default: {
    root: 'inline-flex gap-0.5 rounded-full border-[0.5px] border-border bg-surface p-[3px]',
    button:
      'h-[30px] shrink-0 rounded-full px-3.5 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface',
    active: 'bg-fg text-bg',
    inactive: 'text-fg-muted hover:text-fg',
  },
  // Компактный сегмент внутри карточек (фильтры периодов/ленты).
  mini: {
    root: 'inline-flex shrink-0 gap-px rounded-full bg-surface-3 p-0.5',
    button:
      'h-[22px] rounded-full px-[9px] text-[11.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    active: 'bg-surface text-fg shadow-1',
    inactive: 'text-fg-muted hover:text-fg',
  },
};

/**
 * Сегментный контрол (период / фильтры). Доступный: набор кнопок с aria-pressed.
 * `variant='mini'` — компактная версия для шапок карточек.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
  variant = 'default',
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
  className?: string;
  variant?: SegmentedVariant;
}) {
  const v = VARIANT[variant];
  return (
    <div role="group" aria-label={ariaLabel} className={cn(v.root, className)}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(v.button, active ? v.active : v.inactive)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
