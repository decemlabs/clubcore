/**
 * BookingDetailLoader — thin wrapper that fetches a single booking by id
 * and passes it to BookingDetailModal (Phase 102-03 SCH-02).
 *
 * Keeps React hook rules: useBooking is always called (enabled by id truthy).
 * Shows PageLoading overlay inside the modal while fetching.
 */
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
    // Silently close on error — the transport layer already toasted
    onOpenChange(false);
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
