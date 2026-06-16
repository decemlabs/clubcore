/**
 * SchedulePage — Phase 102-03 SCH-02.
 *
 * Replaces the Phase 37 mock-data schedule with real API data:
 *  - useTrainerSlots (Plan 101) — fetches available trainer slots for the visible week.
 *  - useBookingsByWeek (Task 1) — fetches confirmed bookings in the same window.
 *  - mergeSlotBookings (calendar-utils) — produces CalendarEvent[] with type discriminator.
 *
 * Slot-click routing (UI-SPEC §3.1):
 *  - type='available' → BookingModal (book the slot).
 *  - type='booked'    → BookingDetailLoader → BookingDetailModal (view/cancel/complete).
 *  - type='time-off'/'cancelled' → no-op (EventBlock handles not-clickable).
 *
 * FAB: «Управление расписанием» shown ONLY for owner (can(role,'create','schedule-slots')).
 * Reception sees NO FAB.
 *
 * Data-states:
 *  - isPending (either query) → PageLoading
 *  - isError (either query) → PageError with combined refetch
 *  - slots.length === 0 → EmptyState variant per role
 *  - else → WeekCalendar
 *
 * Week navigation: weekOffset state (0 = current week). fromTime/toTime derived as ISO UTC.
 * Trainer filter: real trainerId or 'all'; filters CalendarEvent[] client-side.
 *
 * All copy Russian per project conventions. Dates Europe/Moscow per CLAUDE.md.
 */
import { useMemo, useState } from 'react';
import { startOfISOWeek, addWeeks, endOfISOWeek, format, addDays } from 'date-fns';
import { ru } from 'date-fns/locale';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { CalendarPlus, CalendarX, Plus } from '@/components/icons';
import { useTrainerSlots } from '@/features/schedule/api';
import { useBookingsByWeek } from '@/features/bookings/api';
import { useTrainers } from '@/features/trainers/api';
import { mergeSlotBookings, type CalendarEvent } from './components/calendar-utils';
import type { ScheduleDay, DayState } from '@/features/schedule/types';
import { SchedulePageHead, type CalView } from './components/SchedulePageHead';
import { ScheduleToolbar, type ScheduleFilters } from './components/ScheduleToolbar';
import { WeekCalendar } from './components/WeekCalendar';
import { BookingModal } from '@/components/modals/BookingModal';
import { BookingDetailLoader } from './components/BookingDetailLoader';
import { ScheduleManagementModal } from '@/components/modals/ScheduleManagementModal';

// ---------------------------------------------------------------------------
// Trainer color palette (deterministic, assigned by index from API list)
// ---------------------------------------------------------------------------

const TRAINER_PALETTE = [
  '#2dd4a4', // emerald (brand primary)
  '#60a5fa', // blue
  '#f472b6', // pink
  '#fb923c', // orange
  '#a78bfa', // violet
  '#34d399', // green
  '#fbbf24', // amber
  '#f87171', // red
  '#38bdf8', // sky
  '#c084fc', // purple
];

/** Build a stable trainerId → color map from the active trainer list. */
function buildColorMap(trainerIds: string[]): Map<string, string> {
  const map = new Map<string, string>();
  trainerIds.forEach((id, i) => {
    map.set(id, TRAINER_PALETTE[i % TRAINER_PALETTE.length] ?? '#888');
  });
  return map;
}

// ---------------------------------------------------------------------------
// Week date helpers (Europe/Moscow compatible; use ISO week Mon-Sun)
// ---------------------------------------------------------------------------

/** Get the Monday start of the week containing `ref`, at UTC midnight. */
function getWeekStart(ref: Date, offsetWeeks: number): Date {
  const base = startOfISOWeek(ref);
  return addWeeks(base, offsetWeeks);
}

/** Format ISO date string for API (e.g. '2026-06-15T00:00:00Z'). */
function toISO(d: Date): string {
  return d.toISOString();
}

/** Russian range label: «15–21 июня 2026» or «28 апр — 4 мая 2026». */
function weekRangeLabel(weekStart: Date): string {
  const weekEnd = endOfISOWeek(weekStart);
  const startMonth = format(weekStart, 'LLLL', { locale: ru });
  const endMonth = format(weekEnd, 'LLLL', { locale: ru });
  const year = format(weekEnd, 'yyyy');

  if (startMonth === endMonth) {
    return `${format(weekStart, 'd')}–${format(weekEnd, 'd')} ${startMonth} ${year}`;
  }
  return `${format(weekStart, 'd MMM', { locale: ru })} — ${format(weekEnd, 'd MMM', { locale: ru })} ${year}`;
}

