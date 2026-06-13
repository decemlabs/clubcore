/**
 * LoadPage — owner-only visits aggregate (Phase 103-03).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls when navigating to /load.
 *
 * Real data: GET /api/v1/reports/visits via useLoad(query).
 * Zero-fill: hourly (24 pts) + daily (full range) via features/load/api.ts.
 * No NaN reaches the charts.
 *
 * LiveNowCard: HIDDEN — no real-time endpoint in Phase 103.
 * TODO Phase 104: wire LiveNow to real-time endpoint.
 */
import { useState } from 'react';
import { useLoad } from '@/features/load/api';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { Lock, BarChart3 } from '@/components/icons';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { LoadPageHead } from './components/LoadPageHead';
import { LoadKpis } from './components/LoadKpis';
import { LoadHeatmapCard } from './components/LoadHeatmapCard';
import { mskTodayISO, mskDaysAgoISO } from '@/lib/format';

// LiveNowCard intentionally omitted — TODO Phase 104: wire LiveNow to real-time endpoint.

export function LoadPage() {
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

  return <LoadPageContent />;
}

function LoadPageContent() {
  const [fromDate, setFromDate] = useState(() => mskDaysAgoISO(29));
  const [toDate, setToDate] = useState(() => mskTodayISO());

  const query = { fromDate, toDate };
  const { data, isPending, isFetching, isError, refetch } = useLoad(query);

  // Initial full-page skeleton.
  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  const hourly = data?.hourly ?? [];
  const daily = data?.daily ?? [];
  const averagePerDay = data?.averagePerDay ?? 0;
  const totalVisits = daily.reduce((s, b) => s + b.count, 0);

  // All-zero check: if no visits at all, show inline EmptyState instead of flat chart.
  const allZero = totalVisits === 0;

  function handleRangeChange(from: string, to: string) {
    setFromDate(from);
    setToDate(to);
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <LoadPageHead
        from={fromDate}
        to={toDate}
        dateRangePicker={
          <DateRangePicker from={fromDate} to={toDate} onChange={handleRangeChange} />
        }
      />

      <LoadKpis averagePerDay={averagePerDay} totalVisits={totalVisits} />

      {/* Section skeleton on date re-fetch (keeps head+KPIs visible). */}
      {isFetching && !isPending ? (
        <Skeleton className="h-[320px] w-full rounded-xl" />
      ) : allZero ? (
        <EmptyState
          icon={BarChart3}
          title="Нет данных за этот период"
          message="В выбранном диапазоне дат нет посещений."
          className="py-24"
        />
      ) : (
        <LoadHeatmapCard hourly={hourly} daily={daily} />
      )}
    </div>
  );
}
