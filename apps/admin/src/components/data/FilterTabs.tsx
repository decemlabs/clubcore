import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

export type FilterTabTone = 'accent' | 'warn' | 'danger';

const COUNT_TONE: Record<FilterTabTone, string> = {
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
  danger: 'bg-danger-soft text-danger',
};

export interface FilterTabItem<V extends string> {
  value: V;
  label: string;
  count?: number;
  /** Тон счётчика; по умолчанию нейтральный. */
  tone?: FilterTabTone;
  icon?: LucideIcon;
}

/** Подчёркнутые вкладки-фильтры со счётчиками (и опциональной иконкой). */
export function FilterTabs<V extends string>({
  tabs,
  value,
  onChange,
  ariaLabel,
  className,
}: {
  tabs: FilterTabItem<V>[];
  value: V;
  onChange: (value: V) => void;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        '-mx-1 flex gap-1.5 overflow-x-auto border-b-[0.5px] border-border px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
        className,
      )}
    >
      {tabs.map((tab) => {
        const active = tab.value === value;
        const Icon = tab.icon;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={cn(
              'relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap px-3.5 pb-3.5 pt-3 text-[13.5px] font-semibold tracking-[-0.1px] transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'text-fg' : 'text-fg-muted hover:text-fg',
            )}
          >
            {Icon ? <Icon className="size-3.5" /> : null}
            {tab.label}
            {tab.count != null ? (
              <span
                className={cn(
                  'rounded-full px-[7px] py-px text-[11.5px] font-bold tabular-nums',
                  active
                    ? 'bg-fg text-bg'
                    : tab.tone
                      ? COUNT_TONE[tab.tone]
                      : 'bg-surface-3 text-fg-muted',
                )}
              >
                {tab.count}
              </span>
            ) : null}
            {active ? (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-t-sm bg-fg" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
