/**
 * CashboxPage — owner-only cash ledger (Phase 103-03).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls when navigating to /cashbox.
 *
 * Real data: GET /api/v1/payments via useCashbox(filter).
 * KPIs: client-side sums — Приход / Возвраты / Нетто.
 * Daily totals: computeDailyTotals via useCashbox.
 * ShiftDrawer removed — no shift endpoint.
 * «Оформить возврат» removed from TransactionsCard — no /payments refund endpoint.
 */
import { useState } from 'react';
import { useCashbox } from '@/features/cashbox/api';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { Lock, Wallet } from '@/components/icons';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { CashboxPageHead } from './components/CashboxPageHead';
import { CashboxKpis } from './components/CashboxKpis';
import { TransactionsCard } from './components/TransactionsCard';

function subtractDays(date: Date, days: number): string {
  const d = new Date(date);
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function CashboxPage() {
  // RBAC guard: MUST be FIRST — before any data hook fires.
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  if (!can(role, 'view', 'payments')) {
    return (
      <EmptyState
        icon={Lock}
        title="Недостаточно прав"
        message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
        className="py-24"
      />
    );
  }

  return <CashboxPageContent />;
}

function CashboxPageContent() {
  const today = todayISO();
  const [receivedFrom, setReceivedFrom] = useState(() => subtractDays(new Date(), 29));
  const [receivedTo, setReceivedTo] = useState(today);

  const filter = { receivedFrom, receivedTo, pageSize: 100 };
  const { data, dailyTotals, isPending, isFetching, isError, refetch } = useCashbox(filter);

  // Initial full-page skeleton.
  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  // Client-side KPI sums from the current page.
  const items = data?.items ?? [];
  const prikhod = items.reduce((s, p) => (p.amountKopecks > 0 ? s + p.amountKopecks : s), 0);
  const vozvrat = items.reduce((s, p) => (p.amountKopecks < 0 ? s + Math.abs(p.amountKopecks) : s), 0);
  const netto = prikhod - vozvrat;
  const total = data?.total ?? 0;

  function handleRangeChange(from: string, to: string) {
    setReceivedFrom(from);
    setReceivedTo(to);
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <CashboxPageHead
        from={receivedFrom}
        to={receivedTo}
        total={total}
        dateRangePicker={
          <DateRangePicker from={receivedFrom} to={receivedTo} onChange={handleRangeChange} />
        }
      />

      <CashboxKpis prikhod={prikhod} vozvrat={vozvrat} netto={netto} />

      {/* Section skeleton on date re-fetch (keeps head+KPIs visible). */}
      {isFetching && !isPending ? (
        <Skeleton className="h-[400px] w-full rounded-xl" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title="Нет операций"
          message="За выбранный период платежей не найдено."
          className="py-24"
        />
      ) : (
        <TransactionsCard items={items} dailyTotals={dailyTotals} />
      )}
    </div>
  );
}
