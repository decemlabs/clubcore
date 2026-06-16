import { ROUTES } from '@/app/routes';
import { Calendar } from '@/components/icons';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageError } from '@/components/feedback/PageState';
import { Skeleton } from '@/components/ui/skeleton';
import { formatTime } from '@/lib/format';
import type { BookingData } from '@/features/bookings/schemas';
import { CardLink, DashboardCard } from './shared';

interface ScheduleTodayProps {
  items: BookingData[];
  total: number;
  isPending: boolean;
  isError: boolean;
  refetch: () => void;
}

function BookingRow({ booking, showBorder }: { booking: BookingData; showBorder: boolean }) {
  const startTime = booking.slot?.startTime ? formatTime(booking.slot.startTime) : '—';
  const endTime = booking.slot?.endTime ? formatTime(booking.slot.endTime) : '';
  const trainerName = booking.slot?.trainerFullName ?? '—';
  const clientName = booking.clientFullName ?? '—';
  const planName = booking.ptPackage?.planName ?? 'PT';
  const statusLabel: Record<BookingData['status'], string> = {
    confirmed: 'Подтверждено',
    cancelled: 'Отменено',
    no_show: 'Не явился',
    completed: 'Завершено',
  };
  const label = statusLabel[booking.status];
  const isLive = booking.status === 'confirmed';

  return (
    <div
      className={`grid grid-cols-[72px_1fr_auto] items-center gap-3 px-5 py-3${showBorder ? ' border-t-[0.5px] border-border' : ''}`}
    >
      <div className="tabular-nums leading-tight">
        <div className="text-[14px] font-[650] text-fg">
          {startTime}
          {endTime ? `–${endTime}` : ''}
        </div>
        <div className="mt-px text-[11px] text-fg-subtle">{planName}</div>
      </div>

      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold">{clientName}</div>
        <div className="mt-px truncate text-[11.5px] text-fg-muted">{trainerName}</div>
      </div>

      <span
        className={`whitespace-nowrap text-[11px] font-medium ${isLive ? 'text-primary-deep dark:text-primary' : 'text-fg-subtle'}`}
      >
        {label}
      </span>
    </div>
  );
}

export function ScheduleToday({ items, total, isPending, isError, refetch }: ScheduleTodayProps) {
  const confirmed = items.filter((b) => b.status === 'confirmed').length;
  const completed = items.filter((b) => b.status === 'completed').length;

  return (
    <DashboardCard
      title="Расписание тренировок · сегодня"
      subtitle={
        isPending || isError
          ? '—'
          : `${total} бронирований · ${confirmed} подтверждено · ${completed} завершено`
      }
      action={<CardLink to={ROUTES.schedule}>Все</CardLink>}
    >
      {isPending ? (
        <div className="flex flex-col gap-2 px-5 py-3">
          <Skeleton className="h-[46px] w-full rounded-xl" />
          <Skeleton className="h-[46px] w-full rounded-xl" />
          <Skeleton className="h-[46px] w-full rounded-xl" />
        </div>
      ) : isError ? (
        <PageError onRetry={refetch} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="Тренировок сегодня нет"
          message="Занятий в расписании не запланировано."
        />
      ) : (
        <div className="py-1">
          {items.map((booking, i) => (
            <BookingRow key={booking.id} booking={booking} showBorder={i > 0} />
          ))}
        </div>
      )}
    </DashboardCard>
  );
}
