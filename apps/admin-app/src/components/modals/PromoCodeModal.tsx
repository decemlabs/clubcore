/**
 * PromoCodeModal — create/edit form for promo codes (Phase 113 PROMO-01).
 *
 * Analog: PlanFormModal.tsx (structure, reset-on-open, safeParse, onError mapping).
 * UI contract: 113-UI-SPEC.md Surface 2.
 *
 * Props:
 *   mode  — 'create' | 'edit'
 *   promo — prefill data for edit mode (PromoCodeData)
 *
 * Conversion at the FE boundary (wire representation ↔ display):
 *   - percentage: FE input is whole percent (1–100); wire value = percent * 100
 *   - fixed: FE input is whole rubles; wire value = rubles * 100 (kopecks)
 *   Inverse conversion for prefill in edit mode.
 *
 * Validation:
 *   - code empty → confirm disabled
 *   - discountValue ≤ 0 → confirm disabled
 *   - percentage value > 100 → confirm disabled + inline hint text-danger
 *   - valid_until < valid_from → confirm disabled + inline hint text-danger
 *
 * Error mapping:
 *   409 promo_code_already_exists → toast.error(«Промокод с таким кодом уже существует»)
 *   422 → toast.error(«Проверьте правильность заполнения полей»)
 *   other → toast.error(«Не удалось сохранить промокод. Попробуйте ещё раз.»)
 */
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useCreatePromoCode, useUpdatePromoCode, ApiError } from '@/features/promoCodes/api'
import {
  PromoCodeCreateSchema,
  PromoCodeUpdateSchema,
  type PromoCodeData,
} from '@/features/promoCodes/schemas'
import { Loader2, Tag } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import {
  ChipGroup,
  Field,
  FieldRow,
  IconChip,
  ModalButton,
  ModalInput,
  ModalTextarea,
  Section,
} from './fields'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PromoCodeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: 'create' | 'edit'
  promo?: PromoCodeData
}

// ---------------------------------------------------------------------------
// Helpers: numeric coercion
// ---------------------------------------------------------------------------

/** Parse an integer field: empty → undefined, non-integer/NaN → NaN. */
function parseIntField(value: string): number | undefined {
  if (value === '') return undefined
  const n = Number(value)
  return Number.isInteger(n) ? n : NaN
}

// ---------------------------------------------------------------------------
// Helpers: wire ↔ display conversion
// ---------------------------------------------------------------------------

/**
 * Convert FE display value → wire discountValue.
 * percentage: percent * 100 (e.g. 10% → 1000 = 10.00%)
 * fixed: rubles * 100 (kopecks)
 */
function toWireDiscountValue(value: string, discountType: 'percentage' | 'fixed'): number | undefined {
  const n = Number(value)
  if (!Number.isFinite(n) || value === '') return undefined
  return discountType === 'percentage' ? Math.round(n * 100) : Math.round(n * 100)
}

/**
 * Convert wire discountValue → FE display string.
 * percentage: wire / 100 (e.g. 1000 → "10")
 * fixed: wire / 100 (kopecks → rubles, e.g. 50000 → "500")
 */
function fromWireDiscountValue(wireValue: number, discountType: 'percentage' | 'fixed'): string {
  return discountType === 'percentage'
    ? String(wireValue / 100)
    : String(wireValue / 100)
}

// ---------------------------------------------------------------------------
// PromoCodeModal
// ---------------------------------------------------------------------------

