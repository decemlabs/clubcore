import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Eye, EyeOff } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { isDomainError, ApiError } from '@/shared/api/errors'
import { emailLoginSchema, type EmailLoginInput } from '../model/schema'
import { useLogin } from '../api/hooks'

interface Props {
  onSuccess: () => void
}

export function EmailLoginForm({ onSuccess }: Props) {
  const [showPassword, setShowPassword] = useState(false)
  const form = useForm<EmailLoginInput>({
    resolver: zodResolver(emailLoginSchema),
    defaultValues: { email: '', password: '' },
  })
  const login = useLogin()

  const onSubmit = form.handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => onSuccess(),
      onError: (err) => {
        const code = err instanceof ApiError || isDomainError(err) ? err.code : undefined
        if (code === 'invalid_credentials') {
          form.setError('root', { type: 'server', message: 'Неверный email или пароль.' })
        } else if (code === 'rate_limited') {
          form.setError('root', {
            type: 'server',
            message: 'Слишком много попыток. Попробуйте через несколько минут.',
          })
        } else if (code === 'validation_failed') {
          const fields =
            err instanceof ApiError || isDomainError(err) ? err.fields : undefined
          if (fields) {
            for (const [k, v] of Object.entries(fields)) {
              const msg = Array.isArray(v) ? String(v[0] ?? '') : String(v)
              form.setError(k as keyof EmailLoginInput, { type: 'server', message: msg })
            }
          }
        } else {
          form.setError('root', {
            type: 'server',
            message: 'Ошибка соединения. Проверьте сеть и попробуйте снова.',
          })
        }
      },
    })
  })

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="username"
          {...form.register('email')}
          aria-invalid={!!form.formState.errors.email}
        />
        {form.formState.errors.email && (
          <p className="text-destructive text-sm">{form.formState.errors.email.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Пароль</Label>
        <div className="relative">
          <Input
            id="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            {...form.register('password')}
            aria-invalid={!!form.formState.errors.password}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1 h-8 w-8"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
          >
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </Button>
        </div>
        {form.formState.errors.password && (
          <p className="text-destructive text-sm">{form.formState.errors.password.message}</p>
        )}
      </div>
      {form.formState.errors.root && (
        <div
          role="alert"
          className="border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm"
        >
          {form.formState.errors.root.message}
        </div>
      )}
      <Button type="submit" className="w-full" disabled={login.isPending}>
        {login.isPending ? 'Вход…' : 'Войти'}
      </Button>
    </form>
  )
}
