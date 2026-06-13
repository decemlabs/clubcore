/**
 * ReportsPage — owner-only 4-tab reports screen (Phase 104-03 RPT-02).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls when navigating to /reports.
 *
 * Four real tabs:
 *   «Выручка»   — GET /api/v1/reports/revenue via useRevenueReport (P103)
 *   «Клиенты»   — GET /api/v1/reports/clients via useClientsReport (P104-01)
 *   «Посещения» — GET /api/v1/reports/visits via useVisitsReport (P103)
 *   «Тренеры»   — GET /api/v1/reports/trainers via useTrainersReport (P104-01)
 *
 * Per-tab «Экспорт CSV» button: idle / downloading / error states.
 * CSV error → Russian toast (UI-SPEC §2.2).
 *
 * Threat T-104-06: reception Lock-EmptyState early-return fires BEFORE any hook.
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { useSession } from '@/features/auth/api';
import {
  useRevenueReport,
  useVisitsReport,
  useClientsReport,
  useTrainersReport,
} from '@/features/reports/api';
import { can } from '@/shared/session/can';
import { downloadCsv } from '@/api/csv';
import { fillRevenueBuckets } from '@/features/reports/utils';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { Lock, Download, Loader2, TrendingUp, BarChart3, Users, UserCog } from '@/components/icons';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { ChipGroup } from '@/components/modals/fields';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/layout/Card';
import { RevenueChart } from '@/pages/finance/components/RevenueChart';
import { LoadHeatmapCard } from '@/pages/load/components/LoadHeatmapCard';
import { fillHourlyBuckets, fillDailyBuckets } from '@/features/reports/utils';
import { mskTodayISO, mskDaysAgoISO, formatRub } from '@/lib/format';
import type { Role } from '@/shared/session/types';
import type {
  TrainerRow,
  RevenueBucket,
  VisitsReportDailyBucket,
  VisitsReportHourlyBucket,
} from '@/features/reports/schemas';

// ---------------------------------------------------------------------------
// Tab config
// ---------------------------------------------------------------------------

type TabKey = 'revenue' | 'clients' | 'visits' | 'trainers';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'revenue', label: 'Выручка' },
  { key: 'clients', label: 'Клиенты' },
  { key: 'visits', label: 'Посещения' },
  { key: 'trainers', label: 'Тренеры' },
];

const GROUP_BY_OPTIONS = [
  { value: 'day', label: 'По дням' },
  { value: 'month', label: 'По месяцам' },
];

// ---------------------------------------------------------------------------
// CSV export button — shared anatomy (idle / downloading / error)
// ---------------------------------------------------------------------------

function CsvButton({
  onClick,
}: {
  onClick: () => Promise<void>;
}) {
  const [downloading, setDownloading] = useState(false);

  async function handleClick() {
    if (downloading) return;
    setDownloading(true);
    try {
      await onClick();
    } catch {
      toast.error('Не удалось скачать файл', {
        description: 'Проверьте соединение и попробуйте ещё раз.',
      });
    } finally {
      setDownloading(false);
    }
  }

  return (
    <button
      type="button"
      disabled={downloading}
      onClick={() => void handleClick()}
      className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-border bg-surface px-[14px] text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-75"
    >
      {downloading ? (
        <Loader2 className="size-[14px] animate-spin text-fg-subtle" />
      ) : (
        <Download className="size-[14px]" />
      )}
      Экспорт CSV
    </button>
  );
}

// ---------------------------------------------------------------------------
// Outer guard component — only calls useSession (Rules of Hooks safe)
// ---------------------------------------------------------------------------

export function ReportsPage() {
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

  return <ReportsPageContent role={role} />;
}

// ---------------------------------------------------------------------------
// Inner content component — data hooks only called when RBAC guard passes
// ---------------------------------------------------------------------------

function ReportsPageContent({ role }: { role: Role }) {
  const [fromDate, setFromDate] = useState(() => mskDaysAgoISO(29));
  const [toDate, setToDate] = useState(() => mskTodayISO());
  const [tab, setTab] = useState<TabKey>('revenue');
  const [groupBy, setGroupBy] = useState<'day' | 'month'>('day');

  // All 4 report hooks — all owner-gated via enabled:can() inside the hooks
  const revenueQuery = useRevenueReport({ fromDate, toDate, groupBy }, role);
  const clientsQuery = useClientsReport({ fromDate, toDate, within: 30 }, role);
  const visitsQuery = useVisitsReport({ fromDate, toDate }, role);
  const trainersQuery = useTrainersReport({ fromDate, toDate }, role);

  function handleRangeChange(from: string, to: string) {
    setFromDate(from);
    setToDate(to);
  }

  function handleTabChange(key: string) {
    setTab(key as TabKey);
  }

  // CSV download handlers per tab
  function handleRevenueCsv() {
    return downloadCsv(
      '/api/v1/reports/revenue.csv',
      `revenue-${fromDate}-${toDate}.csv`,
      { fromDate, toDate, groupBy },
    );
  }

  function handleClientsCsv() {
    return downloadCsv(
      '/api/v1/reports/clients.csv',
      `clients-${fromDate}-${toDate}.csv`,
      { fromDate, toDate, within: 30 },
    );
  }

  function handleVisitsCsv() {
    return downloadCsv(
      '/api/v1/reports/visits.csv',
      `visits-${fromDate}-${toDate}.csv`,
      { fromDate, toDate },
    );
  }

  function handleTrainersCsv() {
    return downloadCsv(
      '/api/v1/reports/trainers.csv',
      `trainers-${fromDate}-${toDate}.csv`,
      { fromDate, toDate },
    );
  }

  const csvHandlers: Record<TabKey, () => Promise<void>> = {
    revenue: handleRevenueCsv,
    clients: handleClientsCsv,
    visits: handleVisitsCsv,
    trainers: handleTrainersCsv,
  };

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Отчёты"
        subtitle="Аналитика по выручке, клиентам, посещениям и тренерам"
        actions={
          <DateRangePicker from={fromDate} to={toDate} onChange={handleRangeChange} />
        }
      />

      {/* Tab selector + CSV button row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TabsGroup tabs={TABS} value={tab} onChange={handleTabChange} />
        <CsvButton onClick={csvHandlers[tab]} />
      </div>

      {/* Tab panels */}
      {tab === 'revenue' ? (
        <RevenueTab
          fromDate={fromDate}
          toDate={toDate}
          groupBy={groupBy}
          onGroupByChange={(v) => setGroupBy(v as 'day' | 'month')}
          query={revenueQuery}
        />
      ) : null}

      {tab === 'clients' ? (
        <ClientsTab query={clientsQuery} />
      ) : null}

      {tab === 'visits' ? (
        <VisitsTab query={visitsQuery} fromDate={fromDate} toDate={toDate} />
      ) : null}

      {tab === 'trainers' ? (
        <TrainersTab query={trainersQuery} />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab selector component
// ---------------------------------------------------------------------------

function TabsGroup({
  tabs,
  value,
  onChange,
}: {
  tabs: { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="inline-flex max-w-full gap-1 self-start overflow-x-auto rounded-[11px] bg-surface-3 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={`inline-flex h-[34px] shrink-0 items-center gap-2 rounded-lg px-[15px] text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${active ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg'}`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Revenue tab
// ---------------------------------------------------------------------------

function RevenueTab({
  fromDate,
  toDate,
  groupBy,
  onGroupByChange,
  query,
}: {
  fromDate: string;
  toDate: string;
  groupBy: 'day' | 'month';
  onGroupByChange: (v: string) => void;
  query: {
    data: { buckets: RevenueBucket[]; fromDate: string; toDate: string; groupBy: 'day' | 'month' } | undefined;
    isPending: boolean;
    isFetching: boolean;
    isError: boolean;
    refetch: () => unknown;
  };
}) {
  const { data, isPending, isFetching, isError, refetch } = query;

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  // Section skeleton on date re-fetch (keeps head + tabs visible).
  if (isFetching && !isPending) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  const buckets = data?.buckets ?? [];
  const filled = fillRevenueBuckets(buckets, fromDate, toDate, groupBy);
  const allZero = filled.every((b) => b.netKopecks === 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <ChipGroup options={GROUP_BY_OPTIONS} value={groupBy} onChange={onGroupByChange} />
      </div>

      {allZero ? (
        <EmptyState
          icon={TrendingUp}
          title="Нет данных за этот период"
          message="В выбранном диапазоне нет транзакций."
          className="py-16"
        />
      ) : (
        <RevenueChart buckets={buckets} fromDate={fromDate} toDate={toDate} groupBy={groupBy} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Clients tab
// ---------------------------------------------------------------------------

function ClientsTab({
  query,
}: {
  query: {
    data: { activeCount: number; expiringCount: number; newClientsCount: number; withinDays: number } | undefined;
    isPending: boolean;
    isFetching: boolean;
    isError: boolean;
    refetch: () => unknown;
  };
}) {
  const { data, isPending, isFetching, isError, refetch } = query;

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  if (isFetching && !isPending) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  if (!data) {
    return (
      <EmptyState
        icon={Users}
        title="Нет данных"
        message="За выбранный период нет данных о клиентах."
        className="py-16"
      />
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <KpiCard
        label="Активные"
        value={String(data.activeCount)}
        sub="клиентов с действующим абонементом"
      />
      <KpiCard
        label="Истекают скоро"
        value={String(data.expiringCount)}
        sub={`истекают в течение ${data.withinDays} дней`}
      />
      <KpiCard
        label="Новые за период"
        value={String(data.newClientsCount)}
        sub="новых клиентов за выбранный диапазон"
      />
    </div>
  );
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card className="flex flex-col px-5 pb-4 pt-[18px]">
      <div className="text-[12.5px] font-medium text-fg-muted">{label}</div>
      <div className="mt-2.5 text-[36px] font-bold leading-[1.05] tracking-[-0.8px] tabular-nums">
        {value}
      </div>
      <div className="mt-2 text-[12px] text-fg-subtle">{sub}</div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Visits tab
// ---------------------------------------------------------------------------

function VisitsTab({
  query,
  fromDate,
  toDate,
}: {
  query: {
    data: {
      daily: VisitsReportDailyBucket[];
      hourly: VisitsReportHourlyBucket[];
      averagePerDay: number;
      fromDate: string;
      toDate: string;
    } | undefined;
    isPending: boolean;
    isFetching: boolean;
    isError: boolean;
    refetch: () => unknown;
  };
  fromDate: string;
  toDate: string;
}) {
  const { data, isPending, isFetching, isError, refetch } = query;

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  if (isFetching && !isPending) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  const hourly = fillHourlyBuckets(data?.hourly ?? []);
  const daily = fillDailyBuckets(data?.daily ?? [], fromDate, toDate);
  const totalVisits = daily.reduce((s, b) => s + b.count, 0);

  if (totalVisits === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="Нет данных за этот период"
        message="В выбранном диапазоне дат нет посещений."
        className="py-16"
      />
    );
  }

  return <LoadHeatmapCard hourly={hourly} daily={daily} />;
}

// ---------------------------------------------------------------------------
// Trainers tab
// ---------------------------------------------------------------------------

function TrainersTab({
  query,
}: {
  query: {
    data: { rows: TrainerRow[] } | undefined;
    isPending: boolean;
    isFetching: boolean;
    isError: boolean;
    refetch: () => unknown;
  };
}) {
  const { data, isPending, isFetching, isError, refetch } = query;

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  if (isFetching && !isPending) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  const rows = data?.rows ?? [];

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={UserCog}
        title="Нет данных о тренерах"
        message="За выбранный период данные о тренерах отсутствуют."
        className="py-16"
      />
    );
  }

  const maxRevenue = Math.max(...rows.map((r) => r.totalRevenueKopecks), 0);

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Тренеры"
        subtitle="Статистика за выбранный период"
      />
      {/* Table header */}
      <div className="grid grid-cols-[minmax(0,1fr)_60px_60px_60px_80px_100px] items-center border-b-[0.5px] border-border px-5 py-2 text-[11.5px] font-semibold uppercase tracking-[0.3px] text-fg-subtle max-md:hidden">
        <span>Тренер</span>
        <span className="text-right">Сессий</span>
        <span className="text-right">Часов</span>
        <span className="text-right">Клиентов</span>
        <span className="text-right">Загруженность</span>
        <span className="text-right">Выручка</span>
      </div>
      {rows.map((row, i) => (
        <ReportsTrainerRow key={row.trainerId} row={row} first={i === 0} maxRevenue={maxRevenue} />
      ))}
    </Card>
  );
}

// IN-03 fix: renamed from TrainerRow to ReportsTrainerRow to avoid name collision
// with the imported TrainerRow type from @/features/reports/schemas.
function ReportsTrainerRow({
  row,
  first,
  maxRevenue,
}: {
  row: TrainerRow;
  first: boolean;
  maxRevenue: number;
}) {
  const barPct = maxRevenue > 0 ? Math.round((row.totalRevenueKopecks / maxRevenue) * 100) : 0;
  return (
    <div
      className={`grid grid-cols-[minmax(0,1fr)_60px_60px_60px_80px_100px] items-center gap-3 px-5 py-3 max-md:grid-cols-[minmax(0,1fr)_80px] ${!first ? 'border-t-[0.5px] border-border' : ''}`}
    >
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold">{row.name}</div>
        {/* Mini bar */}
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-3">
          <div className="h-full rounded-full bg-primary" style={{ width: `${barPct}%` }} />
        </div>
      </div>
      <div className="text-right text-[13px] tabular-nums max-md:hidden">{row.sessionCount}</div>
      <div className="text-right text-[13px] tabular-nums max-md:hidden">{row.totalHours}</div>
      <div className="text-right text-[13px] tabular-nums max-md:hidden">{row.uniqueClients}</div>
      <div className="text-right text-[13px] tabular-nums max-md:hidden">{row.utilizationPct}%</div>
      <div className="text-right text-[14px] font-bold tabular-nums">
        {formatRub(row.totalRevenueKopecks / 100)}
      </div>
    </div>
  );
}
