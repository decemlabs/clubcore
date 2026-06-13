/**
 * calendar-utils merge function unit tests (Phase 102-03 SCH-02).
 *
 * Tests the mergeSlotBookings() discriminator:
 *  - available slot (no booking) → type='available'
 *  - slot with confirmed booking → type='booked'
 *  - cancelled slot → type='cancelled'
 *  - slot with non-confirmed booking (cancelled/no_show/completed) → type='available'
 */
import { describe, it, expect } from 'vitest';
import { mergeSlotBookings } from './calendar-utils';
import type { TrainerSlotData } from '@/features/schedule/schemas';
import type { BookingData } from '@/features/bookings/schemas';

// Monday 2026-06-15 00:00 UTC
const WEEK_START = new Date('2026-06-15T00:00:00Z');

const SLOT_MON: TrainerSlotData = {
  id: 'slot-mon',
  trainerId: 'trainer-1',
  startTime: '2026-06-15T10:00:00Z', // Monday
  endTime: '2026-06-15T11:00:00Z',
  status: 'active',
  createdAt: '2026-06-01T00:00:00Z',
};

const SLOT_TUE: TrainerSlotData = {
  id: 'slot-tue',
  trainerId: 'trainer-1',
  startTime: '2026-06-16T10:00:00Z', // Tuesday
  endTime: '2026-06-16T11:00:00Z',
  status: 'active',
  createdAt: '2026-06-01T00:00:00Z',
};

const SLOT_CANCELLED: TrainerSlotData = {
  id: 'slot-cancelled',
  trainerId: 'trainer-1',
  startTime: '2026-06-17T10:00:00Z', // Wednesday
  endTime: '2026-06-17T11:00:00Z',
  status: 'cancelled',
  createdAt: '2026-06-01T00:00:00Z',
};

const BOOKING_CONFIRMED: BookingData = {
  id: 'booking-1',
  slotId: 'slot-tue',
  clientId: 'client-1',
  ptPackageId: 'pkg-1',
  status: 'confirmed',
  clientFullName: 'Иван Иванов',
  createdAt: '2026-06-01T00:00:00Z',
};

const BOOKING_CANCELLED: BookingData = {
  id: 'booking-2',
  slotId: 'slot-mon',
  clientId: 'client-1',
  ptPackageId: 'pkg-1',
  status: 'cancelled', // not confirmed
  clientFullName: 'Иван Иванов',
  createdAt: '2026-06-01T00:00:00Z',
};

const trainerColorMap = new Map([['trainer-1', '#2dd4a4']]);
const trainerNameMap = new Map([['trainer-1', 'Анна Соколова']]);

describe('mergeSlotBookings — type discriminator', () => {
  it('marks an active slot with no confirmed booking as type=available', () => {
    const events = mergeSlotBookings(
      [SLOT_MON],
      [], // no bookings
      trainerColorMap,
      trainerNameMap,
      WEEK_START,
    );
    expect(events).toHaveLength(1);
    expect(events[0]!.type).toBe('available');
    expect(events[0]!.bookingId).toBeUndefined();
  });

  it('marks a slot with a confirmed booking as type=booked', () => {
    const events = mergeSlotBookings(
      [SLOT_TUE],
      [BOOKING_CONFIRMED],
      trainerColorMap,
      trainerNameMap,
      WEEK_START,
    );
    expect(events).toHaveLength(1);
    expect(events[0]!.type).toBe('booked');
    expect(events[0]!.bookingId).toBe('booking-1');
  });

  it('marks a cancelled slot as type=cancelled regardless of bookings', () => {
    const events = mergeSlotBookings(
      [SLOT_CANCELLED],
      [BOOKING_CONFIRMED],
      trainerColorMap,
      trainerNameMap,
      WEEK_START,
    );
    expect(events).toHaveLength(1);
    expect(events[0]!.type).toBe('cancelled');
  });

  it('marks a slot with a non-confirmed booking as type=available', () => {
    // SLOT_MON has a CANCELLED booking — should still be available
    const events = mergeSlotBookings(
      [SLOT_MON],
      [BOOKING_CANCELLED],
      trainerColorMap,
      trainerNameMap,
      WEEK_START,
    );
    expect(events).toHaveLength(1);
    expect(events[0]!.type).toBe('available');
    expect(events[0]!.bookingId).toBeUndefined();
  });

  it('returns multiple events for multiple slots with correct day indices', () => {
    const events = mergeSlotBookings(
      [SLOT_MON, SLOT_TUE, SLOT_CANCELLED],
      [BOOKING_CONFIRMED],
      trainerColorMap,
      trainerNameMap,
      WEEK_START,
    );
    expect(events).toHaveLength(3);
    const monEvent = events.find((e) => e.slotId === 'slot-mon');
    const tueEvent = events.find((e) => e.slotId === 'slot-tue');
    const cancelledEvent = events.find((e) => e.slotId === 'slot-cancelled');

    expect(monEvent?.day).toBe(0); // Monday = index 0
    expect(tueEvent?.day).toBe(1); // Tuesday = index 1
    expect(cancelledEvent?.day).toBe(2); // Wednesday = index 2
    expect(tueEvent?.type).toBe('booked');
  });

  it('excludes slots outside the 0-6 day window', () => {
    const slotOutsideWeek: TrainerSlotData = {
      ...SLOT_MON,
      id: 'slot-outside',
      startTime: '2026-06-22T10:00:00Z', // Next Monday — day 7
      endTime: '2026-06-22T11:00:00Z',
    };
    const events = mergeSlotBookings(
      [slotOutsideWeek],
      [],
      trainerColorMap,
      trainerNameMap,
      WEEK_START,
    );
    expect(events).toHaveLength(0);
  });
});
