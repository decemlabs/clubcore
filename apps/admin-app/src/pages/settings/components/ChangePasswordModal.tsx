import { useState } from 'react'
import { toast } from 'sonner'
import { Lock } from '@/components/icons'
import { AdaptiveModal } from '@/components/modals/AdaptiveModal'
import { IconChip, ModalButton } from '@/components/modals/fields'
import { useChangePassword, ApiError } from '@/features/auth/api'
import { ChangePasswordSchema } from '@/features/auth/schemas'

// ─── shared inline field class (mirrors SectionsTop.tsx FIELD) ──────────────

const FIELD =
  'h-[38px] w-full rounded-[10px] border-[0.5px] border-border-strong bg-surface-2 px-3 text-[13.5px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle focus:bg-surface'

// ─────────────────────────────────────────────────────────────────────────────
// ChangePasswordModal
//
// AdaptiveModal with three password fields (current / new / confirm).
// Mirrors InviteModal's useState-driven pattern — no react-hook-form (D-101-01-NOHOOKFORM).
// Client validation: min-12 NIST floor + confirm-match (UI-only checks per D-109-03-NO-CONFIRM-ON-WIRE).
// Wrong current password (401 invalid_credentials) → inline field error (T-109-19).
// Success → toast "Пароль изменён. Другие сессии завершены." + sessions invalidated by hook.
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean
  onClose: () => void
}

type FormState = {
  currentPassword: string
  newPassword: string
  confirmPassword: string
  submitting: boolean
}

type FieldErrors = {
  currentPassword?: string
  newPassword?: string
  confirmPassword?: string
}

export function ChangePasswordModal({ open, onClose }: Props) {
  const [form, setForm] = useState<FormState>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    submitting: false,
  })
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const changePassword = useChangePassword()

  // Reset fields + errors on close (setTimeout keeps the transition smooth — mirrors InviteModal)
  function handleOpenChange(value: boolean) {
    if (!value) {
      onClose()
      setTimeout(() => {
        setForm({ currentPassword: '', newPassword: '', confirmPassword: '', submitting: false })
        setFieldErrors({})
      }, 300)
    }
  }

  // Submit is disabled until all three fields are non-empty AND
  // newPassword >= 12 chars AND newPassword === confirmPassword.
  const canSubmit =
    !form.submitting &&
    form.currentPassword.length > 0 &&
    form.newPassword.length >= 12 &&
    form.newPassword === form.confirmPassword

  function handleSubmit() {
    if (!canSubmit) return

    // Run the wire-level schema check first (min-12 floor — mirrors ChangePasswordSchema)
    const result = ChangePasswordSchema.safeParse({
      currentPassword: form.currentPassword,
      newPassword: form.newPassword,
    })
    if (!result.success) {
      const errs: FieldErrors = {}
      for (const issue of result.error.issues) {
        const key = issue.path[0]
        if (key === 'newPassword') errs.newPassword = issue.message
        else if (key === 'currentPassword') errs.currentPassword = issue.message
      }
      setFieldErrors(errs)
      return
    }

    setFieldErrors({})
    setForm((prev) => ({ ...prev, submitting: true }))

    changePassword.mutate(result.data, {
      onSuccess: () => {
        handleOpenChange(false)
        toast.success('Пароль изменён. Другие сессии завершены.')
        // Sessions list is refetched automatically via hook's onSuccess invalidation.
      },
      onError: (err) => {
        setForm((prev) => ({ ...prev, submitting: false }))
        if (
          err instanceof ApiError &&
          (err.code === 'invalid_credentials' ||
            (err.fields?.currentPassword != null))
        ) {
          // T-109-19: map backend wrong-current-password to inline field error
          setFieldErrors({ currentPassword: 'Неверный текущий пароль' })
        } else {
          toast.error('Не удалось изменить пароль. Попробуйте ещё раз.')
        }
      },
    })
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={handleOpenChange}
      title="Сменить пароль"
      icon={<IconChip tone="accent" icon={Lock} />}
      description="Введите текущий пароль и новый пароль (не менее 12 символов)."
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={form.submitting} onClick={() => handleOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            variant="primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {form.submitting ? 'Сохраняем…' : 'Сменить пароль'}
          </ModalButton>
        </>
      }
    >
      <div className="mb-3.5">
        <label className="mb-1.5 block text-[12px] font-semibold text-fg-muted">
          Текущий пароль
        </label>
        <input
          type="password"
          placeholder="Текущий пароль"
          value={form.currentPassword}
          onChange={(e) => {
            setForm((prev) => ({ ...prev, currentPassword: e.target.value }))
            if (fieldErrors.currentPassword) setFieldErrors((prev) => ({ ...prev, currentPassword: undefined }))
          }}
          disabled={form.submitting}
          className={FIELD}
          autoComplete="current-password"
        />
        {fieldErrors.currentPassword ? (
          <div className="mt-1 text-[11px] text-danger">{fieldErrors.currentPassword}</div>
        ) : null}
      </div>
      <div className="mb-3.5">
        <label className="mb-1.5 block text-[12px] font-semibold text-fg-muted">
          Новый пароль
        </label>
        <input
          type="password"
          placeholder="Новый пароль (не менее 12 символов)"
          value={form.newPassword}
          onChange={(e) => {
            setForm((prev) => ({ ...prev, newPassword: e.target.value }))
            if (fieldErrors.newPassword) setFieldErrors((prev) => ({ ...prev, newPassword: undefined }))
          }}
          disabled={form.submitting}
          className={FIELD}
          autoComplete="new-password"
        />
        {fieldErrors.newPassword ? (
          <div className="mt-1 text-[11px] text-danger">{fieldErrors.newPassword}</div>
        ) : null}
      </div>
      <div className="mb-1">
        <label className="mb-1.5 block text-[12px] font-semibold text-fg-muted">
          Подтвердите пароль
        </label>
        <input
          type="password"
          placeholder="Повторите новый пароль"
          value={form.confirmPassword}
          onChange={(e) => {
            setForm((prev) => ({ ...prev, confirmPassword: e.target.value }))
            if (fieldErrors.confirmPassword) setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }))
          }}
          disabled={form.submitting}
          className={FIELD}
          autoComplete="new-password"
        />
        {fieldErrors.confirmPassword ? (
          <div className="mt-1 text-[11px] text-danger">{fieldErrors.confirmPassword}</div>
        ) : null}
      </div>
    </AdaptiveModal>
  )
}
