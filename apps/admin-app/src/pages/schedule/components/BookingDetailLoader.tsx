/**
 * BookingDetailLoader — thin wrapper that fetches a single booking by id
 * and passes it to BookingDetailModal (Phase 102-03 SCH-02).
 *
 * Keeps React hook rules: useBooking is always called (enabled by id truthy).
 * Shows PageLoading overlay inside the modal while fetching.
 */
import { useEffect } from 'react';
import { Loader2 } from '@/components/icons';
import { useBooking } from '@/features/bookings/api';
import { BookingDetailModal } from '@/components/modals/BookingDetailModal';
import type { Role } from '@/shared/session/types';

interface Props {
  bookingId: string;
  role: Role;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BookingDetailLoader({ bookingId, role, open, onOpenChange }: Props) {
  const { data: booking, isPending, isError } = useBooking(bookingId);

  // WR-02: close the modal after render via effect, not during render.
  // Calling onOpenChange(false) synchronously in the render body violates React's rules:
  // it updates parent state during child render, causing cascading re-renders and a
  // "Cannot update a component while rendering a different component" warning in Strict Mode.
  useEffect(() => {
    if (!isPending && (isError || !booking)) {
      onOpenChange(false);
    }
  }, [isPending, isError, booking, onOpenChange]);

  if (isPending) {
    return (
      <div
        role="dialog"
        aria-label="Загрузка бронирования"
        aria-modal="true"
        className="fixed inset-0 z-50 flex items-center justify-center bg-bg/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      >
        <Loader2 className="size-8 animate-spin text-fg-muted" />
      </div>
    );
  }

  if (isError || !booking) {
    // Effect above will close the modal; render null in the meantime
    return null;
  }

  return (
    <BookingDetailModal
      booking={booking}
      role={role}
      open={open}
      onOpenChange={onOpenChange}
    />
  );
}
