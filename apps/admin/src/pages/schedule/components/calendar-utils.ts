/**
 * Геометрия и раскладка недельного календаря (вынесено из компонентов ради react-refresh).
 *
 * Phase 102-03: Added calendar event merge model and mergeSlotBookings() function.
 * CalendarEvent extends SessionEvent with a `type` discriminator:
 *   'available'  — slot with no booking (clickable → BookingModal)
 *   'booked'     — slot with a confirmed booking (clickable → BookingDetailModal)
 *   'cancelled'  — slot status=cancelled (inert, opacity-50)
 *   'time-off'   — time-off block (not clickable, diagonal-stripe)
 */
import type { SessionEvent } from '@/features/schedule/types';
import type { TrainerSlotData } from '@/features/schedule/schemas';
import type { BookingData } from '@/features/bookings/schemas';

// ---------------------------------------------------------------------------
// Calendar event model (Phase 102-03)
// ---------------------------------------------------------------------------

/** Type discriminator for merged calendar events. */
export type CalendarEventType = 'available' | 'booked' | 'cancelled' | 'time-off';

/** Extended SessionEvent that includes the merge discriminator and optional booking/slotId. */
export interface CalendarEvent extends SessionEvent {
  type: CalendarEventType;
  slotId?: string;
  bookingId?: string;
  trainerId?: string;
  trainerFullName?: string;
  slotStartTime?: string;
  slotEndTime?: string;
  /** Pre-resolved trainer color hex (from trainerColorMap at merge time). */
  trainerColor?: string;
}

// ---------------------------------------------------------------------------
// Merge function
// ---------------------------------------------------------------------------

/**
 * Merge trainer slots + bookings into calendar events for the visible week.
 *
 * Rules:
 *  - slot.status === 'booked' AND a confirmed booking exists for this slot → type='booked'
 *  - slot.status === 'active' with no confirmed booking → type='available'
 *  - slot.status === 'cancelled' → type='cancelled'
 *  - bookings with no matching slot (shouldn't happen, but defensive) → skipped
 *
 * Returns CalendarEvent[] which is a superset of SessionEvent[],
 * so existing WeekCalendar/EventBlock components receive compatible data.
 *
 * Unit-tested in calendar-utils.test.ts (T-102-BK-RACE coverage).
 */
export function mergeSlotBookings(
  slots: TrainerSlotData[],
  bookings: BookingData[],
  trainerColorMap: Map<string, string>,
  trainerNameMap: Map<string, string>,
  weekStart: Date,
): CalendarEvent[] {
  // Build lookup: slotId → confirmed booking
  const confirmedBySlot = new Map<string, BookingData>();
  for (const b of bookings) {
    if (b.status === 'confirmed') {
      confirmedBySlot.set(b.slotId, b);
    }
  }

  const events: CalendarEvent[] = [];

  for (const slot of slots) {
    const slotStart = new Date(slot.startTime);
    const slotEnd = new Date(slot.endTime);

    // Compute day index (0=Mon…6=Sun) relative to the week start
    const dayMs = slotStart.getTime() - weekStart.getTime();
    const dayIndex = Math.floor(dayMs / (24 * 60 * 60 * 1000));
    if (dayIndex < 0 || dayIndex > 6) continue;

    const startHHMM = `${pad(slotStart.getHours())}:${pad(slotStart.getMinutes())}`;
    const endHHMM = `${pad(slotEnd.getHours())}:${pad(slotEnd.getMinutes())}`;
    const durationMin = Math.round((slotEnd.getTime() - slotStart.getTime()) / 60_000);

    const trainerName = trainerNameMap.get(slot.trainerId) ?? 'Тренер';
    const trainerColor = trainerColorMap.get(slot.trainerId) ?? '#888';

    const booking = confirmedBySlot.get(slot.id);

    let type: CalendarEventType;
    if (slot.status === 'cancelled') {
      type = 'cancelled';
    } else if (booking != null || slot.status === 'booked') {
      type = 'booked';
    } else {
      type = 'available';
    }

    const event: CalendarEvent = {
      id: slot.id,
      day: dayIndex,
      start: startHHMM,
      end: endHHMM,
      durationMin,
      // Use trainer key as the trainer identifier (cast to TrainerKey for compatibility)
      trainer: slot.trainerId as SessionEvent['trainer'],
      kind: 'personal',
      state: slot.status === 'cancelled' ? 'cancelled' : type === 'booked' ? 'planned' : 'planned',
      who: booking?.clientFullName ?? (type === 'available' ? 'Свободно' : trainerName),
      hall: 1,
      type,
      slotId: slot.id,
      bookingId: booking?.id,
      trainerId: slot.trainerId,
      trainerFullName: trainerName,
      slotStartTime: slot.startTime,
      slotEndTime: slot.endTime,
      trainerColor,
    };

    events.push(event);
  }

  return events;
}

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

export const START_HOUR = 7;
export const END_HOUR = 23;
export const HOUR_PX = 56;
/** Часовые метки 7:00…23:00. */
export const HOURS = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);
/** Высота тела календаря (16 интервалов × 56px + хвост). */
export const BODY_HEIGHT = (END_HOUR - START_HOUR) * HOUR_PX + 16;

/** Минуты от 07:00 для строки «HH:MM». */
export function toMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return (h ?? 0) * 60 + (m ?? 0) - START_HOUR * 60;
}

export interface LaidOutEvent {
  ev: SessionEvent;
  top: number;
  height: number;
  /** Левый отступ в % (для раскладки пересекающихся событий в колонки). */
  leftPct: number;
  widthPct: number;
}

interface Span {
  ev: SessionEvent;
  start: number;
  end: number;
}

/**
 * Раскладка событий одного дня: пересекающиеся по времени делят колонку
 * по горизонтали (жадная упаковка в дорожки внутри кластера пересечений).
 */
export function layoutDay(events: SessionEvent[]): LaidOutEvent[] {
  const spans: Span[] = events.map((ev) => {
    const start = toMinutes(ev.start);
    return { ev, start, end: start + ev.durationMin };
  });
  spans.sort((a, b) => a.start - b.start || b.end - a.end);

  const out: LaidOutEvent[] = [];
  let cluster: Span[] = [];
  let clusterEnd = -1;

  const flush = () => {
    if (cluster.length === 0) return;
    const colEnds: number[] = [];
    const colOf = new Map<Span, number>();
    for (const span of cluster) {
      let col = colEnds.findIndex((end) => end <= span.start);
      if (col === -1) {
        col = colEnds.length;
        colEnds.push(span.end);
      } else {
        colEnds[col] = span.end;
      }
      colOf.set(span, col);
    }
    const cols = colEnds.length;
    for (const span of cluster) {
      const col = colOf.get(span) ?? 0;
      out.push({
        ev: span.ev,
        top: (span.start * HOUR_PX) / 60,
        height: (span.ev.durationMin * HOUR_PX) / 60,
        leftPct: (col / cols) * 100,
        widthPct: 100 / cols,
      });
    }
    cluster = [];
  };

  for (const span of spans) {
    if (cluster.length > 0 && span.start >= clusterEnd) {
      flush();
      clusterEnd = -1;
    }
    cluster.push(span);
    clusterEnd = Math.max(clusterEnd, span.end);
  }
  flush();
  return out;
}
