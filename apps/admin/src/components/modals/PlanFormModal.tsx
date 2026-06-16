/**
 * PlanFormModal — shared create/edit form for membership plans and PT-package plans.
 *
 * Covers PLAN-01 (membership) and PLAN-02 (PT-package), replacing the v3.0 P101 WR-01
 * toast stubs on PlansPage. Wired to the already-shipped CRUD hooks via manual
 * Schema.safeParse() validation (no @hookform/resolvers — D-101-01-NOHOOKFORM).
 *
 * Props:
 *   kind  — 'membership' | 'pt-package'
 *   mode  — 'create' | 'edit'
 *   plan  — prefill data for edit mode
 *
 * Immutability rules (per D-101-02-DURATIONIMMUTABLE + D-101-02-PTUPDATE-NAMEONLY):
 *   Membership edit: durationDays, priceKopecks, freezeDaysLimit are VISIBLE but DISABLED.
 *   PT-package edit: only name is editable; sessionCount, priceKopecks, validityDays disabled.
 *   Disabled fields carry hint «Нельзя изменить после создания».
 *
 * Price fields: user enters rubles; multiply × 100 before sending (backend accepts kopecks).
 * 422 field-error mapping: distributes err.fields to per-field inline errors; non-field → ErrorCallout.
 */
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useCreatePlan, useUpdatePlan, ApiError } from '@/features/plans/api'
import { useCreatePtPackagePlan, useUpdatePtPackagePlan } from '@/features/pt-packages/api'
import {
  MembershipPlanCreateSchema,
  MembershipPlanUpdateSchema,
  type MembershipPlanData,
} from '@/features/plans/schemas'
import {
  PtPackagePlanCreateSchema,
  PtPackagePlanUpdateSchema,
  type PtPackagePlanData,
} from '@/features/pt-packages/schemas'
import { Dumbbell, Loader2, Plus, SquarePen, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { Callout, Field, FieldRow, IconChip, ModalButton, ModalInput, ToggleRow } from './fields'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PlanKind = 'membership' | 'pt-package'
type PlanMode = 'create' | 'edit'

export interface PlanFormModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kind: PlanKind
  mode: PlanMode
  plan?: MembershipPlanData | PtPackagePlanData
}

// ---------------------------------------------------------------------------
// Helper: ErrorCallout (verbatim from SubscriptionModal lines 81–94)
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
// Helper: per-field inline error
// ---------------------------------------------------------------------------

function FieldError({ errors, field }: { errors: Record<string, string[] | undefined>; field: string }) {
  const msg = errors[field]?.[0]
  if (!msg) return null
  return <span className="mt-1 block text-[12px] text-danger">{msg}</span>
}

// ---------------------------------------------------------------------------
// Helper: numeric coercion guards (WR-01 — reject NaN / non-integer silently)
// ---------------------------------------------------------------------------

/** Parse an integer field: empty → undefined, non-integer/NaN → NaN (so Zod's
 *  int() check rejects it with a field error instead of silently coercing). */
function parseIntField(value: string): number | undefined {
  if (value === '') return undefined
  const n = Number(value)
  return Number.isInteger(n) ? n : NaN
}

/** Parse a ruble price field → integer kopecks. empty → undefined,
 *  non-finite → NaN (so Zod's int() check rejects it). */
function parsePriceKopecks(value: string): number | undefined {
  if (value === '') return undefined
  const rub = Number(value)
  if (!Number.isFinite(rub)) return NaN
  return Math.round(rub * 100)
}

/** True when an integer field is either non-empty and a valid integer string. */
function isIntFieldValid(value: string): boolean {
  return value !== '' && Number.isInteger(Number(value))
}

/** True when a ruble-price field holds a finite numeric value. */
function isPriceFieldValid(value: string): boolean {
  return value !== '' && Number.isFinite(Number(value))
}

// ---------------------------------------------------------------------------
// PlanFormModal
// ---------------------------------------------------------------------------

