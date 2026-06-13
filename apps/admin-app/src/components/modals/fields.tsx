import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Check, ChevronDown } from '@/components/icons';

/** Заголовок секции внутри модалки. */
export function Section({ children }: { children: ReactNode }) {
  return (
    <div className="mb-2.5 mt-[18px] text-[11.5px] font-bold uppercase tracking-[0.5px] text-fg-subtle first:mt-0">
      {children}
    </div>
  );
}

/** Ряд из 2–3 полей (на узких — в одну колонку). */
export function FieldRow({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-2.5',
        cols === 3 ? 'min-[480px]:grid-cols-3' : 'min-[480px]:grid-cols-2',
      )}
    >
      {children}
    </div>
  );
}

export function Field({
  label,
  hint,
  optional,
  required,
  children,
}: {
  label?: string;
  hint?: string;
  optional?: boolean;
  /** Показывает красную звёздочку рядом с подписью (обязательное поле). */
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mb-3.5 last:mb-0">
      {label ? (
        <label className="mb-1.5 block text-xs font-semibold tracking-[-0.05px] text-fg-muted">
          {label}
          {required ? <span className="ml-0.5 text-danger">*</span> : null}
          {optional ? <span className="font-medium text-fg-subtle"> — необязательно</span> : null}
        </label>
      ) : null}
      {children}
      {hint ? <div className="mt-1.5 text-[11.5px] text-fg-subtle">{hint}</div> : null}
    </div>
  );
}

const CONTROL =
  'w-full h-[42px] rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 text-sm text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]';

export function ModalInput({
  icon: Icon,
  suffix,
  className,
  ...props
}: React.ComponentProps<'input'> & { icon?: LucideIcon; suffix?: string }) {
  return (
    <div className="relative">
      {Icon ? (
        <Icon className="pointer-events-none absolute left-[13px] top-1/2 size-[13px] -translate-y-1/2 text-fg-subtle" />
      ) : null}
      <input className={cn(CONTROL, Icon && 'pl-[38px]', suffix && 'pr-9', className)} {...props} />
      {suffix ? (
        <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[13px] text-fg-subtle">
          {suffix}
        </span>
      ) : null}
    </div>
  );
}

export function ModalSelect({ className, children, ...props }: React.ComponentProps<'select'>) {
  return (
    <div className="relative">
      <select className={cn(CONTROL, 'cursor-pointer appearance-none pr-9', className)} {...props}>
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-3.5 top-1/2 size-3 -translate-y-1/2 text-fg-subtle"
        strokeWidth={2.4}
      />
    </div>
  );
}

export function ModalTextarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      className={cn(
        'min-h-20 w-full resize-y rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-3 text-sm leading-snug text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]',
        className,
      )}
      {...props}
    />
  );
}

export interface ChipOption {
  value: string;
  label: ReactNode;
  icon?: LucideIcon;
  sub?: string;
}

export function ChipGroup({
  options,
  value,
  onChange,
}: {
  options: ChipOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const active = o.value === value;
        const Icon = o.icon;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border-[0.5px] px-3.5 py-[9px] text-[13px] font-semibold tracking-[-0.1px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'border-fg bg-fg text-bg dark:border-primary dark:bg-primary dark:text-[#06120c]'
                : 'border-border bg-surface text-fg hover:border-border-strong',
            )}
          >
            {Icon ? <Icon className="size-[13px]" strokeWidth={2.2} /> : null}
            {o.label}
            {o.sub ? (
              <span className="ml-0.5 text-[11px] font-medium opacity-65">{o.sub}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export interface PlanOption {
  value: string;
  name: string;
  price: string;
  sub: string;
  tag?: string;
}

export function PlanCards({
  options,
  value,
  onChange,
}: {
  options: PlanOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(140px,1fr))]">
      {options.map((p) => {
        const active = p.value === value;
        return (
          <button
            key={p.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(p.value)}
            className={cn(
              'relative flex flex-col gap-1 rounded-xl border bg-surface p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'border-[1.5px] border-fg bg-surface-2'
                : 'border-border hover:border-border-strong',
            )}
          >
            {p.tag ? (
              <span className="absolute right-2 top-2 rounded-full bg-primary-soft px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.3px] text-primary-deep dark:text-primary">
                {p.tag}
              </span>
            ) : null}
            <span className="text-[13px] font-[650] tracking-[-0.1px]">{p.name}</span>
            <span className="text-[15px] font-bold tabular-nums tracking-[-0.3px]">{p.price}</span>
            <span className="text-[11px] text-fg-subtle">{p.sub}</span>
          </button>
        );
      })}
    </div>
  );
}

export interface PickOption {
  value: string;
  initials: string;
  color: string;
  name: string;
  sub: string;
}

export function PickRow({
  options,
  value,
  onChange,
}: {
  options: PickOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex gap-2.5 overflow-x-auto pb-1.5 pt-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className="flex w-[72px] shrink-0 flex-col items-center gap-1.5 focus-visible:outline-none"
          >
            <span className="relative">
              <span
                style={{ background: o.color }}
                className={cn(
                  'grid size-14 place-items-center rounded-full border-2 text-[17px] font-bold tracking-[-0.3px] text-white transition-transform',
                  active ? 'border-fg' : 'border-transparent',
                )}
              >
                {o.initials}
              </span>
              {active ? (
                <span className="absolute -bottom-1 -right-1 grid size-[18px] place-items-center rounded-full border-2 border-surface bg-primary text-[#042f1f]">
                  <Check className="size-2.5" strokeWidth={3.5} />
                </span>
              ) : null}
            </span>
            <span className="max-w-[72px] truncate text-[11.5px] font-semibold tracking-[-0.1px]">
              {o.name}
            </span>
            <span className="text-[10px] text-fg-subtle">{o.sub}</span>
          </button>
        );
      })}
    </div>
  );
}

