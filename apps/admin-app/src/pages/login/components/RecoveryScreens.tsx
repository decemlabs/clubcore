import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Mail, Lock, CheckCircle2, Check } from '@/components/icons'
import {
  ScreenIcon,
  BackLink,
  AuthHeading,
  Field,
  PasswordField,
  PrimaryButton,
  GhostButton,
  AuthFooter,
  AuthLink,
  SentToPill,
} from './auth-ui'
import { cn } from '@/lib/cn'
import { usePasswordResetRequest, usePasswordResetConfirm, ApiError } from '@/features/auth/api'
import { PasswordResetRequestSchema } from '@/features/auth/schemas'

/* ─── Забыли пароль ─── */
export function ForgotScreen({
  onBack,
  onSent,
}: {
  onBack: () => void
  onSent: (email: string) => void
}) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string>()
  const { mutate: requestReset, isPending } = usePasswordResetRequest()

  const submit = (event: FormEvent) => {
    event.preventDefault()

    // Client-side email validation via schema (backend accepts any string — anti-oracle).
    const parsed = PasswordResetRequestSchema.safeParse({ email })
    if (!parsed.success) {
      setError(parsed.error.flatten().fieldErrors.email?.[0] ?? 'Введите корректный адрес почты')
      return
    }
    setError(undefined)

    requestReset(
      parsed.data,
      {
        onSuccess: () => {
          // Anti-oracle: always proceed to sent screen regardless of backend result.
          onSent(email)
        },
        onError: () => {
          // Backend always returns 202 for this endpoint (anti-oracle).
          // Only genuine 5xx / network errors reach here.
          toast.error('Не удалось отправить ссылку', {
            description: 'Проверьте соединение и попробуйте ещё раз.',
          })
        },
      },
    )
  }

  return (
    <form onSubmit={submit} noValidate>
      <BackLink onClick={onBack}>Назад ко входу</BackLink>
      <ScreenIcon icon={Mail} />
      <AuthHeading
        title="Восстановление пароля"
        sub="Укажите почту, привязанную к аккаунту — вышлем ссылку для сброса."
      />
      <Field
        label="Эл. почта"
        name="email"
        type="email"
        autoComplete="username"
        leadIcon={Mail}
        placeholder="you@moizal.ru"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={error}
        disabled={isPending}
      />
      <PrimaryButton type="submit" loading={isPending}>
        Отправить ссылку
      </PrimaryButton>
      <AuthFooter>
        Вспомнили пароль? <AuthLink onClick={onBack}>Войти</AuthLink>
      </AuthFooter>
    </form>
  )
}

/* ─── Письмо отправлено ─── */
export function SentScreen({
  email,
  onOpenReset,
  onResend,
  onBack,
}: {
  email: string
  onOpenReset: () => void
  onResend: () => void
  onBack: () => void
}) {
  return (
    <div>
      <ScreenIcon icon={CheckCircle2} />
      <AuthHeading
        title="Проверьте почту"
        sub="Мы отправили ссылку для сброса пароля. Она действует 30 минут."
      />
      <div className="mb-[22px]">
        <SentToPill email={email || 'you@moizal.ru'} />
      </div>
      <div className="flex flex-col gap-2.5">
        <PrimaryButton onClick={onOpenReset}>Открыть ссылку из письма</PrimaryButton>
        <GhostButton
          onClick={() => {
            onResend()
            toast('Письмо отправлено повторно')
          }}
        >
          Отправить ещё раз
        </GhostButton>
      </div>
      <AuthFooter>
        Письмо не пришло? Проверьте «Спам» или{' '}
        <AuthLink onClick={onBack}>вернитесь ко входу</AuthLink>
      </AuthFooter>
    </div>
  )
}

/* ─── Сила пароля ─── */
const REQS: { key: string; label: string; test: (v: string) => boolean }[] = [
  { key: 'len', label: '12+ символов', test: (v) => v.length >= 12 },
  {
    key: 'case',
    label: 'Буквы разного регистра',
    test: (v) => /\p{Ll}/u.test(v) && /\p{Lu}/u.test(v),
  },
  { key: 'num', label: 'Хотя бы одна цифра', test: (v) => /\d/.test(v) },
  { key: 'sym', label: 'Символ (!@#$…)', test: (v) => /[^\p{L}\p{N}\s]/u.test(v) },
]

