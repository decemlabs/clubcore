/**
 * TrainerFormModal — Phase 102-02 TRN-01.
 *
 * Wired to real PATCH /api/v1/trainers/{id} (edit) and POST /api/v1/trainers (create).
 * Form fields mapped per UI-SPEC §6.3 — only backend-supported fields kept:
 *   - fullName (first + last name joined → string)
 *   - phone (optional)
 *   - specialization (comma-joined spec chips)
 *   - isActive (status toggle: Активна → true)
 *   - bio (note field)
 *   - photoUrl (URL input)
 *
 * Fields WITHOUT backend support are HIDDEN: employment, ratePersonal, rateGroup,
 * commission, branch, email — they belong to the payroll domain (Phase 104).
 *
 * 409 phone_exists → inline Callout (hook suppresses toast; caller renders Callout).
 * PATCH sends only changed fields (omit = no change per PATCH semantics).
 */
import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/cn'
import { Initials } from '@/components/ui/initials'
import { Check, Loader2, TriangleAlert, UserPlus } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import {
  Callout,
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  ModalSelect,
  ModalTextarea,
  Section,
} from './fields'
import { useCreateTrainer, useUpdateTrainer, ApiError } from '@/features/trainers/api'
import type { TrainerData } from '@/features/trainers/schemas'
import { getInitials } from '@/lib/format'

const SPEC_OPTIONS = ['Йога', 'Стретчинг', 'Пилатес', 'Силовые', 'Кардио', 'Бокс', 'Детские группы']

interface FormState {
  firstName: string
  lastName: string
  phone: string
  specs: string[]
  status: 'active' | 'inactive'
  bio: string
  photoUrl: string
}

const CREATE_INITIAL: FormState = {
  firstName: '',
  lastName: '',
  phone: '',
  specs: [],
  status: 'active',
  bio: '',
  photoUrl: '',
}

function trainerToFormState(t: TrainerData): FormState {
  const parts = t.fullName.trim().split(/\s+/)
  return {
    firstName: parts[0] ?? '',
    lastName: parts.slice(1).join(' '),
    phone: t.phone ?? '',
    specs: t.specialization
      ? t.specialization
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      : [],
    status: t.isActive ? 'active' : 'inactive',
    bio: t.bio ?? '',
    photoUrl: t.photoUrl ?? '',
  }
}

/** Мультивыбор специализаций (чипы с галочкой). */
function SpecChips({ value, onToggle }: { value: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SPEC_OPTIONS.map((o) => {
        const on = value.includes(o)
        return (
          <button
            key={o}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(o)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border-[0.5px] px-3.5 py-2 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              on
                ? 'border-fg bg-fg text-bg dark:border-primary dark:bg-primary dark:text-[#06120c]'
                : 'border-border-strong bg-surface text-fg hover:border-fg-subtle',
            )}
          >
            {on ? <Check className="size-3" strokeWidth={3} /> : null}
            {o}
          </button>
        )
      })}
    </div>
  )
}