const DOW_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

/** Build 7 ScheduleDay objects from a week start Date. */
function buildDays(weekStart: Date, todayMidnight: Date): ScheduleDay[] {
  return Array.from({ length: 7 }, (_, i) => {
    const day = addDays(weekStart, i);
    const isToday = day.toDateString() === todayMidnight.toDateString();
    const isPast = day < todayMidnight;
    const state: DayState = isToday ? 'today' : isPast ? 'past' : 'default';

    const num = format(day, 'd');
    const sub = isToday ? 'сегодня' : isPast ? 'завершено' : format(day, 'd MMMM', { locale: ru });

    return {
      dow: DOW_SHORT[i] ?? '',
      num,
      sub,
      state,
    };
  });
}

/** Get current «HH:MM» label for now-marker. */
function nowLabel(): string {
  const now = new Date();
  const hh = now.getHours().toString().padStart(2, '0');
  const mm = now.getMinutes().toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

// ---------------------------------------------------------------------------
// Modal state types
// ---------------------------------------------------------------------------

interface BookingSlotTarget {
  slotId: string;
  trainerId: string;
  trainerFullName: string;
  slotStartTime: string;
  slotEndTime: string;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function SchedulePage() {
  const sessionQuery = useSession();
  const role = sessionQuery.data?.role ?? 'reception';

  const [view, setView] = useState<CalView>('week');
  const [weekOffset, setWeekOffset] = useState(0);
  const [filters, setFilters] = useState<ScheduleFilters>({ trainer: 'all' });

  // Modal state
  const [bookingSlotTarget, setBookingSlotTarget] = useState<BookingSlotTarget | null>(null);
  const [selectedBookingId, setSelectedBookingId] = useState<string | null>(null);
  const [mgmtOpen, setMgmtOpen] = useState(false);

  // Compute visible week bounds
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const weekStart = useMemo(() => getWeekStart(today, weekOffset), [today, weekOffset]);
  const weekEnd = useMemo(() => {
    const end = endOfISOWeek(weekStart);
    // end of Sunday in UTC
    end.setHours(23, 59, 59, 999);
    return end;
  }, [weekStart]);

  const fromTime = toISO(weekStart);
  const toTime = toISO(weekEnd);
  const rangeLabel = weekRangeLabel(weekStart);

  // Data queries
  const trainersQuery = useTrainers({ active: true });
  const trainers = useMemo(() => trainersQuery.data?.items ?? [], [trainersQuery.data]);

  const trainerColorMap = useMemo(() => buildColorMap(trainers.map((t) => t.id)), [trainers]);

  const trainerNameMap = useMemo(
    () => new Map(trainers.map((t) => [t.id, t.fullName])),
    [trainers],
  );

  const selectedTrainerId = filters.trainer !== 'all' ? filters.trainer : undefined;

  const slotsQuery = useTrainerSlots({
    trainerId: selectedTrainerId,
    fromTime,
    toTime,
  });

  const bookingsQuery = useBookingsByWeek({
    trainerId: selectedTrainerId,
    fromTime,
    toTime,
  });

  // Calendar merge
  const calendarEvents = useMemo(() => {
    const slots = slotsQuery.data?.items ?? [];
    const bookings = bookingsQuery.data?.items ?? [];
    return mergeSlotBookings(slots, bookings, trainerColorMap, trainerNameMap, weekStart);
  }, [slotsQuery.data, bookingsQuery.data, trainerColorMap, trainerNameMap, weekStart]);

  // Build day headers
  const days = useMemo(() => buildDays(weekStart, today), [weekStart, today]);

  // Counts for page head
  const sessionsWeek = calendarEvents.filter((e) => e.type === 'booked').length;
  const plannedToday = calendarEvents.filter((e) => {
    const todayIndex = days.findIndex((d) => d.state === 'today');
    return e.day === todayIndex && e.type === 'booked';
  }).length;

  // Combined pending/error states
  const isPending = slotsQuery.isPending || bookingsQuery.isPending || trainersQuery.isPending;
  const isError = slotsQuery.isError || bookingsQuery.isError;

  const handleRetry = () => {
    void slotsQuery.refetch();
    void bookingsQuery.refetch();
  };

  // Event click routing
  const handleEventClick = (ev: CalendarEvent) => {
    if (ev.type === 'available' && ev.slotId && ev.trainerId) {
      setBookingSlotTarget({
        slotId: ev.slotId,
        trainerId: ev.trainerId,
        trainerFullName: ev.trainerFullName ?? trainerNameMap.get(ev.trainerId) ?? 'Тренер',
        slotStartTime: ev.slotStartTime ?? '',
        slotEndTime: ev.slotEndTime ?? '',
      });
    } else if (ev.type === 'booked' && ev.bookingId) {
      setSelectedBookingId(ev.bookingId);
    }
    // time-off / cancelled → no-op (EventBlock already disables click)
  };

  // Page head data shape (matches SchedulePageHead expectations)
  const headData = {
    rangeLabel,
    sessionsWeek,
    plannedToday,
  };

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={handleRetry} />;

  const slots = slotsQuery.data?.items ?? [];
  const isEmpty = slots.length === 0;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <SchedulePageHead data={headData} view={view} onViewChange={setView} />

      <ScheduleToolbar
        rangeLabel={rangeLabel}
        filters={filters}
        trainerColorMap={trainerColorMap}
        onChange={(patch) => setFilters((p) => ({ ...p, ...patch }))}
        onPrevWeek={() => setWeekOffset((n) => n - 1)}
        onNextWeek={() => setWeekOffset((n) => n + 1)}
        onToday={() => setWeekOffset(0)}
      />

      {isEmpty ? (
        <div className="flex min-h-[320px] items-center justify-center">
          {can(role, 'create', 'schedule-slots') ? (
            <EmptyState
              icon={CalendarPlus}
              title="Расписание пусто"
              message="Опубликуйте слоты или создайте шаблон расписания."
              action={
                <button
                  type="button"
                  onClick={() => setMgmtOpen(true)}
                  className="mt-1 rounded-full bg-fg px-5 py-2.5 text-[13px] font-semibold text-bg transition-colors hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
                >
                  Управление расписанием
                </button>
              }
            />
          ) : (
            <EmptyState
              icon={CalendarX}
              title="Нет слотов на эту неделю"
              message="На выбранной неделе слоты ещё не опубликованы."
            />
          )}
        </div>
      ) : (
        <WeekCalendar
          days={days}
          events={calendarEvents}
          nowLabel={nowLabel()}
          trainerColorMap={trainerColorMap}
          onEventClick={handleEventClick}
        />
      )}

      {/* Owner-only management FAB */}
      {can(role, 'create', 'schedule-slots') && (
        <button
          type="button"
          aria-label="Управление расписанием"
          onClick={() => setMgmtOpen(true)}
          className="fixed bottom-6 right-6 z-30 inline-flex items-center gap-2 rounded-full bg-fg px-4 py-3 text-[13px] font-semibold text-bg shadow-3 transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg max-lg:bottom-[calc(88px+env(safe-area-inset-bottom))] dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
        >
          <Plus className="size-4" strokeWidth={2.4} />
          <span className="max-sm:hidden">Управление расписанием</span>
        </button>
      )}

      {/* Schedule management modal (owner only) */}
      <ScheduleManagementModal open={mgmtOpen} onOpenChange={setMgmtOpen} role={role} />

      {/* Booking create modal (available slot click) */}
      {bookingSlotTarget && (
        <BookingModal
          slotId={bookingSlotTarget.slotId}
          trainerId={bookingSlotTarget.trainerId}
          trainerFullName={bookingSlotTarget.trainerFullName}
          slotStartTime={bookingSlotTarget.slotStartTime}
          slotEndTime={bookingSlotTarget.slotEndTime}
          open={!!bookingSlotTarget}
          onOpenChange={(open) => {
            if (!open) setBookingSlotTarget(null);
          }}
        />
      )}

      {/* Booking detail modal (booked slot click) */}
      {selectedBookingId && (
        <BookingDetailLoader
          bookingId={selectedBookingId}
          role={role}
          open={!!selectedBookingId}
          onOpenChange={(open) => {
            if (!open) setSelectedBookingId(null);
          }}
        />
      )}
    </div>
  );
}
