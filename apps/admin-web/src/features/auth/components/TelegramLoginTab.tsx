import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { MessageCircle } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/shared/ui/input-otp'
import { isDomainError, ApiError } from '@/shared/api/errors'
import { telegramOtpSchema, type TelegramOtpInput } from '../model/schema'
import { useTelegramStart, useTelegramStatus, useTelegramVerify } from '../api/hooks'

const TIMEOUT_MS = 5 * 60 * 1000

interface Props {
  onSuccess: () => void
}

export function TelegramLoginTab({ onSuccess }: Props) {
  const [token, setToken] = useState<string | null>(null)
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [timedOut, setTimedOut] = useState(false)
  const startedAtRef = useRef<number | null>(null)

  const start = useTelegramStart()
  const status = useTelegramStatus(token, !timedOut)
  const verify = useTelegramVerify()
  const otpForm = useForm<TelegramOtpInput>({
    resolver: zodResolver(telegramOtpSchema),
    defaultValues: { code: '' },
  })

  const handleStart = () => {
    start.mutate(undefined, {
      onSuccess: (r) => {
        // Refuse non-https://t.me/ URLs to prevent javascript: or data: href injection
        // when the backend response is untrusted (real-mode transport).
        if (!r.deepLinkUrl.startsWith('https://t.me/')) {
          console.error('[TelegramLoginTab] Unexpected deepLinkUrl:', r.deepLinkUrl)
          return
        }
        setToken(r.deepLinkToken)
        setDeepLink(r.deepLinkUrl)
        setTimedOut(false)
        startedAtRef.current = Date.now()
      },
    })
  }

  const handleVerify = otpForm.handleSubmit(({ code }) => {
    if (!token) return
    verify.mutate(
      { token, code },
      {
        onSuccess: () => onSuccess(),
        onError: (err) => {
          const c = err instanceof ApiError || isDomainError(err) ? err.code : undefined
          if (c === 'otp_invalid') {
            otpForm.setError('code', { type: 'server', message: 'Неверный код. Попробуйте ещё раз.' })
          } else if (c === 'expired') {
            otpForm.setError('code', { type: 'server', message: 'Код истёк. Получите новый.' })
          } else if (c === 'bot_not_started') {
            otpForm.setError('code', {
              type: 'server',
              message: 'Вы ещё не написали боту. Перейдите по ссылке.',
            })
          } else if (c === 'otp_max_attempts') {
            otpForm.setError('code', {
              type: 'server',
              message: 'Код заблокирован. Начните процесс заново.',
            })
          } else {
            otpForm.setError('code', {
              type: 'server',
              message: 'Ошибка соединения. Проверьте сеть и попробуйте снова.',
            })
          }
        },
      },
    )
  })

  // Timeout watcher — separate effect because polling stops via `enabled=false`
  useEffect(() => {
    if (!startedAtRef.current || timedOut || status.data?.bound) return
    const interval = setInterval(() => {
      if (Date.now() - startedAtRef.current! > TIMEOUT_MS) {
        setTimedOut(true)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [token, timedOut, status.data?.bound])

  const bound = !!status.data?.bound

  // Timed-out state — keep `timedOut=true` until handleStart's onSuccess flips it
  // (handleStart already resets timedOut on success). If start fails, the error stays
  // visible and the user can retry.
  if (timedOut) {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground text-sm">Срок действия ссылки истёк.</p>
        {start.isError && (
          <p className="text-destructive text-sm" role="alert">
            Не удалось получить ссылку. Попробуйте ещё раз.
          </p>
        )}
        <Button
          type="button"
          onClick={() => {
            setToken(null)
            setDeepLink(null)
            startedAtRef.current = null
            handleStart()
          }}
          disabled={start.isPending}
          className="w-full"
        >
          {start.isPending ? 'Получение…' : 'Получить новую ссылку'}
        </Button>
      </div>
    )
  }

  // Initial idle state
  if (!token) {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground text-sm">
          Нажмите кнопку ниже, откройте ссылку в Telegram и дождитесь кода.
        </p>
        <Button onClick={handleStart} disabled={start.isPending} className="w-full">
          <MessageCircle className="mr-2 size-4" />
          {start.isPending ? 'Получение…' : 'Получить ссылку Telegram'}
        </Button>
      </div>
    )
  }

  // Polling state — waiting for chat binding
  if (!bound) {
    return (
      <div className="space-y-4">
        <a
          href={deepLink ?? '#'}
          target="_blank"
          rel="noreferrer"
          className="bg-primary text-primary-foreground hover:bg-primary/90 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md text-sm font-medium"
        >
          <MessageCircle className="size-4" />
          Открыть бота в Telegram
        </a>
        <p className="text-muted-foreground text-sm" aria-live="polite">
          Ожидание подтверждения…
        </p>
      </div>
    )
  }

  // Bound state — OTP entry
  return (
    <form onSubmit={handleVerify} className="space-y-4">
      <p className="text-sm text-green-600 dark:text-green-400" aria-live="polite">
        Чат привязан. Введите код из Telegram.
      </p>
      <div className="space-y-2">
        <Label htmlFor="otp">6-значный код</Label>
        <InputOTP
          maxLength={6}
          value={otpForm.watch('code')}
          onChange={(v) => otpForm.setValue('code', v, { shouldValidate: true })}
        >
          <InputOTPGroup>
            <InputOTPSlot index={0} />
            <InputOTPSlot index={1} />
            <InputOTPSlot index={2} />
            <InputOTPSlot index={3} />
            <InputOTPSlot index={4} />
            <InputOTPSlot index={5} />
          </InputOTPGroup>
        </InputOTP>
        {otpForm.formState.errors.code && (
          <p className="text-destructive text-sm">{otpForm.formState.errors.code.message}</p>
        )}
      </div>
      <Button type="submit" className="w-full" disabled={verify.isPending}>
        {verify.isPending ? 'Проверка…' : 'Подтвердить код'}
      </Button>
    </form>
  )
}
