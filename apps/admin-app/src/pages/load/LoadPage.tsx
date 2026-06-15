/**
 * LoadPage — owner-only visits aggregate + advanced analytics (Phase 103-03, Phase 115-03).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls when navigating to /load.
 *
 * Real data:
 *   - GET /api/v1/reports/visits via useLoad(query) — heatmap + DayOfWeek/PeakHour/Frequency
 *   - GET /api/v1/reports/load/now via useLoadNow(role) — live headcount counter (Phase 115)
 *   - GET /api/v1/reports/cohort via useCohortReport — cohort retention grid (Phase 115)
 *   - GET /api/v1/reports/anomaly via useVisitAnomaly — anomaly chart (Phase 115)
 *   - GET /api/v1/reports/at-risk via useAtRiskMembers — at-risk members (Phase 115)
 *
 * LiveNowCard: wired to useLoadNow — omitted silently on error (no alarming UX for approximation).
 * T-115-F3: shows approximation sub-label "Оценка присутствующих · окно N мин".
 */
import { useState } from 'react';
import { useLoad, useLoadNow, useCohortReport, useVisitAnomaly, useAtRiskMembers } from '@/features/load/api';
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
import { LiveNowCard } from './components/LiveNowCard';
import { DayOfWeekCard } from './components/DayOfWeekCard';
import { PeakHourCard } from './components/PeakHourCard';
import { FrequencyCard } from './components/FrequencyCard';
import { DurationPlaceholderCard } from './components/DurationPlaceholderCard';
import { CohortRetentionCard } from './components/CohortRetentionCard';
import { VisitAnomalyCard } from './components/VisitAnomalyCard';
import { AtRiskWidget } from './components/AtRiskWidget';
import { mskTodayISO, mskDaysAgoISO, formatTime } from '@/lib/format';
import type { LiveData } from '@/features/load/types';
import type { Role } from '@/shared/session/types';

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

  return <LoadPageContent role={role} />;
}

function LoadPageContent({ role }: { role: Role }) {
  const [fromDate, setFromDate] = useState(() => mskDaysAgoISO(29));
  const [toDate, setToDate] = useState(() => mskTodayISO());

  const query = { fromDate, toDate };
  const { data, isPending, isFetching, isError, refetch } = useLoad(query, role);

  // Phase 115: advanced analytics hooks (all owner-gated internally via can())
  const { data: liveNowData, isError: liveNowError } = useLoadNow(role);
  const { data: cohortData, isPending: cohortPending, isError: cohortError } = useCohortReport(
    { cohortMonths: 6 },
    role,
  );
  const { data: anomalyData, isPending: anomalyPending, isError: anomalyError } = useVisitAnomaly(
    {},
    role,
  );
  const { data: atRiskData, isPending: atRiskPending, isError: atRiskError } = useAtRiskMembers(role);

  // Map LoadNowData → LiveData (single "Зал" zone; no real capacity from endpoint)
  const liveData: LiveData | undefined =
    !liveNowError && liveNowData
      ? {
          time: formatTime(liveNowData.asOf),
          current: liveNowData.count,
          capacity: 0, // capacity not provided by endpoint — meter shows 0%
          meterPct: 0,
          filledPct: `${liveNowData.count}`,
          dayVisits: liveNowData.count,
          zones: [
            {
              name: 'Зал',
              metaStrong: '',
              metaRest: `Оценка присутствующих · окно ${liveNowData.windowMinutes} мин`,
              barPct: 0,
              tone: 'accent' as const,
              pct: `${liveNowData.count}`,
            },
          ],
        }
      : undefined;

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

      {/* LiveNowCard — wired to useLoadNow; omitted silently on error (T-115-F3). */}
      {liveData ? <LiveNowCard data={liveData} /> : null}

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
        <>
          <LoadHeatmapCard hourly={hourly} daily={daily} />
          <section aria-label="Дополнительная аналитика" className="flex flex-col gap-4">
            <DayOfWeekCard daily={daily} />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <PeakHourCard hourly={hourly} />
              <FrequencyCard daily={daily} />
            </div>
            <DurationPlaceholderCard />
          </section>
        </>
      )}

      {/* Phase 115: Расширенная аналитика — owner-only advanced analytics section.
          Rendered independently from the visits range section so it always shows
          regardless of the visits all-zero state. */}
      <section aria-label="Расширенная аналитика" className="flex flex-col gap-4">
        <CohortRetentionCard data={cohortData} isPending={cohortPending} isError={cohortError} />
        <VisitAnomalyCard data={anomalyData} isPending={anomalyPending} isError={anomalyError} />
        <AtRiskWidget data={atRiskData} isPending={atRiskPending} isError={atRiskError} />
      </section>
    </div>
  );
}
