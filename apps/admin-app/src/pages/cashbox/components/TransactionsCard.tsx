/**
 * TransactionsCard — cash ledger with refund rows and daily-total separators (Phase 103-03).
 *
 * Renders real PaymentData items from GET /api/v1/payments.
 *
 * Refund rows (refundOf != null):
 *   - Icon chip: bg-danger-soft text-danger with Undo2 icon
 *   - Title: «Возврат»
 *   - Amount: text-danger with «−» (U+2212) prefix, READ-ONLY (no action menu)
 *
 * Non-refund rows (owner only):
 *   - Icon chip: based on subjectKind
 *   - Amount: text-fg with «+» prefix
 *   - Owner sees «Оформить возврат» destructive DropdownMenuItem (Phase 112 REF-01)
 *   - Reception sees NO menu trigger (hidden entirely, not disabled — T-112-14)
 *
 * Daily-total separators are injected between date groups using DailyTotal[].
 * Negative daily totals shown in text-danger.
 */
import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { formatRub, formatWeekdayLongRu } from '@/lib/format';
import { CreditCard, MoreHorizontal, Undo2, User } from '@/components/icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { RefundModal } from '@/components/modals/RefundModal';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import type { PaymentData } from '@/features/payments/schemas';
import type { DailyTotal } from '@/features/payments/schemas';

// ---------------------------------------------------------------------------
// Icon chip mapping by subjectKind
// ---------------------------------------------------------------------------

function getChipClass(subjectKind: string, isRefund: boolean): string {
  if (isRefund) return 'bg-danger-soft text-danger';
  if (subjectKind === 'membership') return 'bg-primary-soft text-primary-deep dark:text-primary';
  // pt_package or unknown
  return 'bg-surface-3 text-fg-muted';
}

function getIcon(subjectKind: string, isRefund: boolean) {
  if (isRefund) return Undo2;
  if (subjectKind === 'membership') return CreditCard;
  return User;
}

function getTitle(subjectKind: string, isRefund: boolean): string {
  if (isRefund) return 'Возврат';
  if (subjectKind === 'membership') return 'Абонемент';
  return 'PT-пакет';
}

// ---------------------------------------------------------------------------
// Payment row
// ---------------------------------------------------------------------------

function PaymentRow({
  payment,
  first,
  role,
  onRefund,
}: {
  payment: PaymentData;
  first: boolean;
  role: Role;
  onRefund: (payment: PaymentData) => void;
}) {
  const isRefund = payment.refundOf != null;
  const Icon = getIcon(payment.subjectKind, isRefund);
  const chipClass = getChipClass(payment.subjectKind, isRefund);
  const title = getTitle(payment.subjectKind, isRefund);
  const absAmount = Math.abs(payment.amountKopecks);

  // Owner-gated refund action — hidden entirely for reception (T-112-14)
  const canRefund = can(role, 'refund', 'finance');

  return (
    <div
      className={cn(
        'grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-2',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      <span className={cn('grid size-9 place-items-center rounded-[10px]', chipClass)}>
        <Icon className="size-4" />
      </span>
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold">{title}</div>
        <div className="truncate text-[11.5px] text-fg-subtle">
          {payment.method === 'cash' ? 'Наличные' : 'Онлайн'} · {payment.receivedAt.slice(11, 16)}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div
          className={cn(
            'whitespace-nowrap text-right text-[14.5px] font-bold tabular-nums',
            isRefund ? 'text-danger' : 'text-fg',
          )}
        >
          {/* U+2212 minus sign for refunds, + for payments */}
          {isRefund ? '−' : '+'}
          {formatRub(absAmount / 100)}
        </div>
        {/* Owner-only row action — completely hidden for reception and for refund rows */}
        {canRefund && !isRefund ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="Действия"
                className="grid size-7 place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
              >
                <MoreHorizontal className="size-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                variant="destructive"
                onClick={() => onRefund(payment)}
              >
                Оформить возврат
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Daily total separator row
// ---------------------------------------------------------------------------

function DailyTotalRow({ total }: { total: DailyTotal }) {
  const negative = total.totalKopecks < 0;
  return (
    <div className="flex items-center justify-between bg-surface-2 px-5 py-2 text-[11.5px]">
      <span className="font-semibold text-fg-muted capitalize">
        {formatWeekdayLongRu(total.date)}
      </span>
      <span
        className={cn(
          'font-bold tabular-nums',
          negative ? 'text-danger' : 'text-fg-muted',
        )}
      >
        Итого: {negative ? '−' : '+'}{formatRub(Math.abs(total.totalKopecks) / 100)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------

/**
 * Cash ledger card. Renders payments grouped by date with daily-total separator rows.
 * Owner sees «Оформить возврат» action on non-refund rows (Phase 112 REF-01).
 * Reception sees no action trigger (T-112-14 — hidden entirely, not disabled).
 */
export function TransactionsCard({
  items,
  dailyTotals,
  role,
}: {
  items: PaymentData[];
  dailyTotals: DailyTotal[];
  role: Role;
}) {
  const [refundPayment, setRefundPayment] = useState<PaymentData | null>(null);

  // Build a map of date → DailyTotal for O(1) lookup during render
  const totalsMap = new Map(dailyTotals.map((t) => [t.date, t]));

  // Group items by date (ISO prefix) to inject separators
  const seenDates = new Set<string>();
  const rows: Array<{ type: 'total'; total: DailyTotal } | { type: 'payment'; payment: PaymentData; firstOfDate: boolean }> = [];

  for (const payment of items) {
    const date = payment.receivedAt.slice(0, 10);
    const isFirst = !seenDates.has(date);
    if (isFirst) {
      seenDates.add(date);
      const total = totalsMap.get(date);
      if (total) {
        rows.push({ type: 'total', total });
      }
    }
    rows.push({ type: 'payment', payment, firstOfDate: isFirst });
  }

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Операции"
        subtitle={`${items.length} операций в периоде`}
      />
      <div>
        {rows.map((row) => {
          if (row.type === 'total') {
            return <DailyTotalRow key={`total-${row.total.date}`} total={row.total} />;
          }
          return (
            <PaymentRow
              key={row.payment.id}
              payment={row.payment}
              first={row.firstOfDate}
              role={role}
              onRefund={setRefundPayment}
            />
          );
        })}
      </div>

      {/* RefundModal — opens when owner clicks «Оформить возврат» on a payment row */}
      {refundPayment ? (
        <RefundModal
          payment={refundPayment}
          open={refundPayment !== null}
          onOpenChange={(open) => {
            if (!open) setRefundPayment(null);
          }}
        />
      ) : null}
    </Card>
  );
}
