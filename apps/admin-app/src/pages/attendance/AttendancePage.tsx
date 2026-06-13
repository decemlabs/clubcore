/**
 * AttendancePage — страница «Посещаемость» (Phase 103-02 ATT-01).
 *
 * Wired to real GET /api/v1/visits via useAttendanceList from @/features/attendance/api.
 *
 * Scope reduction (UI-SPEC §1.5):
 * The 9 mock-only analytics widgets (HeatmapCard, PeakHero, HourCurveCard, FrequencyCard,
 * DayOfWeekCard, DurationCard, CohortCard, AnomalyCards, RiskList) are NOT rendered here.
 * Files remain on disk for future wiring. No backend in Phase 103 scope.
 *
 * Renders: page head (date-range picker + check-in button) + total KPI + real visits list with pagination.
 * Roles: reception + owner (ATT-01 — NOT owner-only).
 */
import { useState } from 'react';
import { useAttendanceList } from '@/features/attendance/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { AttendancePageHead } from './components/AttendancePageHead';
import { VisitsList } from './components/VisitsList';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { Activity } from '@/components/icons';
import { formatDateRu, mskTodayISO, mskDaysAgoISO } from '@/lib/format';

// ---------------------------------------------------------------------------
// Константы фильтра
// ---------------------------------------------------------------------------

const PAGE_SIZE = 25;

// Дефолтный диапазон: последние 30 дней (today – 29 дней).
// Используется для вычисления hasFilter — если пользователь не менял даты,
// показываем «Визитов пока нет» вместо «Нет визитов (отфильтровано)».
const DEFAULT_FROM = mskDaysAgoISO(29);
const DEFAULT_TO = mskTodayISO();

// ---------------------------------------------------------------------------
// KPI — простая плитка с общим числом визитов
// ---------------------------------------------------------------------------

function TotalVisitsKpi({ total, from, to }: { total: number; from: string; to: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface px-4 py-3">
      <span className="grid size-9 place-items-center rounded-full bg-surface-3 text-fg-subtle">
        <Activity className="size-4" />
      </span>
      <div>
        <div className="text-[22px] font-bold tabular-nums tracking-[-0.5px]">{total}</div>
        <div className="text-[12px] text-fg-subtle">
          визитов · {formatDateRu(from, 'dd.MM.yy')} – {formatDateRu(to, 'dd.MM.yy')}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Страница
// ---------------------------------------------------------------------------

export function AttendancePage() {
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(DEFAULT_TO);
  const [page, setPage] = useState(1);

  const filter = { from, to, page, pageSize: PAGE_SIZE };

  const { data, isPending, isError, refetch } = useAttendanceList(filter);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  // hasFilter — true когда пользователь изменил диапазон по сравнению с дефолтным.
  // При дефолтном диапазоне и нулевых результатах показываем онбординговый стейт
  // «Визитов пока нет» вместо «Нет визитов за выбранный период».
  const hasFilter = from !== DEFAULT_FROM || to !== DEFAULT_TO;

  function handleRangeChange(nextFrom: string, nextTo: string) {
    setFrom(nextFrom);
    setTo(nextTo);
    setPage(1);
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <AttendancePageHead
        subtitle={`${formatDateRu(from, 'dd.MM.yy')} – ${formatDateRu(to, 'dd.MM.yy')}`}
        dateRangePicker={
          <DateRangePicker from={from} to={to} onChange={handleRangeChange} />
        }
      />

      <TotalVisitsKpi total={data.total} from={from} to={to} />

      <VisitsList
        items={data.items}
        total={data.total}
        page={data.page}
        pageSize={data.pageSize}
        hasFilter={hasFilter}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
