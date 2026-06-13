/**
 * FinancePage — owner-only 2-tab Finance screen (Phase 103-04).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls when navigating to /finance.
 *
 * Two real tabs:
 *   «Выручка»       — GET /api/v1/reports/revenue via useRevenueReport
 *   «Онлайн-платежи» — GET /api/v1/payments?method=online via useOnlinePayments
 *
 * Removed (no backend): «Неудачные», «Выплаты тренерам», CSV «Экспорт» button.
 *
 * Revenue chart: zero-filled via fillRevenueBuckets (no NaN); groupBy day|month toggle.
 * All-zero → inline EmptyState instead of flat-zero chart.
 * Signed netKopecks formats correctly (negative = refund-heavy period).
 */
import { useState } from 'react';
import { useSession } from '@/features/auth/api';
import { useRevenueReport, useOnlinePayments } from '@/features/finance/api';
import { can } from '@/shared/session/can';
import { fillRevenueBuckets } from '@/features/reports/utils';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { Lock, TrendingUp } from '@/components/icons';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { ChipGroup } from '@/components/modals/fields';
import { PageHeader } from '@/components/layout/PageHeader';
import { FinanceTabs } from './components/parts';
import { RevenueChart } from './components/RevenueChart';
import { OnlinePaymentsTable } from './components/OnlinePaymentsTable';
import type { Role } from '@/shared/session/types';
import type { RevenueBucket } from '@/features/reports/schemas';
import type { PaymentData } from '@/features/payments/schemas';
import { mskTodayISO, mskDaysAgoISO } from '@/lib/format';

const TABS = [
  { key: 'revenue', label: 'Выручка' },
  { key: 'online', label: 'Онлайн-платежи' },
];

const GROUP_BY_OPTIONS = [
  { value: 'day', label: 'По дням' },
  { value: 'month', label: 'По месяцам' },
];

const PAGE_SIZE = 25;

// ---------------------------------------------------------------------------
// Outer guard component — only calls useSession (Rules of Hooks safe)
// ---------------------------------------------------------------------------

export function FinancePage() {
  // RBAC guard: MUST be FIRST — before any data hook fires.
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  if (!can(role, 'view', 'reports')) {
    return (
      <EmptyState
        icon={Lock}
        title="Недостаточно прав"
        message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
        className="py-24"
      />
    );
  }

  return <FinancePageContent role={role} />;
}

// ---------------------------------------------------------------------------
// Inner content component — data hooks only called when RBAC guard passes
// ---------------------------------------------------------------------------

function FinancePageContent({ role }: { role: Role }) {
  const [fromDate, setFromDate] = useState(() => mskDaysAgoISO(29));
  const [toDate, setToDate] = useState(() => mskTodayISO());
  const [tab, setTab] = useState('revenue');
  const [groupBy, setGroupBy] = useState<'day' | 'month'>('day');
  const [page, setPage] = useState(1);

  // Revenue tab data — WR-04: pass role directly to avoid session double-waterfall
  const revenueQuery = useRevenueReport({ fromDate, toDate, groupBy }, role);

  // Online payments tab data (method='online' filter)
  const onlineFilter = { receivedFrom: fromDate, receivedTo: toDate, method: 'online' as const, page, pageSize: PAGE_SIZE };
  const onlineQuery = useOnlinePayments(onlineFilter, role);

  function handleRangeChange(from: string, to: string) {
    setFromDate(from);
    setToDate(to);
    setPage(1); // reset pagination on date range change
  }

  function handleGroupByChange(value: string) {
    setGroupBy(value as 'day' | 'month');
  }

  function handleTabChange(key: string) {
    setTab(key);
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Финансы"
        subtitle={`${fromDate} – ${toDate} · выручка и онлайн-платежи`}
        actions={
          <DateRangePicker from={fromDate} to={toDate} onChange={handleRangeChange} />
        }
      />

      <FinanceTabs tabs={TABS} value={tab} onChange={handleTabChange} />

      {tab === 'revenue' ? (
        <RevenueTab
          fromDate={fromDate}
          toDate={toDate}
          groupBy={groupBy}
          onGroupByChange={handleGroupByChange}
          revenueQuery={revenueQuery}
        />
      ) : null}

      {tab === 'online' ? (
        <OnlineTab
          onlineQuery={onlineQuery}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Revenue tab panel
// ---------------------------------------------------------------------------

interface RevenueQueryResult {
  data: { buckets: RevenueBucket[]; fromDate: string; toDate: string; groupBy: 'day' | 'month' } | undefined;
  isPending: boolean;
  isFetching: boolean;
  isError: boolean;
  refetch: () => unknown;
}

function RevenueTab({
  fromDate,
  toDate,
  groupBy,
  onGroupByChange,
  revenueQuery,
}: {
  fromDate: string;
  toDate: string;
  groupBy: 'day' | 'month';
  onGroupByChange: (v: string) => void;
  revenueQuery: RevenueQueryResult;
}) {
  const { data, isPending, isFetching, isError, refetch } = revenueQuery;

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  // Section skeleton on date re-fetch (keeps head + tabs visible).
  if (isFetching && !isPending) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  const buckets = data?.buckets ?? [];

  // Check all-zero after fill
  const filled = fillRevenueBuckets(buckets, fromDate, toDate, groupBy);
  const allZero = filled.every((b) => b.netKopecks === 0);

  return (
    <div className="flex flex-col gap-4">
      {/* groupBy toggle */}
      <div className="flex items-center gap-2">
        <ChipGroup
          options={GROUP_BY_OPTIONS}
          value={groupBy}
          onChange={onGroupByChange}
        />
      </div>

      {allZero ? (
        <EmptyState
          icon={TrendingUp}
          title="Нет данных за этот период"
          message="В выбранном диапазоне нет транзакций."
          className="py-16"
        />
      ) : (
        <RevenueChart
          buckets={buckets}
          fromDate={fromDate}
          toDate={toDate}
          groupBy={groupBy}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Online payments tab panel
// ---------------------------------------------------------------------------

interface OnlineQueryResult {
  data: { items: PaymentData[]; total: number; page: number; pageSize: number } | undefined;
  isPending: boolean;
  isFetching: boolean;
  isError: boolean;
  refetch: () => unknown;
}

function OnlineTab({
  onlineQuery,
  page,
  pageSize,
  onPageChange,
}: {
  onlineQuery: OnlineQueryResult;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const { data, isPending, isFetching, isError, refetch } = onlineQuery;

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  // Section skeleton on date/page re-fetch.
  if (isFetching && !isPending) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  if (items.length === 0) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="Нет данных за этот период"
        message="В выбранном диапазоне нет транзакций."
        className="py-16"
      />
    );
  }

  return (
    <OnlinePaymentsTable
      items={items}
      total={total}
      page={page}
      pageSize={pageSize}
      onPageChange={onPageChange}
    />
  );
}