export function PromoCodeModal({ open, onOpenChange, mode, promo }: PromoCodeModalProps) {
  // ── Form state ────────────────────────────────────────────────────────────
  const [code, setCode] = useState('')
  const [discountType, setDiscountType] = useState<'percentage' | 'fixed'>('percentage')
  const [discountValue, setDiscountValue] = useState('')
  const [maxUses, setMaxUses] = useState('')
  const [perClientLimit, setPerClientLimit] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [applicableTo, setApplicableTo] = useState('')
  const [description, setDescription] = useState('')

  // ── Mutations ─────────────────────────────────────────────────────────────
  const createMutation = useCreatePromoCode()
  const updateMutation = useUpdatePromoCode()

  const isPending = mode === 'create' ? createMutation.isPending : updateMutation.isPending

  // ── Reset on open (prefill from promo in edit mode) ───────────────────────
  useEffect(() => {
    if (open) {
      createMutation.reset()
      updateMutation.reset()

      setCode(promo?.code ?? '')
      const type = promo?.discountType ?? 'percentage'
      setDiscountType(type)
      setDiscountValue(
        promo != null ? fromWireDiscountValue(promo.discountValue, type) : '',
      )
      setMaxUses(promo?.maxUses != null ? String(promo.maxUses) : '')
      setPerClientLimit(promo?.perClientLimit != null ? String(promo.perClientLimit) : '')
      setValidFrom(promo?.validFrom != null ? promo.validFrom.slice(0, 10) : '')
      setValidUntil(promo?.validUntil != null ? promo.validUntil.slice(0, 10) : '')
      setApplicableTo(promo?.applicableTo ?? '')
      setDescription(promo?.description ?? '')
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Inline validation state (for hints) ──────────────────────────────────
  const discountValueNum = Number(discountValue)
  const isPercentTooHigh = discountType === 'percentage' && discountValue !== '' && discountValueNum > 100
  const isDateRangeInvalid =
    validFrom !== '' && validUntil !== '' && validFrom > validUntil

  // ── Required-field check for button disable ───────────────────────────────
  const isCodeValid = code.trim().length > 0
  const isDiscountValid =
    discountValue !== '' && Number.isFinite(discountValueNum) && discountValueNum > 0
  const isRequiredValid =
    isCodeValid && isDiscountValid && !isPercentTooHigh && !isDateRangeInvalid

  // ── Submit ────────────────────────────────────────────────────────────────
  function handleSubmit() {
    const wireDiscountValue = toWireDiscountValue(discountValue, discountType)

    const raw = {
      code: code.trim().toUpperCase(),
      discountType,
      discountValue: wireDiscountValue,
      maxUses: parseIntField(maxUses),
      perClientLimit: parseIntField(perClientLimit),
      validFrom: validFrom !== '' ? validFrom : null,
      validUntil: validUntil !== '' ? validUntil : null,
      applicableTo: applicableTo.trim() !== '' ? applicableTo.trim() : null,
      description: description.trim() !== '' ? description.trim() : null,
    }

    const finalCode = code.trim().toUpperCase()

    function handlePromoError(err: unknown) {
      if (err instanceof ApiError) {
        if (err.code === 'promo_code_already_exists') {
          toast.error('Промокод с таким кодом уже существует')
        } else if (err.code === 'validation_error' || err.code === 'unprocessable_entity') {
          toast.error('Проверьте правильность заполнения полей')
        } else {
          toast.error('Не удалось сохранить промокод. Попробуйте ещё раз.')
        }
      } else {
        toast.error('Не удалось сохранить промокод. Попробуйте ещё раз.')
      }
    }

    if (mode === 'create') {
      const result = PromoCodeCreateSchema.safeParse(raw)
      if (!result.success) {
        toast.error('Проверьте правильность заполнения полей')
        return
      }
      createMutation.mutate(result.data, {
        onSuccess: () => {
          onOpenChange(false)
          toast.success('Промокод создан', { description: finalCode })
        },
        onError: handlePromoError,
      })
    } else {
      if (!promo) return
      const result = PromoCodeUpdateSchema.safeParse(raw)
      if (!result.success) {
        toast.error('Проверьте правильность заполнения полей')
        return
      }
      updateMutation.mutate(
        { id: promo.id, body: result.data },
        {
          onSuccess: () => {
            onOpenChange(false)
            toast.success('Промокод обновлён', { description: finalCode })
          },
          onError: handlePromoError,
        },
      )
    }
  }

  // ── Labels ────────────────────────────────────────────────────────────────
  const title = mode === 'create' ? 'Создать промокод' : 'Редактировать промокод'
  const description_prop = mode === 'edit' && promo ? promo.code : undefined
  const ctaLabel = mode === 'create' ? 'Создать промокод' : 'Сохранить изменения'

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      size="default"
      icon={<IconChip tone="accent" icon={Tag} />}
      title={title}
      description={description_prop}
      footerActions={
        <>
          <ModalButton
            variant="ghost"
            disabled={isPending}
            onClick={() => onOpenChange(false)}
          >
            Отмена
          </ModalButton>
          <ModalButton
            disabled={isPending || !isRequiredValid}
            onClick={handleSubmit}
          >
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              ctaLabel
            )}
          </ModalButton>
        </>
      }
    >
      {/* ── Код и скидка ── */}
      <Section>Код и скидка</Section>

      <Field
        label="Промокод"
        required
        hint="Латинские буквы и цифры. Автоматически переводится в верхний регистр."
      >
        <ModalInput
          type="text"
          placeholder="SUMMER25"
          maxLength={32}
          value={code.toUpperCase()}
          disabled={isPending}
          onChange={(e) => setCode(e.target.value)}
        />
      </Field>

      <FieldRow cols={2}>
        <Field label="Тип скидки" required>
          <ChipGroup
            options={[
              { value: 'percentage', label: 'Процент' },
              { value: 'fixed', label: 'Фикс. сумма' },
            ]}
            value={discountType}
            onChange={(v) => {
              const newType = v as 'percentage' | 'fixed'
              // Reset discount value when switching type to avoid stale wire values
              if (promo && newType !== discountType) {
                setDiscountValue('')
              }
              setDiscountType(newType)
            }}
          />
        </Field>
        <Field
          label={discountType === 'percentage' ? 'Размер скидки, %' : 'Размер скидки, ₽'}
          required
          hint={
            isPercentTooHigh
              ? undefined
              : discountType === 'percentage'
                ? 'От 1 до 100'
                : 'Целое число рублей'
          }
        >
          <ModalInput
            type="number"
            min={1}
            max={discountType === 'percentage' ? 100 : undefined}
            step={1}
            suffix={discountType === 'percentage' ? '%' : '₽'}
            value={discountValue}
            disabled={isPending}
            onChange={(e) => setDiscountValue(e.target.value)}
          />
          {isPercentTooHigh && (
            <span className="mt-1 block text-[11.5px] text-danger">
              Процент не может быть больше 100
            </span>
          )}
        </Field>
      </FieldRow>

      {/* ── Ограничения ── */}
      <Section>Ограничения</Section>

      <FieldRow cols={2}>
        <Field label="Макс. использований" optional hint="Пусто — без ограничений">
          <ModalInput
            type="number"
            min={1}
            step={1}
            placeholder="∞"
            value={maxUses}
            disabled={isPending}
            onChange={(e) => setMaxUses(e.target.value)}
          />
        </Field>
        <Field label="Лимит на клиента" optional hint="Пусто — без ограничений">
          <ModalInput
            type="number"
            min={1}
            step={1}
            placeholder="∞"
            value={perClientLimit}
            disabled={isPending}
            onChange={(e) => setPerClientLimit(e.target.value)}
          />
        </Field>
      </FieldRow>

      {/* ── Срок действия ── */}
      <Section>Срок действия</Section>

      <FieldRow cols={2}>
        <Field label="Начало действия" optional>
          <ModalInput
            type="date"
            value={validFrom}
            disabled={isPending}
            onChange={(e) => setValidFrom(e.target.value)}
          />
        </Field>
        <Field
          label="Конец действия"
          optional
          hint={isDateRangeInvalid ? undefined : undefined}
        >
          <ModalInput
            type="date"
            value={validUntil}
            disabled={isPending}
            onChange={(e) => setValidUntil(e.target.value)}
          />
          {isDateRangeInvalid && (
            <span className="mt-1 block text-[11.5px] text-danger">
              Дата окончания не может быть раньше даты начала
            </span>
          )}
        </Field>
      </FieldRow>

      {/* ── Дополнительно ── */}
      <Section>Дополнительно</Section>

      <Field
        label="Применять к"
        optional
        hint="Пусто — применяется ко всем тарифам"
      >
        <ModalInput
          type="text"
          placeholder="Напр.: Тариф «Стандарт»"
          value={applicableTo}
          disabled={isPending}
          onChange={(e) => setApplicableTo(e.target.value)}
        />
      </Field>

      <Field label="Описание" optional>
        <ModalTextarea
          placeholder="Внутренняя заметка о промокоде…"
          rows={2}
          value={description}
          disabled={isPending}
          onChange={(e) => setDescription(e.target.value)}
        />
      </Field>
    </AdaptiveModal>
  )
}
