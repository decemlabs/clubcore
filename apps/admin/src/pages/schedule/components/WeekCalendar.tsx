/**
 * WeekCalendar — Phase 102-03 SCH-02.
 *
 * Updated to accept CalendarEvent[] (merged slots+bookings with type discriminator)
 * instead of the old mock SessionEvent[]. The days/now/colorByTrainerId props
 * still come from the parent SchedulePage.
 *
 * CalendarEvent is a superset of SessionEvent so layoutDay() works unchanged.
 * EventBlock receives each event's resolved color from the trainerColorMap.
 */
import { cn } from '@/lib/cn';
import { Card } from '@/components/layout/Card';
import type { DayState, ScheduleDay, SessionEvent } from '@/features/schedule/types';
import type { CalendarEvent } from './calendar-utils';
import { EventBlock } from './EventBlock';
import { BODY_HEIGHT, HOUR_PX, HOURS, layoutDay, toMinutes } from './calendar-utils';

const GRID = 'grid grid-cols-[56px_repeat(7,minmax(0,1fr))]';

const DAY_COL_BG: Record<DayState, string> = {
  today: 'bg-[color-mix(in_oklab,var(--primary)_6%,var(--surface))]',
  holiday: 'bg-[repeating-linear-gradient(45deg,var(--surface)_0_14px,var(--surface-2)_14px_18px)]',
  past: 'bg-surface-2',
  default: 'bg-surface',
};

function DayHeader({ day }: { day: ScheduleDay }) {
  const today = day.state === 'today';
  const past = day.state === 'past';
  const holiday = day.state === 'holiday';
  return (
    <div
      className={cn(
        'border-l-[0.5px] border-border px-3.5 py-3',
        today && 'bg-[color-mix(in_oklab,var(--primary)_10%,var(--surface-2))]',
        holiday && 'bg-[color-mix(in_oklab,var(--danger)_8%,var(--surface-2))]',
      )}
    >
      <div className="flex items-baseline gap-1.5">
        <span
          className={cn(
            'text-[11px] font-bold uppercase tracking-[0.5px]',
            today ? 'text-primary-deep dark:text-primary' : 'text-fg-subtle',
          )}
        >
          {day.dow}
        </span>
        <span
          className={cn(
            'text-[18px] font-bold tabular-nums',
            today ? 'text-primary-deep dark:text-primary' : past ? 'text-fg-subtle' : 'text-fg',
          )}
        >
          {day.num}
        </span>
      </div>
      <div
        className={cn(
          'mt-0.5 text-[11px]',
          holiday
            ? 'font-semibold text-danger'
            : today
              ? 'text-primary-deep dark:text-primary'
              : 'text-fg-subtle',
        )}
      >
        {day.sub}
      </div>
    </div>
  );
}

/** Недельный календарь: липкая шапка дней + часовая сетка с блоками-сессиями и линией «сейчас».
 *
 * Phase 102-03: events are CalendarEvent[] (merged slots+bookings).
 * onEventClick receives the CalendarEvent so SchedulePage can route by event.type.
 */
export function WeekCalendar({
  days,
  events,
  nowLabel,
  trainerColorMap,
  onEventClick,
}: {
  days: ScheduleDay[];
  events: CalendarEvent[];
  nowLabel: string;
  trainerColorMap: Map<string, string>;
  onEventClick?: (ev: CalendarEvent) => void;
}) {
  const layoutByDay = days.map((_, di) =>
    layoutDay(events.filter((e) => e.day === di) as SessionEvent[]),
  );
  const nowTop = (toMinutes(nowLabel) * HOUR_PX) / 60;

  return (
    <Card className="overflow-auto max-h-[calc(100vh-13rem)]">
      <div className="min-w-[880px]">
        {/* Липкая шапка дней */}
        <div className={cn(GRID, 'sticky top-0 z-20 border-b-[0.5px] border-border bg-surface-2')}>
          <div className="bg-surface-2" />
          {days.map((day, di) => (
            <DayHeader key={di} day={day} />
          ))}
        </div>

        {/* Тело: часовая ось + 7 колонок + сетка + линия «сейчас» */}
        <div className={cn(GRID, 'relative')} style={{ height: BODY_HEIGHT }}>
          {/* Ось времени */}
          <div className="relative border-r-[0.5px] border-border bg-surface">
            {HOURS.map((h, i) => (
              <span
                key={h}
                className="absolute right-2 -translate-y-1/2 text-[11px] font-semibold tabular-nums text-fg-subtle"
                style={{ top: i * HOUR_PX }}
              >
                {h}:00
              </span>
            ))}
          </div>

          {/* Колонки дней */}
          {days.map((day, di) => (
            <div
              key={di}
              className={cn('relative border-l-[0.5px] border-border', DAY_COL_BG[day.state])}
            >
              {layoutByDay[di]!.map((item) => {
                const calEv = item.ev as CalendarEvent;
                return (
                  <EventBlock
                    key={item.ev.id}
                    item={item}
                    color={
                      calEv.trainerColor ??
                      trainerColorMap.get(calEv.trainerId ?? item.ev.trainer) ??
                      '#999'
                    }
                    onClick={onEventClick ? (ev) => onEventClick(ev as CalendarEvent) : undefined}
                  />
                );
              })}
            </div>
          ))}

          {/* Часовые линии (поверх колонок, под событиями) */}
          <div className="pointer-events-none absolute inset-y-0 left-[56px] right-0 z-[1]">
            {HOURS.map((h, i) => (
              <div
                key={h}
                className="absolute inset-x-0 border-t border-dashed border-border/70"
                style={{ top: i * HOUR_PX }}
              />
            ))}
          </div>

          {/* Линия «сейчас» */}
          <div
            className="pointer-events-none absolute left-[56px] right-0 z-[8] h-0.5 bg-danger shadow-[0_0_8px_rgba(220,38,38,0.5)]"
            style={{ top: nowTop }}
          >
            <span className="absolute -left-[5px] top-1/2 size-2.5 -translate-y-1/2 rounded-full bg-danger" />
            <span className="absolute left-2 top-1/2 -translate-y-1/2 rounded bg-danger px-1.5 py-px text-[10.5px] font-bold tabular-nums text-white">
              {nowLabel}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}
