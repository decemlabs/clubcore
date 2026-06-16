/**
 * OverviewTab — Phase 102-03 SCH-02.
 *
 * Today-schedule: wired to useBookingsByTrainer(trainerId, todayRange, 'confirmed').
 * Completes the Plan 102-02 TODO handoff. (UI-SPEC §7.1)
 *
 * Regulars section: no clean endpoint in Phase 102 — stays on mock.
 * // TODO Phase 104: wire regulars to real endpoint when available.
 *
 * Date handling: Europe/Moscow — compute today's start/end in local time,
 * never `new Date(dateOnlyString)` (DST risk per CLAUDE.md).
 */
import { startOfDay, endOfDay } from 'date-fns';
import { ROUTES } from '@/app/routes';
import { Initials } from '@/components/ui/initials';
import { CardLink } from '@/components/layout/Card';
import { trainerDetail } from '@/mocks/trainer-detail';
import { useBookingsByTrainer } from '@/features/bookings/api';
import { formatTime, formatDateRu } from '@/lib/format';
import { Skeleton } from '@/components/ui/skeleton';
import { Panel, PanelBody, PanelHead } from './shared';

interface Props {
  trainerId: string;
}

/** Returns today's range as ISO strings (using local time to match Moscow wall-clock). */
function todayRange(): { fromTime: string; toTime: string } {
  const now = new Date();
  // Use midnight start of today and midnight start of tomorrow
  const from = startOfDay(now);
  const to = endOfDay(now);
  return {
    fromTime: from.toISOString(),
    toTime: to.toISOString(),
  };
}

export function OverviewTab({ trainerId }: Props) {
  // Real booking data for today's schedule (UI-SPEC §7.1)
  const range = todayRange();
  const bookingsQuery = useBookingsByTrainer(trainerId, range, 'confirmed');

  // Regulars section stays on mock — no dedicated endpoint in Phase 102.
  // TODO Phase 104: wire regulars to real endpoint when available.
  const t = trainerDetail;

  const bookings = bookingsQuery.data?.items ?? [];
  const isLoading = bookingsQuery.isPending;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr] lg:items-start">
      {/* Today schedule — real data from useBookingsByTrainer */}
      <Panel>
        <PanelHead
          title="Расписание · сегодня"
          action={<CardLink to={ROUTES.schedule}>Всё расписание</CardLink>}
        />
        <PanelBody>
          {isLoading ? (
            /* Skeleton rows while loading */
            <div className="flex flex-col gap-2 py-2">
              {Array.from({ length: 3 }, (_, i) => (
                <div key={i} className="flex items-center gap-3 py-1.5">
                  <Skeleton className="size-8 rounded-full" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-3.5 w-3/4 rounded" />
                    <Skeleton className="h-3 w-1/2 rounded" />
                  </div>
                  <Skeleton className="h-3 w-16 rounded" />
                </div>
              ))}
            </div>
          ) : bookings.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
              <span className="text-[13.5px] font-semibold text-fg-muted">
                Нет записей на сегодня
              </span>
              <span className="text-[11.5px] text-fg-subtle">
                {formatDateRu(new Date(), 'd MMMM yyyy')}
              </span>
            </div>
          ) : (
            /* Booking rows */
            bookings.map((booking) => {
              const clientName = booking.clientFullName ?? 'Клиент';
              const initials = clientName
                .trim()
                .split(/\s+/)
                .slice(0, 2)
                .map((w) => (w.charAt(0) ?? '').toUpperCase())
                .join('');
              const slotStart = booking.slot?.startTime;
              const slotEnd = booking.slot?.endTime;
              const timeLabel =
                slotStart && slotEnd
                  ? `${formatTime(slotStart)}–${formatTime(slotEnd)}`
                  : '—';

              return (
                <div
                  key={booking.id}
                  className="flex items-center gap-2.5 border-b-[0.5px] border-border py-[9px] last:border-b-0"
                >
                  <Initials
                    initials={initials || '?'}
                    color="#2dd4a4"
                    className="size-8 text-[11.5px]"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-semibold">{clientName}</div>
                    {booking.ptPackage ? (
                      <div className="text-[11px] text-fg-subtle">
                        {booking.ptPackage.planName}
                      </div>
                    ) : null}
                  </div>
                  <div className="shrink-0 text-[12px] font-semibold tabular-nums text-fg-muted">
                    {timeLabel}
                  </div>
                </div>
              );
            })
          )}
        </PanelBody>
      </Panel>

      <div className="flex flex-col gap-4">
        {/* Regulars — stays on mock, TODO Phase 104 */}
        <Panel>
          <PanelHead
            title="Постоянные клиенты"
            action={
              <span className="rounded-full bg-surface-3 px-[7px] py-px text-[11px] font-bold tabular-nums text-fg-muted">
                {t.regularsCount}
              </span>
            }
          />
          <PanelBody>
            {/* TODO Phase 104: wire regulars to real endpoint when available */}
            {t.regulars.map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 border-b-[0.5px] border-border py-[9px] last:border-b-0"
              >
                <Initials initials={c.initials} color={c.color} className="size-8 text-[11.5px]" />
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold">{c.name}</div>
                  {c.sub ? <div className="text-[11px] text-fg-subtle">{c.sub}</div> : null}
                </div>
              </div>
            ))}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
