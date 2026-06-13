import { useState, type ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Minus, Plus } from '@/components/icons';
import { useSettingsDirty } from './context';

/** Демо-фолбэк: если у кнопки настроек нет своего onClick — показываем тост с её подписью. */
const fallbackToast = (children: ReactNode) => () =>
  toast(typeof children === 'string' ? children : 'Готово');

/* ---------- Section layout ---------- */

export function SectionCard({
  id,
  icon: Icon,
  title,
  desc,
  action,
  danger,
  children,
}: {
  id: string;
  icon: LucideIcon;
  title: string;
  desc: string;
  action?: ReactNode;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      className={cn(
        'scroll-mt-24 overflow-hidden rounded-lg border-[0.5px] shadow-1',
        danger ? 'border-danger/40 bg-danger-soft/30' : 'border-border bg-surface',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b-[0.5px] border-border px-6 py-3.5">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={cn(
              'mt-0.5 grid size-8 shrink-0 place-items-center rounded-[10px]',
              danger ? 'bg-danger-soft text-danger' : 'bg-surface-3 text-fg',
            )}
          >
            <Icon className="size-[18px]" />
          </span>
          <div className="min-w-0">
            <h2 className={cn('text-[16px] font-bold tracking-[-0.3px]', danger && 'text-danger')}>
              {title}
            </h2>
            <p className="mt-0.5 text-[12px] text-fg-muted">{desc}</p>
          </div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="px-6 pb-5 pt-1">{children}</div>
    </section>
  );
}

export function SettingRow({
  label,
  hint,
  children,
  first,
}: {
  label?: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
  first?: boolean;
}) {
  return (
    <div
      className={cn(
        'grid items-start gap-x-6 gap-y-2 py-4 md:grid-cols-[220px_minmax(0,1fr)]',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      {label != null || hint != null ? (
        <div className="min-w-0">
          {label != null ? <div className="text-[13px] font-semibold">{label}</div> : null}
          {hint != null ? (
            <div className="mt-1 text-[11.5px] leading-relaxed text-fg-subtle">{hint}</div>
          ) : null}
        </div>
      ) : (
        <div className="hidden md:block" />
      )}
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/* ---------- Field layout ---------- */

/** Сетка полей 2-в-ряд (на узких — в колонку). Идиома `.field-row`. */
export function FieldGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('grid grid-cols-1 gap-x-4 gap-y-3 min-[520px]:grid-cols-2', className)}>
      {children}
    </div>
  );
}

/** Поле с подписью сверху. */
export function LabeledField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-semibold text-fg-muted">{label}</span>
      {children}
    </label>
  );
}

/* ---------- Controls ---------- */

const FIELD =
  'h-[38px] w-full rounded-[10px] border-[0.5px] border-border-strong bg-surface-2 px-3 text-[13.5px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle focus:bg-surface';

export function TextField({
  defaultValue,
  placeholder,
  sectionId,
}: {
  defaultValue?: string;
  placeholder?: string;
  sectionId: string;
}) {
  const { markDirty } = useSettingsDirty();
  return (
    <input
      type="text"
      defaultValue={defaultValue}
      placeholder={placeholder}
      onChange={() => markDirty(sectionId)}
      className={FIELD}
    />
  );
}

export function SelectField({
  options,
  sectionId,
  className,
}: {
  options: string[];
  sectionId: string;
  className?: string;
}) {
  const { markDirty } = useSettingsDirty();
  return (
    <select
      onChange={() => markDirty(sectionId)}
      className={cn(FIELD, 'cursor-pointer appearance-none', className)}
    >
      {options.map((o) => (
        <option key={o}>{o}</option>
      ))}
    </select>
  );
}

/** Поле с суффиксом-единицей (комиссия %, и т.п.). */
export function MoneyField({
  defaultValue,
  suffix,
  sectionId,
}: {
  defaultValue?: string | number;
  suffix: string;
  sectionId: string;
}) {
  const { markDirty } = useSettingsDirty();
  return (
    <div className="relative">
      <input
        type="text"
        inputMode="numeric"
        defaultValue={defaultValue}
        onChange={() => markDirty(sectionId)}
        className={cn(FIELD, 'pr-9 tabular-nums')}
      />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[13px] font-medium text-fg-subtle">
        {suffix}
      </span>
    </div>
  );
}

export function TextArea({
  defaultValue,
  hint,
  sectionId,
}: {
  defaultValue: string;
  hint?: string;
  sectionId: string;
}) {
  const { markDirty } = useSettingsDirty();
  return (
    <div>
      <textarea
        defaultValue={defaultValue}
        onChange={() => markDirty(sectionId)}
        className={cn(FIELD, 'min-h-[78px] resize-y py-2 leading-relaxed')}
      />
      {hint ? <div className="mt-1 text-[11px] text-fg-subtle">{hint}</div> : null}
    </div>
  );
}

