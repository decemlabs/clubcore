/**
 * CashboxPage — owner-only cash ledger (Phase 103-03, extended Phase 112-03, 116-03).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls when navigating to /cashbox.
 *
 * Real data: GET /api/v1/payments via useCashbox(filter).
 * KPIs: client-side sums — Приход / Возвраты / Нетто.
 * Daily totals: computeDailyTotals via useCashbox.
 * ShiftDrawer removed — no shift endpoint.
 * Phase 112: «Оформить возврат» row action wired (owner-only REF-01).
 * Phase 116: «Экспорт CSV» button (owner-only EXP-01, payments.csv).
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { useCashbox } from '@/features/cashbox/api';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { downloadCsv } from '@/api/csv';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Lock, Wallet, Download, Loader2 } from '@/components/icons';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { CashboxPageHead } from './components/CashboxPageHead';
import { CashboxKpis } from './components/CashboxKpis';
import { TransactionsCard } from './components/TransactionsCard';
import { mskTodayISO, mskDaysAgoISO } from '@/lib/format';

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
  // Derive role for TransactionsCard (role prop threads down for can() gating)
  const session = useSession();
  const role = session.data?.role ?? 'reception';

  const [receivedFrom, setReceivedFrom] = useState(() => mskDaysAgoISO(29));
  const [receivedTo, setReceivedTo] = useState(() => mskTodayISO());
  const [isDownloading, setIsDownloading] = useState(false);

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

  async function handleExport() {
    setIsDownloading(true);
    try {
      await downloadCsv(
        '/api/v1/reports/payments.csv',
        `payments-${receivedFrom}-${receivedTo}.csv`,
        { fromDate: receivedFrom, toDate: receivedTo },
      );
    } catch {
      toast.error('Не удалось экспортировать файл. Попробуйте ещё раз.');
    } finally {
      setIsDownloading(false);
    }
  }

  // Owner-gated export button (hidden for reception — not disabled)
  const exportButton = can(role, 'view', 'finance') ? (
    <Button
      variant="outline"
      size="sm"
      disabled={isDownloading}
      onClick={() => void handleExport()}
      aria-busy={isDownloading}
      aria-label="Экспорт CSV"
      className="h-[34px] shrink-0 gap-1.5 rounded-full px-3.5 text-[13px] font-semibold"
    >
      {isDownloading ? (
        <Loader2 className="size-3.5 animate-spin" />
      ) : (
        <Download className="size-3.5" strokeWidth={2.2} />
      )}
      <span className="max-sm:hidden">Экспорт CSV</span>
    </Button>
  ) : undefined;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <CashboxPageHead
        from={receivedFrom}
        to={receivedTo}
        total={total}
        dateRangePicker={
          <DateRangePicker from={receivedFrom} to={receivedTo} onChange={handleRangeChange} />
        }
        exportButton={exportButton}
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
        <TransactionsCard items={items} dailyTotals={dailyTotals} role={role} />
      )}
    </div>
  );
}
