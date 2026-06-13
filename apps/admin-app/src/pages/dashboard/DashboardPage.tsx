import { useDashboard } from '@/features/dashboard/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { PageHead } from './components/PageHead';
import { KpiStrip } from './components/KpiStrip';
import { OccupancyHours } from './components/OccupancyHours';
import { OccupancyNow } from './components/OccupancyNow';
import { ScheduleToday } from './components/ScheduleToday';
import { ExpiringMemberships } from './components/ExpiringMemberships';
import { RevenueChart } from './components/RevenueChart';
import { TopTrainers } from './components/TopTrainers';
import { ClientMessages } from './components/ClientMessages';
import { ActivityFeed } from './components/ActivityFeed';

export function DashboardPage() {
  const { data, isPending, isError, refetch } = useDashboard();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const {
    overview,
    hourly,
    occupancy,
    schedule,
    expiring,
    revenue,
    topTrainers,
    messages,
    activity,
  } = data;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHead
        dateLabel={overview.dateLabel}
        greetingName={overview.greetingName}
        trainingsToday={overview.trainingsToday}
        expectedVisits={overview.expectedVisits}
        defaultPeriod={overview.defaultPeriod}
      />

      <KpiStrip kpis={overview.kpis} />

      {/* Заполняемость по часам + В клубе сейчас */}
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <OccupancyHours data={hourly} />
        <OccupancyNow data={occupancy} />
      </div>

      {/* Расписание + Истекающие абонементы */}
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <ScheduleToday
          sessions={schedule.sessions}
          nowLabel={schedule.nowLabel}
          total={schedule.total}
          done={schedule.done}
          live={schedule.live}
          planned={schedule.planned}
        />
        <ExpiringMemberships
          items={expiring.items}
          daysAhead={expiring.daysAhead}
          totalClients={expiring.totalClients}
        />
      </div>

      {/* Выручка + Топ тренеры + Обращения */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1.2fr_1fr_1fr]">
        <RevenueChart data={revenue} />
        <TopTrainers trainers={topTrainers} />
        <ClientMessages messages={messages} />
      </div>

      {/* Лента активности */}
      <ActivityFeed data={activity} />
    </div>
  );
}
