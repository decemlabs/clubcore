/**
 * PtPackageSellModal — PT-package instance sell dialog (Phase 107-02 PTPKG-01).
 *
 * - Plan select populated by usePtPackagePlans() (no args — backend default = active only).
 * - amountKopecks is LOCKED to the selected plan's priceKopecks (operator never types it).
 * - amount_mismatch 422 surfaced as a warn Callout (not a crash).
 * - useSellPtPackage owns its own success + error toasts — modal onSuccess ONLY closes.
 * - Optional «Заметка» textarea is display-only (sell hook input has no notes field).
 */
import { useEffect, useState } from 'react'
import { formatKopecks } from '@/lib/format'
import { usePtPackagePlans, useSellPtPackage, ApiError } from '@/features/pt-packages/api'
import { CreditCard, Loader2, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { Callout, Field, IconChip, ModalButton, ModalTextarea, StatRow } from './fields'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ErrorCallout({ error }: { error: Error | null }) {
  if (!error) return null
  // amount_mismatch is handled separately as a warn callout — skip the generic error display
  if (error instanceof ApiError && error.code === 'amount_mismatch') return null
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
// PtPackageSellModal
// ---------------------------------------------------------------------------

export function PtPackageSellModal({
  open,
  onOpenChange,
  clientId,
  clientName,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  clientId: string
  clientName?: string
}) {
  const [selectedPlanId, setSelectedPlanId] = useState<string>('')
  const [notes, setNotes] = useState('')
  const plansQuery = usePtPackagePlans()
  const sellMutation = useSellPtPackage()

  useEffect(() => {
    if (open) {
      setSelectedPlanId('')
      setNotes('')
      sellMutation.reset()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const plans = plansQuery.data?.items ?? []
  const selectedPlan = plans.find((p) => p.id === selectedPlanId)
  const isPending = sellMutation.isPending

  const isAmountMismatch =
    sellMutation.error instanceof ApiError &&
    sellMutation.error.code === 'amount_mismatch'

  function handleSubmit() {
    if (!clientId || !selectedPlanId || !selectedPlan) return
    sellMutation.mutate(
      {
        clientId,
        planId: selectedPlanId,
        amountKopecks: selectedPlan.priceKopecks, // locked — never typed by operator
      },
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
      size="wide"
      icon={<IconChip tone="accent" icon={CreditCard} />}
      title="Продать пакет тренировок"
      description={
        clientName ? `${clientName} · выберите пакет и примите оплату` : 'Выберите пакет и примите оплату'
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Не продавать
          </ModalButton>
          <ModalButton disabled={isPending || !selectedPlanId} onClick={handleSubmit}>
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Продать пакет'
            )}
          </ModalButton>
        </>
      }
    >
      <Field label="Пакет">
        {plansQuery.isPending ? (
          <div className="h-[42px] animate-pulse rounded-xl bg-surface-3" />
        ) : (
          <select
            value={selectedPlanId}
            onChange={(e) => setSelectedPlanId(e.target.value)}
            disabled={isPending}
            className="w-full h-[42px] cursor-pointer appearance-none rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 pr-9 text-sm text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
          >
            <option value="">Выберите пакет…</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {formatKopecks(p.priceKopecks)}
              </option>
            ))}
          </select>
        )}
      </Field>
      {selectedPlan ? (
        <StatRow label="К оплате" value={formatKopecks(selectedPlan.priceKopecks)} accent />
      ) : null}
      <Field label="Заметка" optional>
        <ModalTextarea
          placeholder="Необязательно"
          value={notes}
          disabled={isPending}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />
      </Field>
      {isAmountMismatch && (
        <div className="mt-3.5">
          <Callout tone="warn" icon={TriangleAlert}>
            Стоимость пакета изменилась. Обновите страницу и попробуйте снова.
          </Callout>
        </div>
      )}
      <ErrorCallout error={sellMutation.error} />
    </AdaptiveModal>
  )
}