export function Toggle({
  defaultChecked,
  label,
  sub,
  disabled,
  sectionId,
}: {
  defaultChecked?: boolean;
  label?: ReactNode;
  sub?: ReactNode;
  disabled?: boolean;
  sectionId: string;
}) {
  const { markDirty } = useSettingsDirty();
  const [on, setOn] = useState(!!defaultChecked);
  const toggle = () => {
    if (disabled) return;
    setOn((v) => !v);
    markDirty(sectionId);
  };
  return (
    <div className={cn('flex items-start gap-3', disabled && 'opacity-65')}>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        disabled={disabled}
        onClick={toggle}
        className={cn(
          'relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          on ? 'bg-primary' : 'bg-surface-3',
          !disabled && 'cursor-pointer',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 size-4 rounded-full bg-white transition-[left] shadow-sm',
            on ? 'left-[18px]' : 'left-0.5',
          )}
        />
      </button>
      {label != null || sub != null ? (
        <div className="min-w-0">
          {label != null ? <div className="text-[13px] font-semibold">{label}</div> : null}
          {sub != null ? (
            <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">{sub}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Тумблер 40×24 (управляемый). Идиома `.sw` из System-Settings / Branch-Settings. */
export function Switch({
  checked,
  onChange,
  ariaLabel,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  ariaLabel?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={cn(
        'relative h-6 w-10 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface',
        checked ? 'bg-primary' : 'bg-border-strong',
        disabled && 'opacity-50',
      )}
    >
      <span
        className={cn(
          'absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.2)] transition-transform',
          checked && 'translate-x-4',
        )}
      />
    </button>
  );
}

/**
 * Ряд-переключатель (заголовок+подпись слева, тумблер справа) с разделителями
 * между рядами. Идиома `.trow` из System-Settings / Branch-Settings.
 */
export function ToggleRow({
  title,
  sub,
  defaultChecked,
  sectionId,
  first,
}: {
  title: ReactNode;
  sub?: ReactNode;
  defaultChecked?: boolean;
  sectionId: string;
  first?: boolean;
}) {
  const { markDirty } = useSettingsDirty();
  const [on, setOn] = useState(!!defaultChecked);
  return (
    <div className={cn('flex items-center gap-3 py-3', !first && 'border-t-[0.5px] border-border')}>
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold">{title}</div>
        {sub != null ? (
          <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">{sub}</div>
        ) : null}
      </div>
      <Switch
        checked={on}
        ariaLabel={typeof title === 'string' ? title : undefined}
        onChange={(v) => {
          setOn(v);
          markDirty(sectionId);
        }}
      />
    </div>
  );
}

export function RadioGroup({
  options,
  defaultValue,
  sectionId,
}: {
  options: string[];
  defaultValue: string;
  sectionId: string;
}) {
  const { markDirty } = useSettingsDirty();
  const [value, setValue] = useState(defaultValue);
  return (
    <div className="inline-flex flex-wrap gap-0.5 rounded-full border-[0.5px] border-border bg-surface-2 p-[3px]">
      {options.map((o) => {
        const active = o === value;
        return (
          <button
            key={o}
            type="button"
            onClick={() => {
              setValue(o);
              markDirty(sectionId);
            }}
            className={cn(
              'h-[28px] rounded-full px-3 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
                : 'text-fg-muted hover:text-fg',
            )}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}

export function Stepper({
  defaultValue,
  unit,
  min = 0,
  sectionId,
}: {
  defaultValue: number;
  unit: string;
  min?: number;
  sectionId: string;
}) {
  const { markDirty } = useSettingsDirty();
  const [v, setV] = useState(defaultValue);
  const set = (next: number) => {
    setV(Math.max(min, next));
    markDirty(sectionId);
  };
  const BTN =
    'grid h-[38px] w-9 place-items-center text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg';
  return (
    <div className="inline-flex h-[38px] items-center rounded-[10px] border-[0.5px] border-border-strong bg-surface-2">
      <button
        type="button"
        onClick={() => set(v - 1)}
        className={cn(BTN, 'rounded-l-[10px]')}
        aria-label="Меньше"
      >
        <Minus className="size-3.5" />
      </button>
      <span className="grid w-12 place-items-center text-[13.5px] font-semibold tabular-nums">
        {v}
      </span>
      <button type="button" onClick={() => set(v + 1)} className={cn(BTN)} aria-label="Больше">
        <Plus className="size-3.5" />
      </button>
      <span className="px-3 text-[12.5px] text-fg-subtle">{unit}</span>
    </div>
  );
}

/* ---------- Chips & buttons ---------- */

export type ChipTone = 'neutral' | 'accent' | 'warn';
const CHIP_TONE: Record<ChipTone, string> = {
  neutral: 'bg-surface-3 text-fg-muted',
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
};

export function Chip({ tone = 'neutral', children }: { tone?: ChipTone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center rounded-full px-2.5 text-[11.5px] font-semibold',
        CHIP_TONE[tone],
      )}
    >
      {children}
    </span>
  );
}

const BTN_BASE =
  'inline-flex h-[30px] items-center gap-1.5 rounded-lg px-3 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50';

export function GhostBtn({
  danger,
  children,
  onClick,
  ...props
}: React.ComponentProps<'button'> & { danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick ?? fallbackToast(children)}
      className={cn(
        BTN_BASE,
        'border-[0.5px] border-border bg-surface-2 hover:border-border-strong',
        danger ? 'text-danger' : 'text-fg',
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function PrimaryBtn({ children, onClick, ...props }: React.ComponentProps<'button'>) {
  return (
    <button
      type="button"
      onClick={onClick ?? fallbackToast(children)}
      className={cn(
        BTN_BASE,
        'bg-fg text-bg hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]',
      )}
      {...props}
    >
      {children}
    </button>
  );
}
