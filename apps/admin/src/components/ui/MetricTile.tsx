import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

const VALUE_COLOR = {
  default: '',
  accent: 'text-primary-deep dark:text-primary',
  danger: 'text-danger',
} as const;

/** Компактная метрика-плитка (финансы, филиалы): подпись (+иконка) и крупное значение. Значение 22px, единица 12px (нормализация ±1px, см. plans/009). */
export function MetricTile({
  icon: Icon,
  label,
  value,
  unit,
  variant = 'default',
  className,
}: {
  icon?: LucideIcon;
  label: string;
  value: ReactNode;
  unit?: string;
  variant?: keyof typeof VALUE_COLOR;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-[14px] border-[0.5px] border-border bg-surface px-4 py-3.5 shadow-1',
        className,
      )}
    >
      <div className="flex items-center gap-1.5 text-[12px] text-fg-muted">
        {Icon ? <Icon className="size-[13px] shrink-0 text-fg-subtle" strokeWidth={2} /> : null}
        {label}
      </div>
      <div
        className={cn(
          'mt-1.5 text-[22px] font-bold tabular-nums tracking-[-0.5px]',
          VALUE_COLOR[variant],
        )}
      >
        {value}
        {unit ? <span className="text-[12px] font-semibold text-fg-subtle">{unit}</span> : null}
      </div>
    </div>
  );
}
