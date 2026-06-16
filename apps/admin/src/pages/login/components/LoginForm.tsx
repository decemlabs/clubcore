import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Mail, ArrowRight, AlertCircle } from '@/components/icons'
import { Checkbox } from '@/components/ui/Checkbox'
import {
  AuthHeading,
  Field,
  PasswordField,
  PrimaryButton,
  Divider,
  GoogleButton,
  AuthFooter,
  AuthLink,
  Callout,
} from './auth-ui'
import { useLogin, ApiError, LoginRequestSchema } from '@/features/auth/api'

/**
 * Основной экран входа (AUTH-01).
 *
 * Ошибки (T-100-07 anti-oracle):
 *  - invalid_credentials: одиночный баннер «Неверный email или пароль.» без пометки полей
 *  - 422 fields: инлайн-ошибки через Field error prop
 *  - 5xx / network: Sonner toast (форма остаётся интерактивной)
 */
export function LoginForm({
  onSuccess,
  onForgot,
}: {
  onSuccess: () => void
  onForgot: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({})
  // Banner for invalid_credentials (anti-oracle: above email, no field-level aria-invalid).
  const [credentialError, setCredentialError] = useState<string | null>(null)

  const { mutate: login, isPending } = useLogin()

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    // Clear prior errors on each attempt.
    setCredentialError(null)
    setFieldErrors({})

    // Client-side zod validation (mirrors backend LoginRequest — password.min(12)).
    const result = LoginRequestSchema.safeParse({ email, password })
    if (!result.success) {
      const fe = result.error.flatten().fieldErrors
      setFieldErrors({
        email: fe.email?.[0],
        password: fe.password?.[0],
      })
      return
    }

    login(result.data, {
      onSuccess,
      onError: (err) => {
        if (!(err instanceof ApiError)) {
          toast.error('Не удалось выполнить вход', {
            description: 'Проверьте соединение и попробуйте ещё раз.',
          })
          return
        }

        if (err.code === 'invalid_credentials') {
          // T-100-07: single generic banner, no field-level marks (anti-oracle).
          setCredentialError('Неверный email или пароль.')
          return
        }

        if (err.fields && Object.keys(err.fields).length > 0) {
          // 422-style validation error with per-field messages.
          setFieldErrors({
            email: typeof err.fields['email'] === 'string' ? err.fields['email'] : undefined,
            password:
              typeof err.fields['password'] === 'string' ? err.fields['password'] : undefined,
          })
          return
        }

        // Other codes (5xx, network, etc.) — non-blocking toast.
        toast.error('Не удалось выполнить вход', {
          description: 'Проверьте соединение и попробуйте ещё раз.',
        })
      },
    })
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <AuthHeading title="С возвращением" sub="Войдите в админ-панель, чтобы управлять залом." />

      {/* T-100-07: anti-oracle banner — one generic message, no field enumeration. */}
      {credentialError ? (
        <div className="mb-[18px] flex items-center gap-2 rounded-[10px] bg-danger-soft px-[14px] py-[11px] text-[13px] text-danger">
          <AlertCircle className="size-4 shrink-0" />
          {credentialError}
        </div>
      ) : null}

      <Field
        label="Эл. почта"
        name="email"
        type="email"
        autoComplete="username"
        leadIcon={Mail}
        placeholder="you@moizal.ru"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={fieldErrors.email}
        disabled={isPending}
      />

      <PasswordField
        label="Пароль"
        name="password"
        autoComplete="current-password"
        placeholder="Введите пароль"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={fieldErrors.password}
        labelAction={<AuthLink onClick={onForgot}>Забыли пароль?</AuthLink>}
        disabled={isPending}
      />

      <label className="flex cursor-pointer items-center gap-2.5 text-[13px] text-fg-muted select-none">
        <Checkbox checked={remember} onCheckedChange={setRemember} />
        Запомнить меня
      </label>

      {/* Remember-me is a documented no-op: backend cookie TTLs are fixed. */}
      <div className="mb-[22px] mt-2.5">
        <Callout tone="default">
          Сессия действует 7 дней независимо от этого параметра.
        </Callout>
      </div>

      <PrimaryButton type="submit" loading={isPending} icon={ArrowRight}>
        Войти
      </PrimaryButton>

      <Divider />

      {/* Google Workspace login — no-op in Phase 100; will be wired in a future phase. */}
      <GoogleButton
        onClick={() => toast('Google Workspace вход будет доступен позже.')}
      />

      <AuthFooter>
        Нет доступа?{' '}
        <AuthLink onClick={() => toast('Обратитесь к администратору вашего филиала')}>
          Запросить у администратора
        </AuthLink>
      </AuthFooter>
    </form>
  )
}
