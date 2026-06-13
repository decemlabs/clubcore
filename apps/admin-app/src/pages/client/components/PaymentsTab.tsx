/**
 * Payments tab — real payments via usePaymentsByClient (Phase 101-04).
 *
 * READ-ONLY: no refund/edit affordance here (T-101-13-READONLY).
 * Money actions live on the membership lifecycle (101-03 scope).
 *
 * Per-tab inline error/empty states (UI-SPEC §Surface 1):
 *   - loading: Skeleton rows
 *   - error: inline <PageError onRetry/> (NOT full-page)
 *   - empty: inline EmptyState (no icon tile) «Нет платежей» / «История платежей клиента появятся здесь.»
 *   - data: real PaymentData rows (amountKopecks, method, receivedAt; refundOf rows marked)
 *
 * T-101-12-IDOR: uses the scoped /by-client/{client_id} path; 403 collapses to per-tab error.
 * T-101-13-READONLY: no write affordance rendered.
 * T-101-14-PII-ERR: error rendered via PageError curated copy.
 */
import { usePaymentsByClient } from '@/features/payments/api';
import { formatRub, formatDateRu, formatTime } from '@/lib/format';
import { PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';
import { CreditCard, Undo2 } from '@/components/icons';
import { Card, CardHead } from './shared';
import type { PaymentData } from '@/features/payments/schemas';

const METHOD_LABEL: Record<string, string> = {
  cash: 'Наличные',
  card: 'Карта',
  online: 'Онлайн',
  transfer: 'Перевод',
};

function PaymentRow({ item }: { item: PaymentData }) {
  const isRefund = !!item.refundOf;
  const Icon = isRefund ? Undo2 : CreditCard;
  const methodLabel = METHOD_LABEL[item.method] ?? item.method;
  const dateLabel = `${formatDateRu(item.receivedAt, 'd MMM yyyy')} · ${formatTime(item.receivedAt)}`;

  return (
    <div className="grid grid-cols-[32px_1fr_auto] items-center gap-3.5 border-t-[0.5px] border-border px-4 py-3 first:border-t-0 sm:px-5">
      <span
        className={cn(
          'grid size-8 place-items-center rounded-[10px]',
          isRefund ? 'bg-danger-soft text-danger' : 'bg-surface-3 text-fg',
        )}
      >
        <Icon className="size-[14px]" strokeWidth={2.2} />
      </span>
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">
          {isRefund ? 'Возврат' : methodLabel}
        </div>
        <div className="mt-0.5 truncate text-[11.5px] tabular-nums text-fg-subtle">{dateLabel}</div>
      </div>
      <div
        className={cn(
          'whitespace-nowrap text-sm font-bold tabular-nums tracking-[-0.2px]',
          isRefund && 'text-danger',
        )}
      >
        {isRefund ? '−' : '+'}
        {formatRub(item.amountKopecks)}
      </div>
    </div>
  );
}

export function PaymentsTab({ clientId }: { clientId: string }) {
  const { data, isPending, isError, refetch } = usePaymentsByClient(clientId);

  if (isPending) {
    return (
      <Card className="px-4 py-4 sm:px-5">
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <PageError onRetry={() => void refetch()} />
      </Card>
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <Card>
        <EmptyState
          className="py-12"
          title="Нет платежей"
          message="История платежей клиента появится здесь."
        />
      </Card>
    );
  }

  return (
    <Card>
      <CardHead title="История платежей" sub={`${items.length} операций`} />
      <div className="border-t-[0.5px] border-border">
        {items.map((item) => (
          <PaymentRow key={item.id} item={item} />
        ))}
      </div>
    </Card>
  );
}
