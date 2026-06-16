import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Search } from '@/components/icons';
import { StatusPill, type StatusTone } from '@/components/ui/StatusPill';
import type { RegStatus, PayStatus } from '@/features/finance/types';

/* ---------- Tabs ---------- */

export interface FinTab {
  key: string;
  label: string;
  badge?: number;
}

export function FinanceTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: FinTab[];
  value: string;
  onChange: (k: string) => void;
}) {
  return (
    <div className="inline-flex max-w-full gap-1 self-start overflow-x-auto rounded-[11px] bg-surface-3 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={cn(
              'inline-flex h-[34px] shrink-0 items-center gap-2 rounded-lg px-[15px] text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg',
            )}
          >
            {t.label}
            {t.badge != null ? (
              <span className="grid min-w-4 place-items-center rounded-full bg-danger px-1 text-[10.5px] font-bold text-white">
                {t.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Shared panel / toolbar ---------- */

export { Panel } from '@/components/layout/Panel';

export function Toolbar({
  search,
  onSearch,
  placeholder,
  right,
}: {
  search?: string;
  onSearch?: (v: string) => void;
  placeholder?: string;
  right: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2.5 border-b-[0.5px] border-border bg-surface-2 px-4 py-3">
      {onSearch ? (
        <div className="relative min-w-[160px] max-w-[300px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            type="search"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder={placeholder}
            className="h-9 w-full rounded-[9px] border-[0.5px] border-border-strong bg-surface pl-9 pr-3 text-[13px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-primary focus:shadow-[0_0_0_3px_var(--primary-soft)]"
          />
        </div>
      ) : null}
      {right}
    </div>
  );
}

/* ---------- Status pill (used by FinanceModals) ---------- */

const STATUS: Record<RegStatus | PayStatus, { tone: StatusTone; label: string }> = {
  ok: { tone: 'success', label: 'Успешно' },
  refund: { tone: 'neutral', label: 'Возврат' },
  pending: { tone: 'warning', label: 'Ожидание' },
  paid: { tone: 'success', label: 'Выплачено' },
};

export function FinStatus({ status }: { status: RegStatus | PayStatus }) {
  const s = STATUS[status];
  return (
    <StatusPill tone={s.tone} dot={false}>
      {s.label}
    </StatusPill>
  );
}