const SCORE_HINT = [
  'Используйте буквы, цифры и символы.',
  'Слабый пароль',
  'Средний пароль',
  'Хороший пароль',
  'Надёжный пароль',
]

const SEGMENT_TONE = (score: number, index: number): string => {
  if (index >= score) return 'bg-border'
  if (score === 1) return 'bg-danger'
  if (score <= 3) return 'bg-warning'
  return 'bg-primary-deep dark:bg-primary'
}

function PasswordStrength({ value }: { value: string }) {
  const met = useMemo(() => REQS.map((r) => r.test(value)), [value])
  const score = met.filter(Boolean).length
  return (
    <div className="-mt-2.5 mb-[18px]">
      <div className="flex gap-1.5">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn('h-1 flex-1 rounded-full transition-colors', SEGMENT_TONE(score, i))}
          />
        ))}
      </div>
      <p className="mt-2 text-[12px] text-fg-muted">{SCORE_HINT[score]}</p>
      <ul className="mt-2.5 grid grid-cols-1 gap-x-4 gap-y-1.5 min-[420px]:grid-cols-2">
        {REQS.map((r, i) => (
          <li key={r.key} className="flex items-center gap-2 text-[12px]">
            <span
              className={cn(
                'grid size-4 shrink-0 place-items-center rounded-full transition-colors',
                met[i] ? 'bg-primary text-primary-foreground' : 'bg-surface-3 text-fg-subtle',
              )}
            >
              <Check className="size-2.5" strokeWidth={3.5} />
            </span>
            <span className={met[i] ? 'text-fg-muted' : 'text-fg-subtle'}>{r.label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ─── Новый пароль ─── */
export function ResetScreen({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({})

  // Extract reset token from URL query string if present (deep-link flow).
  // The token is passed via the email link as a query param: /login?state=reset&token=<value>
  const token = new URLSearchParams(window.location.search).get('token') ?? ''

  const { mutate: confirmReset, isPending } = usePasswordResetConfirm()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const next: typeof errors = {}
    // Guard: token must be present (deep-link flow). Without it the backend call is pointless.
    if (!token) {
      setErrors({ password: 'Ссылка для сброса пароля недействительна. Перейдите по ссылке из письма.' })
      return
    }
    // Mirror backend password.min(12) — T-100-10.
    if (password.length < 12) next.password = 'Пароль должен содержать не менее 12 символов'
    if (confirm !== password) next.confirm = 'Пароли не совпадают'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    confirmReset(
      { token, newPassword: password },
      {
        onSuccess: onDone,
        onError: (err) => {
          if (err instanceof ApiError && err.code === 'weak_password') {
            // T-100-10: backend re-enforces password strength — surface as field error.
            setErrors({ password: 'Пароль слишком простой. Добавьте цифры и символы.' })
            return
          }
          toast.error('Не удалось обновить пароль', {
            description: 'Проверьте соединение и попробуйте ещё раз.',
          })
        },
      },
    )
  }

  return (
    <form onSubmit={submit} noValidate>
      <ScreenIcon icon={Lock} />
      <AuthHeading
        title="Новый пароль"
        sub="Придумайте надёжный пароль — он будет действовать для всех филиалов."
      />
      <PasswordField
        label="Пароль"
        name="new-password"
        autoComplete="new-password"
        placeholder="Новый пароль"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
        disabled={isPending}
      />
      <PasswordStrength value={password} />
      <PasswordField
        label="Повторите пароль"
        name="confirm-password"
        autoComplete="new-password"
        placeholder="Ещё раз"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        error={errors.confirm}
        disabled={isPending}
      />
      <PrimaryButton type="submit" loading={isPending}>
        Сохранить и войти
      </PrimaryButton>
    </form>
  )
}
