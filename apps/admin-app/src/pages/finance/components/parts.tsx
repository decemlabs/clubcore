import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatInt } from '@/lib/format';
import { Initials } from '@/components/ui/initials';
import { StatusPill, type StatusTone } from '@/components/ui/StatusPill';
import { MetricTile } from '@/components/ui/MetricTile';
import { Search, RefreshCw } from '@/components/icons';
import type { FailRow, PayRow, RegRow, RegStatus, PayStatus } from '@/features/finance/types';

/* ---------- KPI tile ---------- */

export function FinanceKpi(props: {
  icon?: LucideIcon;
  label: string;
  value: ReactNode;
  unit?: string;
  variant?: 'default' | 'accent' | 'danger';
}) {
  return <MetricTile {...props} className="transition-shadow hover:shadow-2" />;
}

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

/* ---------- Shared table pieces ---------- */

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

function ClientCell({
  initials,
  gradient,
  name,
  sub,
}: {
  initials: string;
  gradient: string;
  name: string;
  sub: string;
}) {
  return (
    <div className="col-span-2 flex min-w-0 items-center gap-2.5 md:col-span-1">
      <Initials initials={initials} color={gradient} className="size-8 text-[11.5px]" />
      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold">{name}</div>
        <div className="truncate text-[11.5px] text-fg-subtle">{sub}</div>
      </div>
    </div>
  );
}

function DateCell({ date, time }: { date: string; time: string }) {
  return (
    <div className="text-[12.5px] tabular-nums text-fg-muted">
      {date}
      <span className="block text-[11px] text-fg-subtle">{time}</span>
    </div>
  );
}

function FinCell({
  label,
  right,
  children,
}: {
  label?: string;
  right?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={cn('min-w-0', right && 'md:text-right')}>
      {label ? (
        <span className="mb-0.5 block text-[10.5px] font-semibold uppercase tracking-[0.4px] text-fg-subtle md:hidden">
          {label}
        </span>
      ) : null}
      {children}
    </div>
  );
}

const HEAD =
  'hidden border-b-[0.5px] border-border px-4 py-2.5 text-[10.5px] font-bold uppercase tracking-[0.5px] text-fg-subtle md:grid md:items-center md:gap-3.5';
const ROW =
  'grid grid-cols-2 gap-x-3 gap-y-2 border-b-[0.5px] border-border px-4 py-3 last:border-b-0 md:items-center md:gap-3.5';

function fmt(n: number) {
  return formatInt(n);
}

/* ---------- Reg pane ---------- */

export function RegTable({ rows, onRow }: { rows: RegRow[]; onRow: (r: RegRow) => void }) {
  return (
    <div>
      <div className={cn(HEAD, 'md:grid-cols-[92px_1.5fr_1fr_0.9fr_110px]')}>
        <span>Дата</span>
        <span>Клиент / операция</span>
        <span>Способ</span>
        <span className="md:text-right">Сумма</span>
        <span className="md:text-right">Статус</span>
      </div>
      {rows.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={() => onRow(r)}
          className={cn(
            ROW,
            'cursor-pointer text-left transition-colors hover:bg-surface-2 md:grid-cols-[92px_1.5fr_1fr_0.9fr_110px]',
          )}
        >
          <ClientCell initials={r.initials} gradient={r.gradient} name={r.name} sub={r.desc} />
          <FinCell label="Дата">
            <DateCell date={r.date} time={r.time} />
          </FinCell>
          <FinCell label="Способ">
            <span className="text-[12.5px] text-fg-muted">{r.method}</span>
          </FinCell>
          <FinCell label="Сумма" right>
            <span
              className={cn(
                'whitespace-nowrap text-[13px] font-bold tabular-nums',
                r.status === 'refund' && 'text-danger',
              )}
            >
              {r.status === 'refund' ? '−' : ''}
              {fmt(r.amount)}&nbsp;₽
            </span>
          </FinCell>
          <FinCell label="Статус" right>
            <FinStatus status={r.status} />
          </FinCell>
        </button>
      ))}
    </div>
  );
}

/* ---------- Fail pane ---------- */

export function FailTable({ rows, onRetry }: { rows: FailRow[]; onRetry: (r: FailRow) => void }) {
  return (
    <div>
      <div className={cn(HEAD, 'md:grid-cols-[92px_1.4fr_1.3fr_100px_120px]')}>
        <span>Дата</span>
        <span>Клиент</span>
        <span>Причина</span>
        <span className="md:text-right">Сумма</span>
        <span className="md:text-right">Действие</span>
      </div>
      {rows.map((r) => (
        <div key={r.id} className={cn(ROW, 'md:grid-cols-[92px_1.4fr_1.3fr_100px_120px]')}>
          <ClientCell initials={r.initials} gradient={r.gradient} name={r.name} sub={r.phone} />
          <FinCell label="Дата">
            <DateCell date={r.date} time={r.time} />
          </FinCell>
          <FinCell label="Причина">
            <span className="text-[12px] text-danger">{r.reason}</span>
          </FinCell>
          <FinCell label="Сумма" right>
            <span className="whitespace-nowrap text-[13px] font-bold tabular-nums">
              {fmt(r.amount)}&nbsp;₽
            </span>
          </FinCell>
          <FinCell right>
            <button
              type="button"
              onClick={() => onRetry(r)}
              className="inline-flex h-8 items-center gap-1.5 rounded-[9px] border-[0.5px] border-border-strong bg-surface px-2.5 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-md:w-full max-md:justify-center md:ml-auto"
            >
              <RefreshCw className="size-3.5" strokeWidth={2} />
              Повторить
            </button>
          </FinCell>
        </div>
      ))}
    </div>
  );
}

/* ---------- Pay pane ---------- */

export function PayTable({ rows, onPayout }: { rows: PayRow[]; onPayout: (r: PayRow) => void }) {
  return (
    <div>
      <div className={cn(HEAD, 'md:grid-cols-[1.4fr_0.9fr_1fr_1fr_130px]')}>
        <span>Тренер</span>
        <span className="md:text-right">Тренировок</span>
        <span className="md:text-right">Начислено</span>
        <span className="md:text-right">К выплате</span>
        <span className="md:text-right">Статус</span>
      </div>
      {rows.map((r) => (
        <div key={r.id} className={cn(ROW, 'md:grid-cols-[1.4fr_0.9fr_1fr_1fr_130px]')}>
          <ClientCell initials={r.initials} gradient={r.gradient} name={r.name} sub={r.spec} />
          <FinCell label="Тренировок" right>
            <span className="text-[12.5px] text-fg-subtle">—</span>
          </FinCell>
          <FinCell label="Начислено" right>
            <span className="whitespace-nowrap text-[13px] font-semibold tabular-nums">
              {fmt(r.accrued)}&nbsp;₽
            </span>
          </FinCell>
          <FinCell label="К выплате" right>
            <span className="whitespace-nowrap text-[13px] font-bold tabular-nums">
              {fmt(r.payout)}&nbsp;₽
            </span>
          </FinCell>
          <FinCell right>
            {r.status === 'paid' ? (
              <FinStatus status="paid" />
            ) : (
              <button
                type="button"
                onClick={() => onPayout(r)}
                className="inline-flex h-8 items-center rounded-[9px] bg-fg px-3 text-[12.5px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8] max-md:w-full max-md:justify-center md:ml-auto"
              >
                Выплатить
              </button>
            )}
          </FinCell>
        </div>
      ))}
    </div>
  );
}
