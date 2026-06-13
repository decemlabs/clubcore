/**
 * New Client modal — wired to real POST /api/v1/clients (Phase 101 CLI-03).
 *
 * Validation via ClientCreateSchema.safeParse() (no react-hook-form in admin-app).
 * On success: toast.success('Клиент добавлен') + close.
 * On 422: map err.fields → inline field errors.
 * On 403: non-blocking toast.error.
 * On 5xx/network: generic toast, form stays open.
 * Submit state: disables buttons + shows spinner.
 */
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Loader2, Phone } from '@/components/icons'
import { useCreateClient, ApiError } from '@/features/clients/api'
import { ClientCreateSchema } from '@/features/clients/schemas'
import { AdaptiveModal } from './AdaptiveModal'
import {
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  Section,
} from './fields'

interface FormState {
  lastName: string
  firstName: string
  middleName: string
  phone: string
  email: string
  birthday: string
  gender: '' | 'male' | 'female'
  notes: string
}

const EMPTY: FormState = {
  lastName: '',
  firstName: '',
  middleName: '',
  phone: '',
  email: '',
  birthday: '',
  gender: '',
  notes: '',
}

type FieldErrors = Partial<Record<keyof FormState, string>>

export function NewClientModal({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [form, setForm] = useState<FormState>(EMPTY)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})

  const { mutate: createClient, isPending } = useCreateClient()

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setForm(EMPTY)
      setFieldErrors({})
    }
  }, [open])

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((s) => ({ ...s, [k]: v }))

  const handleSubmit = () => {
    // Client-side Zod validation
    const parsed = ClientCreateSchema.safeParse({
      lastName: form.lastName,
      firstName: form.firstName,
      middleName: form.middleName || undefined,
      phone: form.phone,
      email: form.email || undefined,
      birthday: form.birthday || undefined,
      gender: form.gender || undefined,
      notes: form.notes || undefined,
    })

    if (!parsed.success) {
      const flat = parsed.error.flatten().fieldErrors
      const errs: FieldErrors = {}
      for (const [k, msgs] of Object.entries(flat)) {
        if (msgs && msgs.length > 0) errs[k as keyof FormState] = msgs[0]
      }
      setFieldErrors(errs)
      return
    }

    setFieldErrors({})
    createClient(parsed.data, {
      onSuccess: () => {
        toast.success('Клиент добавлен')
        onOpenChange(false)
      },
      onError: (err) => {
        if (err instanceof ApiError) {
          if (err.code === 'forbidden') {
            toast.error('Недостаточно прав', {
              description: 'Создание клиентов доступно только сотрудникам.',
            })
            return
          }
          if (err.fields) {
            // 422: backend field errors → inline
            const errs: FieldErrors = {}
            for (const [field, message] of Object.entries(err.fields)) {
              errs[field as keyof FormState] = String(message)
            }
            setFieldErrors(errs)
            return
          }
          toast.error(err.message || 'Не удалось создать клиента. Попробуйте ещё раз.')
        } else {
          toast.error('Не удалось создать клиента. Проверьте соединение и попробуйте ещё раз.')
        }
      },
    })
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      size="wide"
      title="Новый клиент"
      description="Заполните анкету клиента"
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton disabled={isPending} onClick={handleSubmit}>
            {isPending ? (
              <>
                <Loader2 className="size-[16px] animate-spin" />
                Создание…
              </>
            ) : (
              'Создать клиента'
            )}
          </ModalButton>
        </>
      }
    >
      <Section>Профиль</Section>
      <FieldRow>
        <Field label="Фамилия" hint={fieldErrors.lastName}>
          <ModalInput
            placeholder="Иванова"
            autoComplete="family-name"
            value={form.lastName}
            onChange={(e) => set('lastName', e.target.value)}
            disabled={isPending}
          />
        </Field>
        <Field label="Имя" hint={fieldErrors.firstName}>
          <ModalInput
            placeholder="Мария"
            autoComplete="given-name"
            value={form.firstName}
            onChange={(e) => set('firstName', e.target.value)}
            disabled={isPending}
          />
        </Field>
      </FieldRow>
      <Field label="Отчество" optional hint={fieldErrors.middleName}>
        <ModalInput
          placeholder="Сергеевна"
          autoComplete="additional-name"
          value={form.middleName}
          onChange={(e) => set('middleName', e.target.value)}
          disabled={isPending}
        />
      </Field>
      <FieldRow>
        <Field label="Телефон" hint={fieldErrors.phone}>
          <ModalInput
            icon={Phone}
            type="tel"
            placeholder="+79991234567"
            autoComplete="tel"
            value={form.phone}
            onChange={(e) => set('phone', e.target.value)}
            disabled={isPending}
          />
        </Field>
        <Field label="Email" optional hint={fieldErrors.email}>
          <ModalInput
            type="email"
            placeholder="maria@mail.ru"
            autoComplete="email"
            value={form.email}
            onChange={(e) => set('email', e.target.value)}
            disabled={isPending}
          />
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Дата рождения" optional>
          <ModalInput
            type="date"
            value={form.birthday}
            onChange={(e) => set('birthday', e.target.value)}
            disabled={isPending}
          />
        </Field>
        <Field label="Пол" optional>
          <select
            value={form.gender}
            onChange={(e) => set('gender', e.target.value as FormState['gender'])}
            disabled={isPending}
            className="h-[42px] w-full rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 text-sm text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
          >
            <option value="">Не указан</option>
            <option value="female">Женский</option>
            <option value="male">Мужской</option>
          </select>
        </Field>
      </FieldRow>

      <Section>Заметка</Section>
      <Field optional hint={fieldErrors.notes}>
        <textarea
          className="min-h-[80px] w-full resize-none rounded-[10px] border-[0.5px] border-border bg-surface-2 px-3 py-2.5 text-sm text-fg outline-none placeholder:text-fg-subtle focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
          placeholder="Аллергии, пожелания, особенности…"
          maxLength={4096}
          value={form.notes}
          onChange={(e) => set('notes', e.target.value)}
          disabled={isPending}
        />
      </Field>
    </AdaptiveModal>
  )
}
