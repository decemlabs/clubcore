/**
 * Dashboard landing page (Phase 104-02).
 *
 * Universal landing: both roles land on /.
 * Owner sees full analytics layout (KPI + Occupancy + Revenue + TopTrainers + Schedule + Expiring).
 * Reception sees ONLY operational widgets: ScheduleToday + ExpiringMemberships.
 *
 * Owner-only cards are NOT rendered for reception — not locked, not placeholdered — absent.
 * CR-01 fix: owner-only hooks live in DashboardOwnerSection which only MOUNTS when
 * isOwner === true → hooks NEVER instantiated for reception → zero owner-only API calls (T-104-04).
 *
 * ClientMessages: hidden for ALL roles (no staff-chat backend).
 * OccupancyNow: hidden for ALL roles (no real-time endpoint).
 * ActivityFeed: hidden for all roles — using EmptyState with link to /audit-log.
 */
import { useMemo } from 'react';
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
import type { Role } from '@/shared/session/types';
import type { BookingData } from '@/features/bookings/schemas';
import type { MembershipData } from '@/features/memberships/schemas';
import { PageHead } from './components/PageHead';
import { KpiStrip } from './components/KpiStrip';
import { OccupancyHours } from './components/OccupancyHours';
import { ScheduleToday } from './components/ScheduleToday';
import { ExpiringMemberships } from './components/ExpiringMemberships';
import { RevenueChart } from './components/RevenueChart';
import { TopTrainers } from './components/TopTrainers';

// ---------------------------------------------------------------------------
// Outer component — calls only both-role hooks; owner section mounts separately
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const { data: me } = useSession();
  const role = me?.role ?? 'reception';
  const isOwner = can(role, 'view', 'reports');

  // IN-04 fix: stable date value via useMemo — prevents refetch churn across renders.
  // Empty deps: intentionally locked to session-start day; reloading will pick up a new day.
  const today = useMemo(() => mskTodayISO(), []);

  // Both-role hooks — always fire for all roles
  const scheduleTodayQ = useScheduleToday(today);
  const expiringQ = useExpiringMemberships();

  const scheduleItems = scheduleTodayQ.data?.items ?? [];
  const scheduleTotal = scheduleTodayQ.data?.total ?? 0;
  const confirmedToday = scheduleItems.filter((b) => b.status === 'confirmed').length;
  const expiringItems = expiringQ.data?.items ?? [];

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHead fullName={me?.fullName} bookingsToday={confirmedToday} />

      {/* ── Owner-only analytics section ────────────────────────────────── */}
      {/* CR-01: DashboardOwnerSection only mounts when isOwner === true.   */}
      {/* Owner-only hooks live INSIDE it — never instantiated for reception. */}
      {isOwner && (
        <DashboardOwnerSection
          role={role}
          today={today}
          scheduleItems={scheduleItems}
          scheduleTotal={scheduleTotal}
          schedulePending={scheduleTodayQ.isPending}
          scheduleError={scheduleTodayQ.isError}
          scheduleRefetch={() => void scheduleTodayQ.refetch()}
          expiringItems={expiringItems}
          expiringPending={expiringQ.isPending}
          confirmedToday={confirmedToday}
        />
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

// ---------------------------------------------------------------------------
// Inner owner-only section — only mounts when isOwner === true (CR-01)
// Owner-only hooks (useRevenueReport / useVisitsReport / useClientsReport /
// useTrainersReport) are declared here so they NEVER register for reception.
// ---------------------------------------------------------------------------

interface OwnerSectionProps {
  role: Role;
  today: string;
  scheduleItems: BookingData[];
  scheduleTotal: number;
  schedulePending: boolean;
  scheduleError: boolean;
  scheduleRefetch: () => void;
  expiringItems: MembershipData[];
  expiringPending: boolean;
  confirmedToday: number;
}

function DashboardOwnerSection({
  role,
  today,
  scheduleItems,
  scheduleTotal,
  schedulePending,
  scheduleError,
  scheduleRefetch,
  expiringItems,
  expiringPending,
  confirmedToday,
}: OwnerSectionProps) {
  // IN-04 fix: stable date values frozen at first render of owner section.
  const from30 = useMemo(() => mskDaysAgoISO(29), []);
  // WR-04 fix: derive monthStart from MSK today string (not local Date methods).
  // today is already 'YYYY-MM-DD' in MSK — slice to 'YYYY-MM' and append '-01'.
  const monthStart = useMemo(() => today.slice(0, 7) + '-01', [today]);
  const monthName = useMemo(
    () =>
      // Use noon UTC on the first of the month to avoid any DST edge cases.
      new Date(monthStart + 'T12:00:00Z').toLocaleDateString('ru-RU', {
        month: 'long',
        year: 'numeric',
        timeZone: 'Europe/Moscow',
      }),
    [monthStart],
  );

  // CR-01 fix: owner-only hooks instantiated inside this inner component only.
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

  // CR-02 fix: extract today's revenue bucket only (not a 30-day sum).
  // The revenue query covers 30 days for the chart; find the bucket whose period === today.
  const todayBucket = revenueQ.data?.buckets.find((b) => b.period === today);
  const todayRevenue = todayBucket?.netKopecks ?? 0;

  return (
    <>
      <KpiStrip
        data={{
          netKopecks: todayRevenue,
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
        <ScheduleToday
          items={scheduleItems}
          total={scheduleTotal}
          isPending={schedulePending}
          isError={scheduleError}
          refetch={scheduleRefetch}
        />
      </div>

      {/* Expiring + Revenue + TopTrainers */}
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr_1fr]">
        <ExpiringMemberships
          items={expiringItems}
          isPending={expiringPending}
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
  );
}