export function PlanFormModal({ open, onOpenChange, kind, mode, plan }: PlanFormModalProps) {
  // ── Membership plan form state ──────────────────────────────────────────
  const [memName, setMemName] = useState('')
  const [memDurationDays, setMemDurationDays] = useState('')
  const [memPriceRub, setMemPriceRub] = useState('')
  const [memFreezeDays, setMemFreezeDays] = useState('')
  const [memActive, setMemActive] = useState(true)

  // ── PT-package plan form state ──────────────────────────────────────────
  const [ptName, setPtName] = useState('')
  const [ptSessionCount, setPtSessionCount] = useState('')
  const [ptPriceRub, setPtPriceRub] = useState('')
  const [ptValidityDays, setPtValidityDays] = useState('')

  // ── Validation state ────────────────────────────────────────────────────
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[] | undefined>>({})
  const [serverFieldErrors, setServerFieldErrors] = useState<Record<string, string[] | undefined>>({})

  // ── Mutations ────────────────────────────────────────────────────────────
  const createPlan = useCreatePlan()
  const updatePlan = useUpdatePlan()
  const createPtPlan = useCreatePtPackagePlan()
  const updatePtPlan = useUpdatePtPackagePlan()

  const activeMutation = kind === 'membership'
    ? (mode === 'create' ? createPlan : updatePlan)
    : (mode === 'create' ? createPtPlan : updatePtPlan)

  const isPending = activeMutation.isPending

  // ── Reset on open ────────────────────────────────────────────────────────
  useEffect(() => {
    if (open) {
      setSubmitAttempted(false)
      setFieldErrors({})
      setServerFieldErrors({})
      createPlan.reset()
      updatePlan.reset()
      createPtPlan.reset()
      updatePtPlan.reset()

      if (kind === 'membership') {
        const mp = plan as MembershipPlanData | undefined
        setMemName(mp?.name ?? '')
        setMemDurationDays(mp ? String(mp.durationDays) : '')
        setMemPriceRub(mp ? String(Math.round(mp.priceKopecks / 100)) : '')
        setMemFreezeDays(mp?.freezeDaysLimit != null ? String(mp.freezeDaysLimit) : '')
        setMemActive(mp?.active ?? true)
      } else {
        const pp = plan as PtPackagePlanData | undefined
        setPtName(pp?.name ?? '')
        setPtSessionCount(pp ? String(pp.sessionCount) : '')
        setPtPriceRub(pp ? String(Math.round(pp.priceKopecks / 100)) : '')
        setPtValidityDays(pp?.validityDays != null ? String(pp.validityDays) : '')
      }
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Submit ────────────────────────────────────────────────────────────────
  function handleSubmit() {
    setSubmitAttempted(true)
    setServerFieldErrors({})

    if (kind === 'membership') {
      if (mode === 'create') {
        const raw = {
          name: memName.trim(),
          durationDays: parseIntField(memDurationDays),
          priceKopecks: parsePriceKopecks(memPriceRub),
          freezeDaysLimit: parseIntField(memFreezeDays),
          active: memActive,
        }
        const result = MembershipPlanCreateSchema.safeParse(raw)
        if (!result.success) {
          setFieldErrors(result.error.flatten().fieldErrors)
          return
        }
        setFieldErrors({})
        createPlan.mutate(result.data, {
          onSuccess: (data) => {
            onOpenChange(false)
            toast.success('Тариф создан', { description: data.name })
          },
          onError: (err) => {
            if (err instanceof ApiError && err.fields) {
              const fe: Record<string, string[]> = {}
              for (const [k, v] of Object.entries(err.fields)) {
                fe[k] = Array.isArray(v) ? v.map(String) : [String(v)]
              }
              setServerFieldErrors(fe)
            }
          },
        })
      } else {
        // edit — durationDays, priceKopecks, freezeDaysLimit are immutable
        // (D-101-02). Send ONLY the genuinely-mutable fields so the disabled
        // prefill can never round-trip a stale price/freeze value (WR-02).
        const raw = {
          name: memName.trim() || undefined,
          active: memActive,
        }
        const result = MembershipPlanUpdateSchema.safeParse(raw)
        if (!result.success) {
          setFieldErrors(result.error.flatten().fieldErrors)
          return
        }
        setFieldErrors({})
        if (!plan) return
        updatePlan.mutate({ id: plan.id, body: result.data }, {
          onSuccess: (data) => {
            onOpenChange(false)
            toast.success('Тариф обновлён', { description: data.name })
          },
          onError: (err) => {
            if (err instanceof ApiError && err.fields) {
              const fe: Record<string, string[]> = {}
              for (const [k, v] of Object.entries(err.fields)) {
                fe[k] = Array.isArray(v) ? v.map(String) : [String(v)]
              }
              setServerFieldErrors(fe)
            }
          },
        })
      }
    } else {
      // pt-package
      if (mode === 'create') {
        const raw = {
          name: ptName.trim(),
          sessionCount: parseIntField(ptSessionCount),
          priceKopecks: parsePriceKopecks(ptPriceRub),
          validityDays: parseIntField(ptValidityDays),
        }
        const result = PtPackagePlanCreateSchema.safeParse(raw)
        if (!result.success) {
          setFieldErrors(result.error.flatten().fieldErrors)
          return
        }
        setFieldErrors({})
        createPtPlan.mutate(result.data, {
          onSuccess: (data) => {
            onOpenChange(false)
            toast.success('Услуга создана', { description: data.name })
          },
          onError: (err) => {
            if (err instanceof ApiError && err.fields) {
              const fe: Record<string, string[]> = {}
              for (const [k, v] of Object.entries(err.fields)) {
                fe[k] = Array.isArray(v) ? v.map(String) : [String(v)]
              }
              setServerFieldErrors(fe)
            }
          },
        })
      } else {
        // edit — only name
        const raw = { name: ptName.trim() }
        const result = PtPackagePlanUpdateSchema.safeParse(raw)
        if (!result.success) {
          setFieldErrors(result.error.flatten().fieldErrors)
          return
        }
        setFieldErrors({})
        if (!plan) return
        updatePtPlan.mutate({ id: plan.id, body: result.data }, {
          onSuccess: (data) => {
            onOpenChange(false)
            toast.success('Услуга обновлена', { description: data.name })
          },
          onError: (err) => {
            if (err instanceof ApiError && err.fields) {
              const fe: Record<string, string[]> = {}
              for (const [k, v] of Object.entries(err.fields)) {
                fe[k] = Array.isArray(v) ? v.map(String) : [String(v)]
              }
              setServerFieldErrors(fe)
            }
          },
        })
      }
    }
  }

  // ── Merge client + server field errors ────────────────────────────────────
  const allFieldErrors: Record<string, string[] | undefined> = { ...fieldErrors }
  for (const [k, v] of Object.entries(serverFieldErrors)) {
    allFieldErrors[k] = v
  }

  // ── Metadata ──────────────────────────────────────────────────────────────
  const title =
    kind === 'membership'
      ? mode === 'create' ? 'Новый тариф' : 'Редактировать тариф'
      : mode === 'create' ? 'Новая услуга' : 'Редактировать услугу'

  const ctaLabel =
    kind === 'membership'
      ? mode === 'create' ? 'Создать тариф' : 'Сохранить тариф'
      : mode === 'create' ? 'Создать услугу' : 'Сохранить услугу'

  const cancelLabel = mode === 'create' ? 'Не создавать' : 'Не сохранять'

  const icon =
    mode === 'edit'
      ? <IconChip tone="accent" icon={SquarePen} />
      : kind === 'membership'
        ? <IconChip tone="accent" icon={Dumbbell} />
        : <IconChip tone="accent" icon={Plus} />

  const description =
    mode === 'edit' && plan ? `«${plan.name}»` : undefined

  // ── Required-field check for button disable ───────────────────────────────
  const isRequiredValid =
    kind === 'membership'
      ? mode === 'create'
        ? memName.trim().length > 0 &&
          isIntFieldValid(memDurationDays) &&
          isPriceFieldValid(memPriceRub)
        : memName.trim().length > 0
      : mode === 'create'
        ? ptName.trim().length > 0 &&
          isIntFieldValid(ptSessionCount) &&
          isPriceFieldValid(ptPriceRub)
        : ptName.trim().length > 0

  const isEditMode = mode === 'edit'
  const immutableHint = 'Нельзя изменить после создания'

  // ── Mutation error for ErrorCallout (non-field error only) ────────────────
  const mutError = activeMutation.error
  const hasServerFieldErrors = Object.keys(serverFieldErrors).length > 0
  const showErrorCallout = mutError != null && !hasServerFieldErrors

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      size="wide"
      icon={icon}
      title={title}
      description={description}
      footerActions={
        <>
          <ModalButton
            variant="ghost"
            disabled={isPending}
            onClick={() => onOpenChange(false)}
          >
            {cancelLabel}
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
      {kind === 'membership' ? (
        <>
          {/* Membership plan fields */}
          <Field label="Название" required>
            <ModalInput
              type="text"
              placeholder="Название тарифа"
              value={memName}
              disabled={isPending}
              onChange={(e) => setMemName(e.target.value)}
              maxLength={100}
            />
            {submitAttempted && <FieldError errors={allFieldErrors} field="name" />}
          </Field>
          <FieldRow>
            <Field
              label="Длительность"
              hint={isEditMode ? immutableHint : undefined}
            >
              <ModalInput
                type="number"
                min={1}
                max={3650}
                suffix="дн."
                placeholder="30"
                value={memDurationDays}
                disabled={isPending || isEditMode}
                onChange={(e) => setMemDurationDays(e.target.value)}
              />
              {submitAttempted && <FieldError errors={allFieldErrors} field="durationDays" />}
            </Field>
            <Field
              label="Стоимость"
              hint={isEditMode ? immutableHint : undefined}
            >
              <ModalInput
                type="number"
                min={0}
                suffix="₽"
                placeholder="2000"
                value={memPriceRub}
                disabled={isPending || isEditMode}
                onChange={(e) => setMemPriceRub(e.target.value)}
              />
              {submitAttempted && <FieldError errors={allFieldErrors} field="priceKopecks" />}
            </Field>
          </FieldRow>
          <Field
            label="Дней заморозки"
            optional
            hint={isEditMode ? immutableHint : undefined}
          >
            <ModalInput
              type="number"
              min={0}
              max={365}
              suffix="дн."
              placeholder="14"
              value={memFreezeDays}
              disabled={isPending || isEditMode}
              onChange={(e) => setMemFreezeDays(e.target.value)}
            />
            {submitAttempted && <FieldError errors={allFieldErrors} field="freezeDaysLimit" />}
          </Field>
          <ToggleRow
            title="Активен"
            sub="Тариф виден клиентам и доступен для продажи"
            checked={memActive}
            onChange={setMemActive}
            disabled={isPending}
          />
        </>
      ) : (
        <>
          {/* PT-package plan fields */}
          <Field label="Название" required>
            <ModalInput
              type="text"
              placeholder="Название услуги"
              value={ptName}
              disabled={isPending}
              onChange={(e) => setPtName(e.target.value)}
              maxLength={100}
            />
            {submitAttempted && <FieldError errors={allFieldErrors} field="name" />}
          </Field>
          <FieldRow>
            <Field
              label="Количество занятий"
              hint={isEditMode ? immutableHint : undefined}
            >
              <ModalInput
                type="number"
                min={1}
                max={1000}
                suffix="шт."
                placeholder="10"
                value={ptSessionCount}
                disabled={isPending || isEditMode}
                onChange={(e) => setPtSessionCount(e.target.value)}
              />
              {submitAttempted && <FieldError errors={allFieldErrors} field="sessionCount" />}
            </Field>
            <Field
              label="Стоимость"
              hint={isEditMode ? immutableHint : undefined}
            >
              <ModalInput
                type="number"
                min={1}
                suffix="₽"
                placeholder="5000"
                value={ptPriceRub}
                disabled={isPending || isEditMode}
                onChange={(e) => setPtPriceRub(e.target.value)}
              />
              {submitAttempted && <FieldError errors={allFieldErrors} field="priceKopecks" />}
            </Field>
          </FieldRow>
          <Field
            label="Срок действия"
            optional
            hint={isEditMode ? immutableHint : undefined}
          >
            <ModalInput
              type="number"
              min={1}
              max={3650}
              suffix="дн."
              placeholder="90"
              value={ptValidityDays}
              disabled={isPending || isEditMode}
              onChange={(e) => setPtValidityDays(e.target.value)}
            />
            {submitAttempted && <FieldError errors={allFieldErrors} field="validityDays" />}
          </Field>
        </>
      )}
      {showErrorCallout && <ErrorCallout error={mutError} />}
    </AdaptiveModal>
  )
}
