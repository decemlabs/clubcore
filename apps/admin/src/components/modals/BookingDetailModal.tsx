/**
 * BookingDetailModal — view booking details, cancel, and complete a PT booking (Phase 102-03 SCH-02).
 *
 * Opened when user clicks a booked slot in WeekCalendar.
 *
 * Footer logic per status + role:
 *  - confirmed + owner:                 «Отмена брони» (danger-ghost) + «Завершить» (primary) + «Закрыть» (ghost)
 *  - confirmed + reception + >24h:      «Отмена брони» (danger-ghost) + «Закрыть» (ghost)
 *  - confirmed + reception + ≤24h:      «Закрыть» only (cancel button hidden — T-102-BK-WINDOW)
 *  - completed/cancelled/no_show:       «Закрыть» only
 *
 * Cancel flow: opens ConfirmModal → useCancelBooking.
 * 409 cancel_window_expired → close both modals (hook already toasts the friendly copy).
 *
 * Complete flow: useCompleteBooking → POST /api/v1/pt-sessions with bookingId.
 * 409 booking_not_confirmed / booking_mismatch → hook toasts friendly copy.
 *
 * All copy per UI-SPEC Copywriting Contract (Russian only).
 */
import { useState } from 'react';
import { CalendarCheck, Loader2 } from '@/components/icons';
import { AdaptiveModal } from './AdaptiveModal';
import { ConfirmModal } from './ConfirmModal';
import { IconChip, ModalButton, StatRow } from './fields';
import { useCancelBooking, useCompleteBooking } from '@/features/bookings/api';
import { formatTime, formatDateRu } from '@/lib/format';
import type { BookingData } from '@/features/bookings/schemas';
import type { Role } from '@/shared/session/types';

// Status display
const STATUS_LABEL: Record<string, string> = {
  confirmed: 'Подтверждено',
  cancelled: 'Отменено',
  no_show: 'Не явился',
  completed: 'Завершено',
};

const STATUS_CLASS: Record<string, string> = {
  confirmed: 'bg-primary-soft text-primary-deep dark:text-primary',
  cancelled: 'bg-surface-3 text-fg-subtle',
  no_show: 'bg-warning-soft text-warning-deep',
  completed: 'bg-surface-3 text-fg-subtle',
};

interface BookingDetailModalProps {
  booking: BookingData;
  role: Role;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Returns true if the slot starts within 24 hours from now. */
function isWithin24h(startTime: string): boolean {
  const now = Date.now();
  const slotTime = new Date(startTime).getTime();
  return slotTime - now < 24 * 60 * 60 * 1000;
}

export function BookingDetailModal({ booking, role, open, onOpenChange }: BookingDetailModalProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const cancelBooking = useCancelBooking();
  const completeBooking = useCompleteBooking();

  const isConfirmed = booking.status === 'confirmed';
  const isTerminal = !isConfirmed;
  const slotStartTime = booking.slot?.startTime ?? '';
  const within24h = slotStartTime ? isWithin24h(slotStartTime) : false;
  const showCancel = isConfirmed && (role === 'owner' || (role === 'reception' && !within24h));
  const showComplete = isConfirmed && role === 'owner';
  const isCompletePending = completeBooking.isPending;
  const isCancelPending = cancelBooking.isPending;

  const clientFullName = booking.clientFullName ?? 'Клиент';
  const trainerFullName = booking.slot?.trainerFullName ?? 'Тренер';
  const timeDisplay = slotStartTime
    ? `${formatTime(slotStartTime)}–${formatTime(booking.slot?.endTime ?? '')} · ${formatDateRu(slotStartTime, 'd MMMM yyyy')}`
    : '—';

  // Cancel confirm message per role + 24h window (UI-SPEC §3.4)
  const cancelMessage =
    role === 'owner'
      ? 'Бронирование будет отменено. Владелец может отменить в любое время.'
      : within24h
        ? 'До занятия менее 24 часов. Отмена возможна только владельцем.'
        : 'Бронирование будет отменено. Клиент получит уведомление.';

  const handleCancel = async () => {
    try {
      await cancelBooking.mutateAsync({
        bookingId: booking.id,
        body: { reason: 'Отменено администратором' },
      });
      setConfirmOpen(false);
      onOpenChange(false);
    } catch {
      // Hook already handled cancel_window_expired with a toast.
      // Any other errors are also toasted by the hook.
      setConfirmOpen(false);
      onOpenChange(false);
    }
  };

  const handleComplete = async () => {
    if (!booking.slot?.trainerId) return;
    try {
      await completeBooking.mutateAsync({
        ptPackageId: booking.ptPackageId,
        trainerId: booking.slot.trainerId,
        bookingId: booking.id,
      });
      onOpenChange(false);
    } catch {
      // Hook already toasted booking_not_confirmed/booking_mismatch errors.
      // Do NOT crash.
    }
  };

  return (
    <>
      <AdaptiveModal
        open={open}
        onOpenChange={onOpenChange}
        icon={<IconChip tone="accent" icon={CalendarCheck} />}
        title="Бронирование"
        description={`${clientFullName} · ${trainerFullName} · ${formatDateRu(slotStartTime, 'd MMMM')}`}
        footerActions={
          <>
            {showCancel && (
              <ModalButton
                variant="ghost"
                className="text-danger hover:bg-danger-soft hover:text-danger"
                disabled={isCancelPending || isCompletePending}
                onClick={() => setConfirmOpen(true)}
              >
                Отмена брони
              </ModalButton>
            )}
            {showComplete && (
              <ModalButton
                variant="primary"
                disabled={isCompletePending || isCancelPending}
                onClick={() => void handleComplete()}
              >
                {isCompletePending ? <Loader2 className="size-4 animate-spin" /> : null}
                Завершить
              </ModalButton>
            )}
            {isTerminal && null}
            <ModalButton
              variant="ghost"
              disabled={isCancelPending || isCompletePending}
              onClick={() => onOpenChange(false)}
            >
              Закрыть
            </ModalButton>
          </>
        }
      >
        {/* Booking details — StatRow rows */}
        <StatRow label="Клиент" value={clientFullName} />
        <StatRow label="Тренер" value={trainerFullName} />
        <StatRow label="Время" value={timeDisplay} />
        <StatRow
          label="Статус"
          value={
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLASS[booking.status] ?? ''}`}
            >
              {STATUS_LABEL[booking.status] ?? booking.status}
            </span>
          }
        />
        {booking.ptPackage && (
          <StatRow
            label="PT-пакет"
            value={`${booking.ptPackage.planName} · Осталось: ${booking.ptPackage.sessionsRemaining} из ${booking.ptPackage.sessionsTotal}`}
          />
        )}
      </AdaptiveModal>

      {/* Cancel confirmation modal */}
      <ConfirmModal
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        payload={{
          title: 'Отменить бронирование?',
          message: cancelMessage,
          tone: 'danger',
          confirmLabel: 'Отменить запись',
          cancelLabel: 'Назад',
          onConfirm: handleCancel,
        }}
      />
    </>
  );
}
