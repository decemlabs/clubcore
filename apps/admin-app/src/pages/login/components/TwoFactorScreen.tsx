import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from 'react';
import { toast } from 'sonner';
import { ShieldCheck } from '@/components/icons';
import { ScreenIcon, BackLink, AuthHeading, PrimaryButton, AuthFooter, AuthLink } from './auth-ui';
import { cn } from '@/lib/cn';

const LENGTH = 6;

/** 6-значный OTP: автопереход, Backspace назад, вставка распределяется по ячейкам. */
function OtpInput({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  const setAt = (index: number, digit: string) => {
    const chars = value.split('');
    chars[index] = digit;
    onChange(chars.join('').slice(0, LENGTH));
  };

  const handleChange = (index: number, raw: string) => {
    const digit = raw.replace(/\D/g, '').slice(-1);
    if (!digit) return;
    setAt(index, digit);
    if (index < LENGTH - 1) refs.current[index + 1]?.focus();
  };

  const handleKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace' && !value[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    const digits = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, LENGTH);
    if (!digits) return;
    onChange(digits);
    refs.current[Math.min(digits.length, LENGTH - 1)]?.focus();
  };

  return (
    <div className="flex gap-2.5">
      {Array.from({ length: LENGTH }).map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          inputMode="numeric"
          maxLength={1}
          aria-label={`Цифра ${i + 1}`}
          value={value[i] ?? ''}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          className={cn(
            'h-14 min-w-0 flex-1 rounded-[10px] border bg-surface text-center text-[23px] font-bold tabular-nums text-fg outline-none transition',
            value[i]
              ? 'border-fg dark:border-primary'
              : 'border-border-strong focus:border-primary focus:ring-[3px] focus:ring-primary-soft',
          )}
        />
      ))}
    </div>
  );
}

/**
 * Подтверждение входа кодом из приложения-аутентификатора. «Подтвердить» → onConfirm
 * (переход на дашборд). Таймер на повторную отправку — 28 секунд.
 */
export function TwoFactorScreen({
  email,
  onBack,
  onConfirm,
}: {
  email: string;
  onBack: () => void;
  onConfirm: () => void;
}) {
  const [code, setCode] = useState('');
  const [seconds, setSeconds] = useState(28);

  useEffect(() => {
    if (seconds <= 0) return;
    const id = window.setInterval(() => setSeconds((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(id);
  }, [seconds]);

  const resend = () => {
    setSeconds(28);
    toast('Новый код отправлен');
  };

  return (
    <div>
      <BackLink onClick={onBack}>Назад</BackLink>
      <ScreenIcon icon={ShieldCheck} />
      <AuthHeading
        title="Подтверждение входа"
        sub={
          <>
            Введите 6-значный код из приложения-аутентификатора для{' '}
            <b className="font-semibold text-fg">{email || 'm.kostina@moizal.ru'}</b>.
          </>
        }
      />

      <OtpInput value={code} onChange={setCode} />

      <div className="mb-[22px] mt-3.5 flex items-center justify-between text-[12.5px] text-fg-muted">
        {seconds > 0 ? (
          <span>
            Новый код через{' '}
            <b className="font-semibold tabular-nums text-fg">
              0:{String(seconds).padStart(2, '0')}
            </b>
          </span>
        ) : (
          <span />
        )}
        <button
          type="button"
          onClick={resend}
          disabled={seconds > 0}
          className="font-semibold text-primary-deep transition-colors hover:underline disabled:cursor-not-allowed disabled:text-fg-subtle disabled:no-underline dark:text-primary"
        >
          Отправить снова
        </button>
      </div>

      <PrimaryButton onClick={onConfirm} disabled={code.length < LENGTH}>
        Подтвердить
      </PrimaryButton>

      <AuthFooter>
        Нет доступа к приложению?{' '}
        <AuthLink onClick={() => toast('Введите один из резервных кодов')}>
          Ввести резервный код
        </AuthLink>
      </AuthFooter>
    </div>
  );
}
