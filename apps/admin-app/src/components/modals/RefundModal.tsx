/**
 * RefundModal — owner-gated confirmation dialog for payment refunds (Phase 112 REF-01).
 *
 * Opens from a «Оформить возврат» destructive DropdownMenuItem on non-refund payment rows
 * in both Cashbox (TransactionsCard) and Finance (OnlinePaymentsTable).
 *
 * Props:
 *   payment  — the original payment to refund (id, amountKopecks, subjectKind, method, receivedAt)
 *   open     — dialog open state
 *   onOpenChange — dialog open state setter
 *
 * Validation:
 *   - Amount must be 0.01–remaining (in rubles)
 *   - Reason must be ≥3 chars
 *   - Confirm disabled when invalid or busy
 *
 * On success: Sonner toast + paymentsKeys.lists() invalidated via hook
 * On 409: toast mapped from ApiError code; modal stays open
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { Undo2 } from '@/components/icons';
import { AdaptiveModal } from '@/components/modals/AdaptiveModal';
import {
  IconChip,
  ModalButton,
  Field,
  ModalInput,
  ModalTextarea,
  StatRow,
} from '@/components/modals/fields';
import { formatRub, formatDateRu } from '@/lib/format';
import { useRefundPayment, ApiError } from '@/features/payments/api';
import type { PaymentData } from '@/features/payments/schemas';

// ---------------------------------------------------------------------------
// Label helpers
// ---------------------------------------------------------------------------

function getSubjectKindLabel(subjectKind: string): string {
  if (subjectKind === 'membership') return 'Абонемент';
  if (subjectKind === 'pt_package') return 'PT-пакет';
  return subjectKind;
}

function getMethodLabel(method: string): string {
  if (method === 'cash') return 'Наличные';
  if (method === 'online') return 'Онлайн';
  return method;
}

// ---------------------------------------------------------------------------
// Error handler — maps ApiError codes to Russian toasts
// ---------------------------------------------------------------------------

function handleRefundError(err: unknown) {
  if (err instanceof ApiError) {
    if (err.code === 'over_refund') {
      toast.error('Возврат невозможен: сумма превышает доступный остаток');
    } else if (err.code === 'already_refunded') {
      toast.error('Возврат невозможен: сумма превышает доступный остаток');
    } else if (err.code === 'cannot_refund_refund') {
      toast.error('Нельзя оформить возврат на возврат');
    } else {
      toast.error('Не удалось оформить возврат. Попробуйте ещё раз.');
    }
  } else {
    toast.error('Не удалось оформить возврат. Попробуйте ещё раз.');
  }
}

// ---------------------------------------------------------------------------
// RefundModal
// ---------------------------------------------------------------------------

export interface RefundModalProps {
  payment: PaymentData;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RefundModal({ payment, open, onOpenChange }: RefundModalProps) {
  const refundMutation = useRefundPayment();

  // Original amount in rubles (payment.amountKopecks is always positive for non-refund rows)
  const originalRub = Math.abs(payment.amountKopecks) / 100;

  // For Phase 112 the backend supports one partial refund per original.
  // alreadyRefunded is 0 for Phase 112 (no multi-refund tracking on client side yet).
  const alreadyRefundedKopecks = 0;
  const remainingKopecks = payment.amountKopecks - alreadyRefundedKopecks;
  const remainingRub = remainingKopecks / 100;

  const [amountRub, setAmountRub] = useState<string>(String(remainingRub));
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  // Validation
  const amountNum = parseFloat(amountRub);
  const amountValid = !isNaN(amountNum) && amountNum >= 0.01 && amountNum <= remainingRub;
  const amountExceedsHint = !isNaN(amountNum) && amountNum > remainingRub;
  const reasonValid = reason.trim().length >= 3;
  const formValid = amountValid && reasonValid;

  function handleOpenChange(value: boolean) {
    if (!value) {
      onOpenChange(false);
      // Reset form state after dialog animation completes
      setTimeout(() => {
        setAmountRub(String(remainingRub));
        setReason('');
        setBusy(false);
      }, 300);
    }
  }

  function handleSubmit() {
    if (!formValid || busy) return;
    const amountKopecks = Math.round(amountNum * 100);
    setBusy(true);
    refundMutation.mutate(
      { paymentId: payment.id, amountKopecks, reason: reason.trim() },
      {
        onSuccess: () => {
          handleOpenChange(false);
          toast.success('Возврат оформлен', {
            description: formatRub(amountNum),
          });
        },
        onError: (err) => {
          setBusy(false);
          handleRefundError(err);
        },
      },
    );
  }

  const description = [
    getSubjectKindLabel(payment.subjectKind),
    getMethodLabel(payment.method),
    formatDateRu(payment.receivedAt),
  ].join(' · ');

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={handleOpenChange}
      title="Оформить возврат"
      icon={<IconChip tone="warn" icon={Undo2} />}
      description={description}
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={busy} onClick={() => handleOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton variant="danger" disabled={!formValid || busy} onClick={handleSubmit}>
            Оформить возврат
          </ModalButton>
        </>
      }
    >
      {/* Payment summary rows */}
      <StatRow label="Исходная сумма" value={formatRub(originalRub)} />
      {alreadyRefundedKopecks > 0 ? (
        <StatRow label="Уже возвращено" value={formatRub(alreadyRefundedKopecks / 100)} />
      ) : null}
      <StatRow label="Доступно к возврату" value={formatRub(remainingRub)} accent />

      {/* Amount field */}
      <Field
        label="Сумма возврата"
        required
        hint={
          amountExceedsHint
            ? undefined
            : 'Частичный возврат разрешён — не более доступного остатка'
        }
      >
        <ModalInput
          type="number"
          suffix="₽"
          value={amountRub}
          min={0.01}
          max={remainingRub}
          step={0.01}
          disabled={busy}
          onChange={(e) => setAmountRub(e.target.value)}
        />
        {amountExceedsHint ? (
          <div className="mt-1.5 text-[11.5px] text-danger">Превышает доступный остаток</div>
        ) : null}
      </Field>

      {/* Reason field */}
      <Field
        label="Причина возврата"
        required
        hint="Минимум 3 символа · сохраняется в журнале"
      >
        <ModalTextarea
          placeholder="Например: клиент передумал, ошибка кассира…"
          value={reason}
          minLength={3}
          disabled={busy}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
    </AdaptiveModal>
  );
}
