/**
 * Edit Client modal — wired to real PATCH/DELETE /api/v1/clients/{id} (Phase 101 CLI-03).
 *
 * Validation via ClientUpdateSchema.safeParse() (no react-hook-form in admin-app).
 * On PATCH success: toast.success('Изменения сохранены') + close.
 * On DELETE success: toast.success('Клиент удалён') + close.
 * On 422: map err.fields → inline field errors.
 * On 403: non-blocking toast.error.
 * On 5xx/network: generic toast, form stays open.
 * Submit state: disables buttons + shows spinner.
 * Delete button: HIDDEN for reception via can(role, 'delete', 'clients') (T-101-02-OWNERDEL).
 */
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Initials } from '@/components/ui/initials'
import { Segmented } from '@/components/ui/Segmented'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Camera, Loader2, Mail, Phone, Trash2, TriangleAlert } from '@/components/icons'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
import { useClient, useUpdateClient, useDeleteClient, ApiError } from '@/features/clients/api'
import { ClientUpdateSchema } from '@/features/clients/schemas'
import { useModals } from './modals-context'
import { AdaptiveModal } from './AdaptiveModal'
import {
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  ModalTextarea,
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

type FieldErrors = Partial<Record<keyof FormState, string>>

const GENDER_OPTIONS: { value: 'male' | 'female'; label: string }[] = [
  { value: 'female', label: 'Женский' },
  { value: 'male', label: 'Мужской' },
]

interface EditClientModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  clientId?: string
}

