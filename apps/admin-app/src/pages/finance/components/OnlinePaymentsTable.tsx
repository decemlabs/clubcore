/**
 * OnlinePaymentsTable — paginated table of online payments (Phase 103-04).
 *
 * Renders PaymentData rows filtered to method='online'.
 * Row anatomy mirrors TransactionsCard (cashbox) — reuses the same visual treatment:
 *   - Refund rows (refundOf != null): Undo2 icon chip bg-danger-soft, «Возврат» title,
 *     amount text-danger with «−» (U+2212) prefix — READ-ONLY.
 *   - Non-refund rows: CreditCard/User chip, «Абонемент»/«PT-пакет» title, «+» prefix.
 * Amount: formatRub(Math.abs(amountKopecks) / 100).
 * Date: formatDateRu(receivedAt) + time slice.
 */
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { Pagination } from '@/components/data/Pagination';
import { formatRub, formatDateRu } from '@/lib/format';
import { CreditCard, Undo2, User } from '@/components/icons';
import type { PaymentData } from '@/features/payments/schemas';

// ---------------------------------------------------------------------------
// Icon chip helpers (mirrors TransactionsCard)
// ---------------------------------------------------------------------------

function getChipClass(subjectKind: string, isRefund: boolean): string {
  if (isRefund) return 'bg-danger-soft text-danger';
  if (subjectKind === 'membership') return 'bg-primary-soft text-primary-deep dark:text-primary';
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

function PaymentRow({ payment, first }: { payment: PaymentData; first: boolean }) {
  const isRefund = payment.refundOf != null;
  const Icon = getIcon(payment.subjectKind, isRefund);
  const chipClass = getChipClass(payment.subjectKind, isRefund);
  const title = getTitle(payment.subjectKind, isRefund);
  const absAmount = Math.abs(payment.amountKopecks);

  // Format date: 'dd MMMM' + time from receivedAt
  const dateLabel = formatDateRu(payment.receivedAt);
  const timeLabel = payment.receivedAt.slice(11, 16);

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
          Онлайн · {dateLabel} · {timeLabel}
        </div>
      </div>
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface OnlinePaymentsTableProps {
  items: PaymentData[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function OnlinePaymentsTable({
  items,
  total,
  page,
  pageSize,
  onPageChange,
}: OnlinePaymentsTableProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <Card as="section" className="flex flex-col">
      <CardHeader
        title="Онлайн-платежи"
        subtitle={`${total} операций · только метод «Онлайн»`}
      />
      <div>
        {items.map((payment, i) => (
          <PaymentRow key={payment.id} payment={payment} first={i === 0} />
        ))}
      </div>
      {pageCount > 1 ? (
        <Pagination
          page={page}
          pageCount={pageCount}
          shown={items.length}
          total={total}
          noun="платежей"
          onPageChange={onPageChange}
        />
      ) : null}
    </Card>
  );
}
