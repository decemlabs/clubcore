import {
  forwardRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react';
import type { LucideIcon } from 'lucide-react';
import { ArrowLeft, AlertCircle, Eye, EyeOff, Loader2, TriangleAlert } from '@/components/icons';
import { cn } from '@/lib/cn';

/** Тон плитки-иконки экрана (scr-icon). */
type IconTone = 'accent' | 'warning' | 'danger';

const ICON_TONE: Record<IconTone, string> = {
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warning: 'bg-warning-soft text-warning-deep',
  danger: 'bg-danger-soft text-danger',
};

/** Крупная плитка-иконка над заголовком экрана. */
export function ScreenIcon({ icon: Icon, tone = 'accent' }: { icon: LucideIcon; tone?: IconTone }) {
  return (
    <span
      className={cn(
        'mb-[22px] grid size-[52px] place-items-center rounded-[15px]',
        ICON_TONE[tone],
      )}
    >
      <Icon className="size-6" strokeWidth={1.9} />
    </span>
  );
}

/** Ссылка «← Назад» над заголовком. */
export function BackLink({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mb-[26px] inline-flex items-center gap-1.5 text-[13px] font-semibold text-fg-muted transition-colors hover:text-fg"
    >
      <ArrowLeft className="size-4" strokeWidth={2.2} />
      {children}
    </button>
  );
}

/** Заголовок + подзаголовок экрана. */
export function AuthHeading({ title, sub }: { title: ReactNode; sub: ReactNode }) {
  return (
    <div className="mb-[26px]">
      <h1 className="text-[22px] font-bold tracking-[-0.6px] text-fg sm:text-[25px]">{title}</h1>
      <p className="mt-2 text-[14px] leading-[1.55] text-fg-muted">{sub}</p>
    </div>
  );
}

/** Текстовое поле с лид-иконкой, опциональной ссылкой в строке метки и ошибкой. */
interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  leadIcon?: LucideIcon;
  error?: string;
  /** Правый элемент в строке метки (напр. ссылка «Забыли пароль?»). */
  labelAction?: ReactNode;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(
  ({ label, leadIcon: Lead, error, labelAction, className, id, ...props }, ref) => {
    const fieldId = id ?? props.name;
    return (
      <div className="mb-[18px]">
        <div className="mb-[7px] flex items-center justify-between">
          <label htmlFor={fieldId} className="text-[12.5px] font-semibold text-fg-muted">
            {label}
          </label>
          {labelAction}
        </div>
        <div className="relative">
          {Lead ? (
            <Lead className="pointer-events-none absolute left-[13px] top-1/2 size-[18px] -translate-y-1/2 text-fg-subtle" />
          ) : null}
          <input
            ref={ref}
            id={fieldId}
            className={cn(
              'h-[46px] w-full rounded-[10px] border bg-surface text-[14.5px] text-fg outline-none transition placeholder:text-fg-subtle',
              Lead ? 'pl-10 pr-3' : 'px-3.5',
              error
                ? 'border-danger focus:ring-[3px] focus:ring-danger-soft'
                : 'border-border-strong focus:border-primary focus:ring-[3px] focus:ring-primary-soft',
              className,
            )}
            aria-invalid={error ? true : undefined}
            {...props}
          />
        </div>
        {error ? (
          <p className="mt-1.5 flex items-center gap-1.5 text-[12px] text-danger">
            <AlertCircle className="size-[14px]" />
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
Field.displayName = 'Field';

/** Поле пароля с переключателем видимости (наследует анатомию Field). */
export function PasswordField({
  label,
  error,
  labelAction,
  ...props
}: Omit<FieldProps, 'leadIcon' | 'type'>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Field
        {...props}
        label={label}
        error={error}
        labelAction={labelAction}
        leadIcon={undefined}
        type={visible ? 'text' : 'password'}
        className="pl-3.5 pr-11"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
        className="absolute right-2 top-[30px] grid size-8 place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg-muted"
      >
        {visible ? <EyeOff className="size-[18px]" /> : <Eye className="size-[18px]" />}
      </button>
    </div>
  );
}

/** Полноширинная основная кнопка. В светлой теме — чернильная, в тёмной — изумрудная. */
export function PrimaryButton({
  children,
  loading,
  icon: Icon,
  className,
  ...props
}: { loading?: boolean; icon?: LucideIcon } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      disabled={loading || props.disabled}
      className={cn(
        'flex h-12 w-full items-center justify-center gap-2 rounded-[10px] text-[14.5px] font-semibold transition-[background,transform] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70',
        'bg-fg text-bg hover:bg-[#000] dark:bg-primary dark:text-primary-foreground dark:hover:bg-[#5ee9b8]',
        className,
      )}
    >
      {loading ? <Loader2 className="size-[18px] animate-spin" /> : null}
      {children}
      {!loading && Icon ? <Icon className="size-[18px]" strokeWidth={2.2} /> : null}
    </button>
  );
}

/** Полноширинная вторичная (ghost) кнопка. */
export function GhostButton({
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        'flex h-11 w-full items-center justify-center gap-2 rounded-[10px] border border-border-strong bg-surface text-[14px] font-semibold text-fg transition-colors hover:bg-surface-3 active:scale-[0.99]',
        className,
      )}
    >
      {children}
    </button>
  );
}

/** Разделитель «или». */
export function Divider({ children = 'или' }: { children?: ReactNode }) {
  return (
    <div className="my-[22px] flex items-center gap-3 text-[12px] text-fg-subtle">
      <span className="h-px flex-1 bg-border" />
      {children}
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

/** Кнопка входа через Google Workspace (фирменный мультицветный «G»). */
export function GoogleButton({ onClick }: { onClick: () => void }) {
  return (
    <GhostButton onClick={onClick}>
      <svg className="size-[18px]" viewBox="0 0 24 24" aria-hidden>
        <path
          fill="#4285F4"
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        />
        <path
          fill="#34A853"
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"
        />
        <path
          fill="#FBBC05"
          d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"
        />
        <path
          fill="#EA4335"
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"
        />
      </svg>
      Войти через Google Workspace
    </GhostButton>
  );
}

/** Подвал экрана с emerald-ссылкой. */
export function AuthFooter({ children }: { children: ReactNode }) {
  return <p className="mt-7 text-center text-[13px] text-fg-muted">{children}</p>;
}

/** Текстовая emerald-ссылка для подвалов / строк меток. */
export function AuthLink({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-semibold text-primary-deep transition-colors hover:underline dark:text-primary"
    >
      {children}
    </button>
  );
}

/** Информационный/предупреждающий блок. */
export function Callout({
  children,
  tone = 'warning',
}: {
  children: ReactNode;
  tone?: 'warning' | 'default';
}) {
  return (
    <div
      className={cn(
        'flex items-start gap-2.5 rounded-[10px] px-[15px] py-[13px] text-[12.5px] leading-[1.5]',
        tone === 'warning'
          ? 'bg-warning-soft text-warning-deep'
          : 'border border-border bg-surface-2 text-fg-muted',
      )}
    >
      <TriangleAlert className="mt-px size-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

/** Пилюля с адресом, на который отправлено письмо. */
export function SentToPill({ email }: { email: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-surface-3 py-[7px] pl-[11px] pr-[14px] text-[13px] font-semibold text-fg">
      <span className="size-[7px] rounded-full bg-primary" />
      {email}
    </span>
  );
}