export function TrainerFormModal({
  open,
  onOpenChange,
  trainer,
  onSuccess,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  trainer?: TrainerData
  onSuccess?: () => void
}) {
  const mode = trainer ? 'edit' : 'create'
  const initial = useMemo(
    () => (trainer ? trainerToFormState(trainer) : CREATE_INITIAL),
    [trainer],
  )

  const [state, setState] = useState<FormState>(initial)
  const [phoneExistsError, setPhoneExistsError] = useState(false)

  const updateTrainer = useUpdateTrainer()
  const createTrainer = useCreateTrainer()

  const isPending = updateTrainer.isPending || createTrainer.isPending

  useEffect(() => {
    if (open) {
      setState(initial)
      setPhoneExistsError(false)
    }
  }, [open, initial])

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setState((s) => ({ ...s, [k]: v }))

  const dirty = useMemo(() => JSON.stringify(state) !== JSON.stringify(initial), [state, initial])

  const buildFullName = () => {
    const parts = [state.firstName.trim(), state.lastName.trim()].filter(Boolean)
    return parts.join(' ')
  }

  const save = async () => {
    setPhoneExistsError(false)
    const fullName = buildFullName()
    if (!fullName) return

    const specialization = state.specs.join(', ') || null
    const phone = state.phone.trim() || null
    const bio = state.bio.trim() || null
    const photoUrl = state.photoUrl.trim() || null
    const isActive = state.status === 'active'

    try {
      if (mode === 'edit' && trainer) {
        // PATCH — only include changed fields
        const body: Record<string, unknown> = {}
        const orig = initial

        if (fullName !== buildFullNameFrom(orig)) body['fullName'] = fullName
        if (phone !== (orig.phone || null)) body['phone'] = phone
        if (specialization !== (orig.specs.join(', ') || null)) body['specialization'] = specialization
        if (bio !== (orig.bio || null)) body['bio'] = bio
        if (photoUrl !== (orig.photoUrl || null)) body['photoUrl'] = photoUrl
        if (isActive !== (orig.status === 'active')) body['isActive'] = isActive

        await updateTrainer.mutateAsync({
          id: trainer.id,
          body,
        })
      } else {
        // POST — create new trainer
        await createTrainer.mutateAsync({
          fullName,
          phone: phone ?? undefined,
        })
      }
      onOpenChange(false)
      onSuccess?.()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'phone_exists') {
        setPhoneExistsError(true)
      }
      // Other errors are toasted by the mutation hook
    }
  }

  const icon =
    mode === 'edit' ? (
      <Initials
        initials={getInitials(trainer?.fullName ?? '')}
        color="linear-gradient(135deg,#8b5cf6,#ec4899)"
        className="size-11 text-[15px]"
      />
    ) : (
      <span className="grid size-11 place-items-center rounded-[13px] bg-primary-soft text-primary-deep dark:text-primary">
        <UserPlus className="size-5" strokeWidth={2} />
      </span>
    )

  const footerInfo = (
    <div className="flex items-center gap-3">
      {dirty ? (
        <span className="flex items-center gap-1.5 font-medium text-warning-deep">
          <span className="size-[7px] rounded-full bg-current" />
          Несохранённые изменения
        </span>
      ) : (
        <span className="text-[13px] text-fg-muted">
          {mode === 'edit' ? 'Сохранено' : 'Все поля можно изменить позже'}
        </span>
      )}
    </div>
  )

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      size="wide"
      icon={icon}
      title={mode === 'create' ? 'Новый тренер' : 'Редактирование тренера'}
      description={
        mode === 'create'
          ? 'Заполните карточку — тренер появится в команде'
          : trainer?.fullName ?? 'Редактирование тренера'
      }
      footerInfo={footerInfo}
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            disabled={(mode === 'edit' && !dirty) || isPending || !buildFullName()}
            onClick={() => void save()}
          >
            {isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : mode === 'create' ? (
              'Добавить тренера'
            ) : (
              'Сохранить'
            )}
          </ModalButton>
        </>
      }
    >
      <Section>Профиль</Section>

      <FieldRow>
        <Field label="Имя" required>
          <ModalInput
            placeholder="Имя"
            value={state.firstName}
            onChange={(e) => set('firstName', e.target.value)}
            autoComplete="given-name"
          />
        </Field>
        <Field label="Фамилия">
          <ModalInput
            placeholder="Фамилия"
            value={state.lastName}
            onChange={(e) => set('lastName', e.target.value)}
            autoComplete="family-name"
          />
        </Field>
      </FieldRow>

      <Field label="Телефон">
        <ModalInput
          type="tel"
          placeholder="+7 ___ ___-__-__"
          value={state.phone}
          onChange={(e) => {
            set('phone', e.target.value)
            setPhoneExistsError(false)
          }}
          autoComplete="tel"
        />
      </Field>

      {phoneExistsError && (
        <Callout tone="danger" icon={TriangleAlert}>
          Этот номер уже используется другим тренером
        </Callout>
      )}

      <Field label="Фото URL" optional>
        <ModalInput
          type="url"
          placeholder="https://example.com/photo.jpg"
          value={state.photoUrl}
          onChange={(e) => set('photoUrl', e.target.value)}
        />
      </Field>

      <Section>Специализация</Section>
      <SpecChips
        value={state.specs}
        onToggle={(v) =>
          set(
            'specs',
            state.specs.includes(v) ? state.specs.filter((s) => s !== v) : [...state.specs, v],
          )
        }
      />

      <Section>Статус и биография</Section>
      <Field label="Статус">
        <ModalSelect value={state.status} onChange={(e) => set('status', e.target.value as 'active' | 'inactive')}>
          <option value="active">Активна</option>
          <option value="inactive">Неактивна</option>
        </ModalSelect>
      </Field>
      <Field label="Заметка / биография" optional>
        <ModalTextarea
          placeholder="Опыт, сертификаты, особенности…"
          value={state.bio}
          onChange={(e) => set('bio', e.target.value)}
        />
      </Field>
    </AdaptiveModal>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildFullNameFrom(state: FormState): string {
  const parts = [state.firstName.trim(), state.lastName.trim()].filter(Boolean)
  return parts.join(' ')
}
