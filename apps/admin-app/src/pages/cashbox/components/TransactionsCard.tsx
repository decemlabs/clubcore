import { useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Card, CardHeader } from '@/components/layout/Card';
import { formatInt } from '@/lib/format';
import {
  ArrowDown,
  ArrowRightLeft,
  ChevronRight,
  Coffee,
  CreditCard,
  MoreHorizontal,
  Undo2,
  User,
  Wallet,
} from '@/components/icons';
import type {
  CashboxData,
  Transaction,
  TxCategory,
  TxFilter,
  TxMethod,
} from '@/features/cashbox/types';

const TX_ICON: Record<TxCategory, { Icon: LucideIcon; cls: string }> = {
  membership: { Icon: CreditCard, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
  bar: { Icon: Coffee, cls: 'bg-warning-soft text-warning-deep' },
  pt: { Icon: User, cls: 'bg-surface-3 text-fg-muted' },
  refund: { Icon: Undo2, cls: 'bg-danger-soft text-danger' },
  cashin: { Icon: ArrowDown, cls: 'bg-surface-3 text-fg-subtle' },
};

const METHOD_ICON: Record<TxMethod, LucideIcon> = {
  card: CreditCard,
  cash: Wallet,
  transfer: ArrowRightLeft,
  refund: Undo2,
};

function Chip({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean;
  label: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active
          ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
          : 'border-[0.5px] border-border text-fg-muted hover:border-border-strong hover:text-fg',
      )}
    >
      {label}
      <span
        className={cn(
          'font-mono text-[11px] tabular-nums',
          active ? 'opacity-70' : 'text-fg-subtle',
        )}
      >
        {count}
      </span>
    </button>
  );
}

function TxRow({ tx, first }: { tx: Transaction; first: boolean }) {
  const { Icon, cls } = TX_ICON[tx.category];
  const MethodIcon = METHOD_ICON[tx.method];
  const refund = tx.amount < 0;
  return (
    <div
      className={cn(
        'grid grid-cols-[52px_32px_minmax(0,1fr)_120px_auto_28px] items-center gap-3.5 px-5 py-3 transition-colors hover:bg-surface-2',
        'max-sm:grid-cols-[44px_28px_minmax(0,1fr)_auto]',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      <div className="font-mono text-[12.5px] tabular-nums leading-tight">
        {tx.time}
        <div className="text-[11px] text-fg-subtle">{tx.ago}</div>
      </div>
      <span className={cn('grid size-8 place-items-center rounded-[10px]', cls)}>
        <Icon className="size-4" />
      </span>
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold">{tx.title}</div>
        <div className="truncate text-[11.5px] text-fg-subtle">
          <b className="font-semibold text-fg-muted">{tx.client}</b>
          {tx.note ? <> · {tx.note}</> : null}
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-fg-muted max-sm:hidden">
        <MethodIcon
          className={cn(
            'size-3.5 shrink-0',
            tx.method === 'cash' && 'text-primary-deep dark:text-primary',
          )}
        />
        <span className="truncate">
          {tx.methodLabel}
          {tx.methodTail ? <small className="ml-0.5 text-fg-subtle">{tx.methodTail}</small> : null}
        </span>
      </div>
      <div className="whitespace-nowrap text-right">
        <div
          className={cn(
            'text-[14.5px] font-bold tabular-nums',
            refund ? 'text-danger' : tx.muted ? 'text-fg-subtle' : 'text-fg',
          )}
        >
          {refund ? '−' : '+'}
          {formatInt(Math.abs(tx.amount))}
        </div>
        <div className="text-[11px] text-fg-subtle">{tx.doc}</div>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="Действия с операцией"
            className="grid size-7 place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-sm:hidden"
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[180px]">
          <DropdownMenuItem onSelect={() => toast.success('Чек распечатан')}>
            Печать чека
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => toast('Детали операции')}>
            Детали операции
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-danger focus:text-danger"
            onSelect={() => toast.success('Возврат оформлен')}
          >
            Оформить возврат
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

/** Лента операций смены с фильтр-чипами и итогом. */
export function TransactionsCard({ data }: { data: CashboxData }) {
  const [filter, setFilter] = useState<TxFilter>('all');
  const visible = useMemo(
    () =>
      filter === 'all'
        ? data.transactions
        : data.transactions.filter((t) => (t.category as string) === filter),
    [data.transactions, filter],
  );

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Операции за смену"
        subtitle={`${data.txCount} операций · обновлено только что`}
      />

      <div className="flex flex-wrap gap-2 px-5 pb-3">
        {data.filters.map((c) => (
          <Chip
            key={c.filter}
            active={filter === c.filter}
            label={c.label}
            count={c.count}
            onClick={() => setFilter(c.filter)}
          />
        ))}
      </div>

      <div>
        {visible.map((tx, i) => (
          <TxRow key={tx.id} tx={tx} first={i === 0} />
        ))}
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t-[0.5px] border-border px-5 py-3.5 text-[12.5px] text-fg-muted">
        <span>
          Итого: <b className="font-bold tabular-nums text-fg">+{formatInt(data.txTotal)} ₽</b> по{' '}
          {data.txCount} операциям
        </span>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md font-semibold text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Показать все
          <ChevronRight className="size-3" strokeWidth={2.4} />
        </button>
      </div>
    </Card>
  );
}