function EditClientForm({
  clientId,
  onOpenChange,
}: {
  clientId: string
  onOpenChange: (open: boolean) => void
}) {
  const { open: openModal } = useModals()
  const session = useSession()
  const role = session.data?.role ?? 'reception'

  const { data: client } = useClient(clientId)
  const { mutate: updateClient, isPending: isUpdating } = useUpdateClient()
  const { mutate: deleteClient, isPending: isDeleting } = useDeleteClient()

  const isPending = isUpdating || isDeleting

  const [form, setForm] = useState<FormState>({
    lastName: '',
    firstName: '',
    middleName: '',
    phone: '',
    email: '',
    birthday: '',
    gender: '',
    notes: '',
  })
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [guard, setGuard] = useState(false)

  // Sync form when client data loads
  useEffect(() => {
    if (client) {
      setForm({
        lastName: client.lastName,
        firstName: client.firstName,
        middleName: client.middleName ?? '',
        phone: client.phone,
        email: client.email ?? '',
        birthday: client.birthday ?? '',
        gender: (client.gender as FormState['gender']) ?? '',
        notes: client.notes ?? '',
      })
    }
  }, [client])

  const initial = useMemo<FormState | null>(() => {
    if (!client) return null
    return {
      lastName: client.lastName,
      firstName: client.firstName,
      middleName: client.middleName ?? '',
      phone: client.phone,
      email: client.email ?? '',
      birthday: client.birthday ?? '',
      gender: (client.gender as FormState['gender']) ?? '',
      notes: client.notes ?? '',
    }
  }, [client])

  const dirty = useMemo(
    () => initial !== null && JSON.stringify(form) !== JSON.stringify(initial),
    [form, initial],
  )

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((s) => ({ ...s, [k]: v }))

  const requestClose = (next: boolean) => {
    if (next) return
    if (dirty) setGuard(true)
    else onOpenChange(false)
  }

  const handleSubmit = () => {
    const parsed = ClientUpdateSchema.safeParse({
      lastName: form.lastName || undefined,
      firstName: form.firstName || undefined,
      middleName: form.middleName || undefined,
      phone: form.phone || undefined,
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
    updateClient(
      { id: clientId, body: parsed.data },
      {
        onSuccess: () => {
          toast.success('Изменения сохранены')
          onOpenChange(false)
        },
        onError: (err) => {
          if (err instanceof ApiError) {
            if (err.code === 'forbidden') {
              toast.error('Недостаточно прав', {
                description: 'Редактирование доступно только сотрудникам.',
              })
              return
            }
            if (err.fields) {
              const errs: FieldErrors = {}
              for (const [field, message] of Object.entries(err.fields)) {
                errs[field as keyof FormState] = String(message)
              }
              setFieldErrors(errs)
              return
            }
            toast.error(err.message || 'Не удалось сохранить изменения. Попробуйте ещё раз.')
          } else {
            toast.error('Не удалось сохранить изменения. Проверьте соединение и попробуйте ещё раз.')
          }
        },
      },
    )
  }

  const handleDelete = () => {
    const fullName = [client?.lastName, client?.firstName].filter(Boolean).join(' ')
    onOpenChange(false)
    openModal('confirm', {
      confirm: {
        title: 'Удалить клиента?',
        message: `«${fullName}» будет помечен как удалённый. История посещений сохранится в архиве.`,
        tone: 'danger',
        confirmLabel: 'Удалить',
        requireText: 'УДАЛИТЬ',
        onConfirm: () => {
          deleteClient(clientId, {
            onSuccess: () => {
              toast.success('Клиент удалён')
            },
            onError: (err) => {
              if (err instanceof ApiError && err.code === 'forbidden') {
                toast.error('Недостаточно прав', {
                  description: 'Удаление клиента доступно только владельцу.',
                })
              } else {
                toast.error('Не удалось удалить клиента. Попробуйте ещё раз.')
              }
            },
          })
        },
      },
    })
  }

  const fullName = client
    ? [client.lastName, client.firstName].filter(Boolean).join(' ')
    : '…'

  const initials = client
    ? [client.lastName, client.firstName]
        .filter(Boolean)
        .map((s) => s[0]?.toUpperCase() ?? '')
        .join('')
        .slice(0, 2)
    : ''

  const canDelete = can(role, 'delete', 'clients')

  return (
    <>
      <AdaptiveModal
        open={true}
        onOpenChange={requestClose}
        size="wide"
        icon={
          <Initials
            initials={initials}
            color="linear-gradient(135deg,#2dd4a4,#059669)"
            className="size-11 text-[15px]"
          />
        }
        title="Редактирование клиента"
        description={fullName}
        footerInfo={
          <div className="flex items-center gap-3">
            {/* Delete button — HIDDEN for reception (T-101-02-OWNERDEL defense-in-depth) */}
            {canDelete && (
              <button
                type="button"
                aria-label="Удалить клиента"
                onClick={handleDelete}
                disabled={isPending}
                className="grid size-9 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-danger hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Trash2 className="size-[15px]" />
              </button>
            )}
            {dirty ? (
              <span className="flex items-center gap-1.5 font-medium text-warning-deep">
                <span className="size-[7px] rounded-full bg-current" />
                Несохранённые изменения
              </span>
            ) : (
              <span>Сохранено</span>
            )}
          </div>
        }
        footerActions={
          <>
            <ModalButton variant="ghost" disabled={isPending} onClick={() => requestClose(false)}>
              Отмена
            </ModalButton>
            <ModalButton disabled={isPending || !dirty} onClick={handleSubmit}>
              {isUpdating ? (
                <>
                  <Loader2 className="size-[16px] animate-spin" />
                  Сохранение…
                </>
              ) : (
                'Сохранить'
              )}
            </ModalButton>
          </>
        }
      >
        <Section>Профиль</Section>
        <div className="flex items-center gap-3.5">
          <span className="relative shrink-0">
            <Initials
              initials={initials}
              color="linear-gradient(135deg,#2dd4a4,#059669)"
              className="size-[60px] text-xl"
            />
            <span className="absolute -bottom-0.5 -right-0.5 grid size-[22px] place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted">
              <Camera className="size-3" />
            </span>
          </span>
        </div>

        <div className="mt-3.5">
          <FieldRow>
            <Field label="Фамилия" hint={fieldErrors.lastName}>
              <ModalInput
                value={form.lastName}
                onChange={(e) => set('lastName', e.target.value)}
                disabled={isPending}
              />
            </Field>
            <Field label="Имя" hint={fieldErrors.firstName}>
              <ModalInput
                value={form.firstName}
                onChange={(e) => set('firstName', e.target.value)}
                disabled={isPending}
              />
            </Field>
          </FieldRow>
        </div>
        <Field label="Отчество" optional hint={fieldErrors.middleName}>
          <ModalInput
            value={form.middleName}
            onChange={(e) => set('middleName', e.target.value)}
            disabled={isPending}
          />
        </Field>
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
            <Segmented
              options={GENDER_OPTIONS}
              value={form.gender === '' ? 'female' : form.gender}
              onChange={(v) => set('gender', v as FormState['gender'])}
              ariaLabel="Пол"
            />
          </Field>
        </FieldRow>

        <Section>Контакты</Section>
        <Field label="Телефон" hint={fieldErrors.phone}>
          <ModalInput
            icon={Phone}
            type="tel"
            value={form.phone}
            onChange={(e) => set('phone', e.target.value)}
            disabled={isPending}
          />
        </Field>
        <Field label="Эл. почта" optional hint={fieldErrors.email}>
          <ModalInput
            icon={Mail}
            type="email"
            value={form.email}
            onChange={(e) => set('email', e.target.value)}
            disabled={isPending}
          />
        </Field>

        <Section>Заметка для администраторов</Section>
        <Field hint={fieldErrors.notes}>
          <ModalTextarea
            placeholder="Аллергии, пожелания, особенности…"
            maxLength={4096}
            value={form.notes}
            onChange={(e) => set('notes', e.target.value)}
            disabled={isPending}
          />
        </Field>
      </AdaptiveModal>

      {/* Unsaved changes guard dialog */}
      <Dialog open={guard} onOpenChange={setGuard}>
        <DialogContent
          showCloseButton={false}
          className="gap-0 overflow-hidden rounded-[18px] border-border bg-surface p-0 sm:max-w-[400px]"
        >
          <div className="flex gap-3.5 p-[22px]">
            <span className="grid size-[42px] shrink-0 place-items-center rounded-xl bg-warning-soft text-warning-deep">
              <TriangleAlert className="size-5" />
            </span>
            <div>
              <DialogTitle className="text-base font-bold tracking-[-0.3px]">
                Закрыть без сохранения?
              </DialogTitle>
              <DialogDescription className="mt-1.5 text-[13px] leading-relaxed text-fg-muted">
                В карточке есть несохранённые изменения. Если закрыть сейчас — они будут потеряны.
              </DialogDescription>
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 border-t-[0.5px] border-border bg-surface-2 px-[22px] py-3.5">
            <ModalButton
              variant="text"
              className="text-danger hover:bg-danger-soft hover:text-danger"
              onClick={() => {
                setGuard(false)
                onOpenChange(false)
              }}
            >
              Не сохранять
            </ModalButton>
            <div className="flex gap-2">
              <ModalButton variant="ghost" onClick={() => setGuard(false)}>
                Остаться
              </ModalButton>
              <ModalButton
                onClick={() => {
                  setGuard(false)
                  handleSubmit()
                }}
              >
                Сохранить
              </ModalButton>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export function EditClientModal({ open, onOpenChange, clientId }: EditClientModalProps) {
  if (!open || !clientId) {
    return (
      <AdaptiveModal
        open={false}
        onOpenChange={onOpenChange}
        title="Редактирование клиента"
        size="wide"
        footerActions={<></>}
      >
        <></>
      </AdaptiveModal>
    )
  }

  return <EditClientForm clientId={clientId} onOpenChange={onOpenChange} />
}