export function ResultList({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-xl border-[0.5px] border-border bg-surface">
      {children}
    </div>
  );
}

export function ResultItem({
  initials,
  color,
  name,
  meta,
  aside,
  active,
  onClick,
}: {
  initials: string;
  color: string;
  name: string;
  meta: string;
  aside?: ReactNode;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-[11px] border-b-[0.5px] border-border px-3 py-2.5 text-left transition-colors last:border-b-0 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
        active && 'bg-surface-3',
      )}
    >
      <span
        style={{ background: color }}
        className="grid size-8 shrink-0 place-items-center rounded-full text-xs font-bold tracking-[-0.2px] text-white"
      >
        {initials}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold tracking-[-0.1px]">{name}</span>
        <span className="mt-px block truncate text-[11.5px] text-fg-subtle">{meta}</span>
      </span>
      {aside ? (
        <span className="shrink-0 text-right text-[11.5px] font-semibold tabular-nums">
          {aside}
        </span>
      ) : null}
    </button>
  );
}

export { Callout } from '@/components/ui/callout';

const BTN_BASE =
  'inline-flex h-10 items-center justify-center gap-[7px] rounded-full px-5 text-[13.5px] font-semibold tracking-[-0.1px] transition-[background-color,border-color,color,transform] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface disabled:pointer-events-none disabled:opacity-50';

const BTN_VARIANTS = {
  primary:
    'bg-fg text-bg hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]',
  ghost:
    'border-[0.5px] border-border bg-surface text-fg hover:border-border-strong hover:bg-surface-2',
  danger: 'bg-danger text-white hover:bg-[#b91c1c]',
  text: 'px-3 text-fg-muted hover:text-fg',
} as const;

export function ModalButton({
  variant = 'primary',
  className,
  ...props
}: React.ComponentProps<'button'> & { variant?: keyof typeof BTN_VARIANTS }) {
  return (
    <button type="button" className={cn(BTN_BASE, BTN_VARIANTS[variant], className)} {...props} />
  );
}

export type IconChipTone = 'accent' | 'warn' | 'danger' | 'indigo';

/** Иконка-чип в шапке модалки; тон задаёт смысл действия. */
export function IconChip({
  tone = 'accent',
  icon: Icon,
}: {
  tone?: IconChipTone;
  icon: LucideIcon;
}) {
  return (
    <span
      className={cn(
        'grid size-11 place-items-center rounded-[13px]',
        tone === 'accent' && 'bg-primary-soft text-primary-deep dark:text-primary',
        tone === 'warn' && 'bg-warning-soft text-warning-deep',
        tone === 'danger' && 'bg-danger-soft text-danger',
        tone === 'indigo' && 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300',
      )}
    >
      <Icon className="size-5" strokeWidth={2} />
    </span>
  );
}

/** Строка «метка — значение» в рамке (новая дата, сумма к возврату и т.п.). */
export function StatRow({
  label,
  value,
  accent,
}: {
  label: ReactNode;
  value: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="mt-3.5 flex items-center gap-2.5 rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-3">
      <span className="text-xs text-fg-muted">{label}</span>
      <span
        className={cn(
          'ml-auto text-[15px] font-bold tabular-nums tracking-[-0.3px]',
          accent && 'text-primary-deep dark:text-primary',
        )}
      >
        {value}
      </span>
    </div>
  );
}

/** Строка с тумблером (уведомить участников, автопродление и т.п.). */
export function ToggleRow({
  title,
  sub,
  checked,
  onChange,
}: {
  title: string;
  sub: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="mt-3.5 flex items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-2.5">
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-semibold">{title}</div>
        <div className="mt-px text-[11.5px] text-fg-subtle">{sub}</div>
      </div>
      <ToggleSwitch checked={checked} onChange={onChange} ariaLabel={title} />
    </div>
  );
}

/** Переключатель-тумблер (автопродление, фиксация цены и т.п.). */
export function ToggleSwitch({
  checked,
  onChange,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-6 w-10 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface',
        checked ? 'bg-primary' : 'bg-border-strong',
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
