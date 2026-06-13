/**
 * Dashboard landing page (Phase 104-02).
 *
 * Universal landing: both roles land on /.
 * Owner sees full analytics layout (KPI + Occupancy + Revenue + TopTrainers + Schedule + Expiring).
 * Reception sees ONLY operational widgets: ScheduleToday + ExpiringMemberships.
 *
 * Owner-only cards are NOT rendered for reception — not locked, not placeholdered — absent.
 * This means their hooks NEVER mount for reception → zero owner-only API calls (T-104-04).
 *
 * ClientMessages: hidden for ALL roles (no staff-chat backend).
 * OccupancyNow: hidden for ALL roles (no real-time endpoint).
 * ActivityFeed: hidden for all roles — using EmptyState with link to /audit-log.
 */
import { Link } from 'react-router-dom';
import { useSession } from '@/features/auth/api';
import {
  useScheduleToday,
  useExpiringMemberships,
  useRevenueReport,
  useVisitsReport,
  useClientsReport,
  useTrainersReport,
} from '@/features/dashboard/api';
import { can } from '@/shared/session/can';
import { ROUTES } from '@/app/routes';
import { Activity } from '@/components/icons';
import { EmptyState } from '@/components/feedback/EmptyState';
import { mskTodayISO, mskDaysAgoISO } from '@/lib/format';
import { PageHead } from './components/PageHead';
import { KpiStrip } from './components/KpiStrip';
import { OccupancyHours } from './components/OccupancyHours';
import { ScheduleToday } from './components/ScheduleToday';
import { ExpiringMemberships } from './components/ExpiringMemberships';
import { RevenueChart } from './components/RevenueChart';
import { TopTrainers } from './components/TopTrainers';

export function DashboardPage() {
  const { data: me } = useSession();
  const role = me?.role ?? 'reception';
  const isOwner = can(role, 'view', 'reports');

  const today = mskTodayISO();
  const from30 = mskDaysAgoISO(29);

  // MSK first day of current month
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
  const monthName = now.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric', timeZone: 'Europe/Moscow' });

  // Both-role hooks (always fetched)
  const scheduleTodayQ = useScheduleToday(today);
  const expiringQ = useExpiringMemberships();

  // Owner-only hooks (only called when isOwner — each keeps enabled:can() gate)
  const revenueQ = useRevenueReport(
    { fromDate: from30, toDate: today, groupBy: 'day' },
    role,
  );
  const visitsQ = useVisitsReport(
    { fromDate: today, toDate: today },
    role,
  );
  const clientsQ = useClientsReport(
    { fromDate: from30, toDate: today, within: 7 },
    role,
  );
  const trainersQ = useTrainersReport(
    { fromDate: monthStart, toDate: today },
    role,
  );

  const scheduleItems = scheduleTodayQ.data?.items ?? [];
  const scheduleTotal = scheduleTodayQ.data?.total ?? 0;
  const confirmedToday = scheduleItems.filter((b) => b.status === 'confirmed').length;
  const expiringItems = expiringQ.data?.items ?? [];

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHead fullName={me?.fullName} bookingsToday={confirmedToday} />

      {/* ── Owner-only analytics section ────────────────────────────────── */}
      {isOwner && (
        <>
          <KpiStrip
            data={{
              netKopecks: revenueQ.data?.buckets.reduce(
                (s, b) => s + (b.netKopecks ?? 0),
                0,
              ),
              visitsToday: visitsQ.data?.daily.reduce((s, b) => s + b.count, 0),
              expiringCount: clientsQ.data?.expiringCount,
              bookingsToday: confirmedToday,
            }}
          />

          {/* Occupancy hours */}
          <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
            <OccupancyHours
              data={visitsQ.data}
              isPending={visitsQ.isPending}
            />
            {/* ScheduleToday — owner left slot replaced below; occupancy right slot */}
            <ScheduleToday
              items={scheduleItems}
              total={scheduleTotal}
              isPending={scheduleTodayQ.isPending}
              isError={scheduleTodayQ.isError}
              refetch={() => void scheduleTodayQ.refetch()}
            />
          </div>

          {/* Expiring + Revenue + TopTrainers */}
          <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr_1fr]">
            <ExpiringMemberships
              items={expiringItems}
              isPending={expiringQ.isPending}
            />
            <RevenueChart
              data={revenueQ.data}
              fromDate={from30}
              toDate={today}
              isPending={revenueQ.isPending}
            />
            <TopTrainers
              data={trainersQ.data}
              isPending={trainersQ.isPending}
              month={monthName}
            />
          </div>

          {/* OccupancyNow: hidden — no real-time endpoint */}
          {/* ClientMessages: hidden — no staff-chat backend */}

          {/* ActivityFeed: disabled — link to audit-log instead of expensive fetch */}
          <EmptyState
            icon={Activity}
            title="Активность"
            message="Доступна в журнале действий"
            action={
              <Link
                to={ROUTES.audit}
                className="mt-1 text-[13px] font-semibold text-primary-deep hover:underline dark:text-primary"
              >
                Перейти →
              </Link>
            }
            className="rounded-xl border-[0.5px] border-border bg-surface py-10 shadow-1"
          />
        </>
      )}

      {/* ── Both-role operational widgets ─────────────────────────────────── */}
      {!isOwner && (
        <>
          <ScheduleToday
            items={scheduleItems}
            total={scheduleTotal}
            isPending={scheduleTodayQ.isPending}
            isError={scheduleTodayQ.isError}
            refetch={() => void scheduleTodayQ.refetch()}
          />
          <ExpiringMemberships
            items={expiringItems}
            isPending={expiringQ.isPending}
          />
        </>
      )}
    </div>
  );
}
