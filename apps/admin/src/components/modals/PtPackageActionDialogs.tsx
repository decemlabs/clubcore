/**
 * PtPackageActionDialogs — PT-package cancel + refund dialogs (Phase 107-02 PTPKG-02).
 *
 * PtPackageCancelDialog:
 *   - OWNER_ONLY (can(role,'cancel','pt-packages') gates the kebab item in TrainingsTab)
 *   - Required reason (1–200 chars) — unlike membership cancel where reason is optional
 *   - Always-shown danger Callout (irreversibility warning)
 *   - useCancelPtPackage owns its own toast — onSuccess ONLY closes
 *
 * PtPackageRefundDialog:
 *   - Reception+owner (B-07)
 *   - Required reason (1–200 chars)
 *   - Warn Callout + К возврату StatRow + Дата покупки StatRow
 *   - useRefundPtPackage owns its own toast — onSuccess ONLY closes
 *
 * Both: useEffect reset on open, isPending block on onOpenChange, spinner on submit.
 */
import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'
import { formatKopecks, formatDateRu } from '@/lib/format'
import { useCancelPtPackage, useRefundPtPackage, ApiError } from '@/features/pt-packages/api'
import type { PtPackageData } from '@/features/pt-packages/schemas'
import { CircleX, Loader2, ReceiptText, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { Callout, Field, IconChip, ModalButton, StatRow } from './fields'

// ---------------------------------------------------------------------------
// Shared helper
// ---------------------------------------------------------------------------

function ErrorCallout({ error }: { error: Error | null }) {
  if (!error) return null
  const msg =
    error instanceof ApiError
      ? error.message
      : 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.'
  return (
    <div className="mt-3.5">
      <Callout tone="danger" icon={TriangleAlert}>
        {msg}
      </Callout>
    </div>
  )
}

// ---------------------------------------------------------------------------
// PtPackageCancelDialog
// ---------------------------------------------------------------------------

export function PtPackageCancelDialog({
  open,
  onOpenChange,
  item,
  clientName,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  item: PtPackageData
  clientName?: string
}) {
  const [reason, setReason] = useState('')
  const [touched, setTouched] = useState(false)
  const cancelMutation = useCancelPtPackage()

  useEffect(() => {
    if (open) {
      setReason('')
      setTouched(false)
      cancelMutation.reset()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = cancelMutation.isPending
  const reasonTrimmed = reason.trim()

  function handleSubmit() {
    setTouched(true)
    if (!reasonTrimmed) return
    cancelMutation.mutate(
      { packageId: item.id, body: { reason: reasonTrimmed } },
      {
        onSuccess: () => {
          onOpenChange(false)
        },
      },
    )
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip tone="danger" icon={CircleX} />}
      title="Отменить пакет тренировок?"
      description={
        clientName ? `${clientName} · «${item.planSnapshot.name}»` : `«${item.planSnapshot.name}»`
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Не отменять
          </ModalButton>
          <ModalButton
            variant="danger"
            disabled={isPending || reasonTrimmed.length === 0}
            onClick={handleSubmit}
          >
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Отменить пакет'
            )}
          </ModalButton>
        </>
      }
    >
      <Callout tone="danger" icon={TriangleAlert}>
        Пакет станет неактивным. Оставшиеся занятия будут аннулированы. Действие необратимо.
      </Callout>
      <div className="mt-3.5">
        <Field label="Причина отмены" required>
          <textarea
            className={cn(
              'min-h-[80px] w-full resize-none rounded-[10px] border-[0.5px] border-border bg-surface-2',
              'px-3 py-2.5 text-[13.5px] outline-none placeholder:text-fg-subtle',
              'focus:border-primary focus:ring-2 focus:ring-primary/20',
            )}
            maxLength={200}
            placeholder="Укажите причину отмены"
            value={reason}
            disabled={isPending}
            onChange={(e) => setReason(e.target.value)}
            onBlur={() => setTouched(true)}
          />
          <div className="mt-1 flex justify-between">
            {touched && reasonTrimmed.length === 0 ? (
              <span className="text-[12px] text-danger">Причина обязательна</span>
            ) : (
              <span />
            )}
            <span className="ml-auto text-[11.5px] tabular-nums text-fg-subtle">
              {reason.length}/200
            </span>
          </div>
        </Field>
      </div>
      <ErrorCallout error={cancelMutation.error} />
    </AdaptiveModal>
  )
}

// ---------------------------------------------------------------------------
// PtPackageRefundDialog
// ---------------------------------------------------------------------------

export function PtPackageRefundDialog({
  open,
  onOpenChange,
  item,
  clientName,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  item: PtPackageData
  clientName?: string
}) {
  const [reason, setReason] = useState('')
  const [touched, setTouched] = useState(false)
  const refundMutation = useRefundPtPackage()

  useEffect(() => {
    if (open) {
      setReason('')
      setTouched(false)
      refundMutation.reset()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = refundMutation.isPending
  const reasonTrimmed = reason.trim()

  function handleSubmit() {
    setTouched(true)
    if (!reasonTrimmed) return
    refundMutation.mutate(
      { packageId: item.id, body: { reason: reasonTrimmed } },
      {
        onSuccess: () => {
          onOpenChange(false)
        },
      },
    )
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip tone="danger" icon={ReceiptText} />}
      title="Оформить возврат"
      description={
        clientName ? `${clientName} · «${item.planSnapshot.name}»` : `«${item.planSnapshot.name}»`
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Не возвращать
          </ModalButton>
          <ModalButton
            variant="danger"
            disabled={isPending || reasonTrimmed.length === 0}
            onClick={handleSubmit}
          >
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              `Вернуть ${formatKopecks(item.amountKopecks)}`
            )}
          </ModalButton>
        </>
      }
    >
      <Callout tone="warn" icon={TriangleAlert}>
        Возврат полный и необратимый. Средства вернутся тем же способом, которым была принята оплата.
      </Callout>
      <StatRow label="К возврату" value={formatKopecks(item.amountKopecks)} accent />
      <StatRow label="Дата покупки" value={formatDateRu(item.createdAt, 'd MMMM yyyy')} />
      <div className="mt-3.5">
        <Field label="Причина возврата" required>
          <textarea
            className={cn(
              'min-h-[80px] w-full resize-none rounded-[10px] border-[0.5px] border-border bg-surface-2',
              'px-3 py-2.5 text-[13.5px] outline-none placeholder:text-fg-subtle',
              'focus:border-primary focus:ring-2 focus:ring-primary/20',
            )}
            maxLength={200}
            placeholder="Укажите причину возврата"
            value={reason}
            disabled={isPending}
            onChange={(e) => setReason(e.target.value)}
            onBlur={() => setTouched(true)}
          />
          <div className="mt-1 flex justify-between">
            {touched && reasonTrimmed.length === 0 ? (
              <span className="text-[12px] text-danger">Причина обязательна для возврата</span>
            ) : (
              <span />
            )}
            <span className="ml-auto text-[11.5px] tabular-nums text-fg-subtle">
              {reason.length}/200
            </span>
          </div>
        </Field>
      </div>
      <ErrorCallout error={refundMutation.error} />
    </AdaptiveModal>
  )
}
