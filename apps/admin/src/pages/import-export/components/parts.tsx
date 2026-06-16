import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Panel as PanelShell, PanelTitle, PanelBody } from '@/components/layout/Panel';
import { Upload, FileText, X, ArrowRight, Check, CircleX } from '@/components/icons';
import type { MapRow, PreviewRow, ErrorRow } from '@/features/import-export/types';

/* ---------- Buttons ---------- */

const BTN =
  'inline-flex h-[38px] items-center justify-center gap-[7px] rounded-[10px] px-4 text-[13px] font-semibold transition-colors active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-45';
const VARIANTS = {
  primary:
    'bg-fg text-bg hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]',
  ghost: 'border-[0.5px] border-border-strong bg-surface text-fg hover:bg-surface-3',
} as const;

export function Btn({
  variant = 'primary',
  sm,
  className,
  ...props
}: React.ComponentProps<'button'> & { variant?: keyof typeof VARIANTS; sm?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        BTN,
        VARIANTS[variant],
        sm && 'h-8 gap-1.5 rounded-[9px] px-[11px] text-[12.5px]',
        className,
      )}
      {...props}
    />
  );
}

/* ---------- Panel ---------- */

export function Panel({
  title,
  caption,
  bodyless,
  children,
}: {
  title?: string;
  caption?: ReactNode;
  bodyless?: boolean;
  children: ReactNode;
}) {
  return (
    <PanelShell>
      {title ? <PanelTitle title={title} caption={caption} /> : null}
      {bodyless ? children : <PanelBody>{children}</PanelBody>}
    </PanelShell>
  );
}

/* ---------- Callout ---------- */

const CALLOUT = {
  info: {
    box: 'border-[0.5px] border-border bg-surface-2',
    icon: 'text-fg-muted',
    text: 'text-fg-muted',
  },
  warn: {
    box: 'border-transparent bg-warning-soft',
    icon: 'text-warning-deep',
    text: 'text-warning-deep',
  },
  ok: {
    box: 'border-transparent bg-primary-soft',
    icon: 'text-primary-deep dark:text-primary',
    text: 'text-primary-deep dark:text-primary',
  },
} as const;

export function Callout({
  tone,
  icon: Icon,
  children,
}: {
  tone: keyof typeof CALLOUT;
  icon: LucideIcon;
  children: ReactNode;
}) {
  const c = CALLOUT[tone];
  return (
    <div
      className={cn(
        'flex items-start gap-2.5 rounded-xl border p-[12px_14px] text-[12.5px] leading-relaxed',
        c.box,
        c.text,
      )}
    >
      <Icon className={cn('mt-px size-[18px] shrink-0', c.icon)} strokeWidth={2} />
      <div className="[&_b]:font-semibold [&_b]:text-fg">{children}</div>
    </div>
  );
}

/* ---------- Stepper ---------- */

export interface Step {
  key: string;
  label: string;
}

export function Stepper({
  steps,
  current,
  onGo,
}: {
  steps: Step[];
  current: number;
  onGo: (i: number) => void;
}) {
  return (
    <div className="-mx-0.5 flex gap-0.5 overflow-x-auto rounded-full border-[0.5px] border-border bg-surface p-1.5 shadow-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {steps.map((s, i) => {
        const active = i === current;
        const done = i < current;
        return (
          <button
            key={s.key}
            type="button"
            onClick={() => onGo(i)}
            className={cn(
              'inline-flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-full px-3 py-2 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'bg-fg text-bg dark:bg-surface-3 dark:text-fg'
                : done
                  ? 'text-primary-deep dark:text-primary'
                  : 'text-fg-subtle hover:text-fg-muted',
            )}
          >
            <span
              className={cn(
                'grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-bold',
                active
                  ? 'bg-primary text-[#06120c]'
                  : done
                    ? 'bg-primary-soft text-primary-deep dark:text-primary'
                    : 'bg-surface-3 text-fg-muted',
              )}
            >
              {i + 1}
            </span>
            {s.label}
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Upload pane ---------- */

export function Dropzone({ onPick }: { onPick: () => void }) {
  return (
    <div className="flex flex-col items-center rounded-[14px] border-[1.5px] border-dashed border-border-strong bg-surface-2 px-6 py-9 text-center">
      <span className="mb-3.5 grid size-[54px] place-items-center rounded-[15px] bg-surface-3 text-fg-muted">
        <Upload className="size-6" strokeWidth={1.9} />
      </span>
      <div className="text-[14.5px] font-[650]">Перетащите файл сюда</div>
      <div className="mb-4 mt-1 text-[12.5px] text-fg-subtle">или выберите на устройстве</div>
      <Btn variant="ghost" onClick={onPick}>
        Выбрать файл
      </Btn>
    </div>
  );
}

export function FileChip({
  name,
  meta,
  onRemove,
}: {
  name: string;
  meta: string;
  onRemove: () => void;
}) {
  return (
    <div className="mt-3.5 flex items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface-2 p-[12px_14px]">
      <span className="grid size-[38px] shrink-0 place-items-center rounded-[10px] bg-primary-soft text-primary-deep dark:text-primary">
        <FileText className="size-[18px]" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] font-semibold">{name}</div>
        <div className="truncate text-[11.5px] text-fg-subtle">{meta}</div>
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label="Убрать файл"
        className="grid size-[30px] shrink-0 place-items-center rounded-full text-fg-subtle transition-colors hover:bg-surface-3 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="size-[15px]" strokeWidth={2.2} />
      </button>
    </div>
  );
}

/* ---------- Map pane ---------- */

export function MapRowItem({
  row,
  fields,
  value,
  onChange,
}: {
  row: MapRow;
  fields: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const skip = value === fields[fields.length - 1];
  return (
    <div className="grid grid-cols-1 items-center gap-2.5 border-b-[0.5px] border-border py-2.5 last:border-b-0 sm:grid-cols-[1fr_28px_1fr] sm:gap-3">
      <div>
        <div className="rounded-[9px] border-[0.5px] border-border bg-surface-2 px-3 py-2.5 font-mono text-[13px] font-semibold">
          {row.src}
        </div>
        <div className="mt-0.5 text-[11px] text-fg-subtle">напр.: {row.sample}</div>
      </div>
      <ArrowRight className="hidden size-4 justify-self-center text-fg-subtle sm:block" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'h-[42px] w-full cursor-pointer appearance-none rounded-[9px] border-[0.5px] border-border-strong bg-surface-2 px-3.5 pr-9 text-[13.5px] outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]',
          skip ? 'text-fg-subtle' : 'text-fg',
          "bg-[url('data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20width=%2712%27%20height=%2712%27%20viewBox=%270%200%2024%2024%27%20fill=%27none%27%20stroke=%27%23a8a29e%27%20stroke-width=%272.4%27%20stroke-linecap=%27round%27%3E%3Cpolyline%20points=%276%209%2012%2015%2018%209%27/%3E%3C/svg%3E')] bg-[right_13px_center] bg-no-repeat",
        )}
      >
        {fields.map((f) => (
          <option key={f}>{f}</option>
        ))}
      </select>
    </div>
  );
}

/* ---------- Preview pane ---------- */

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={cn(
        'grid size-[22px] shrink-0 place-items-center rounded-full',
        ok ? 'bg-primary-soft text-primary-deep dark:text-primary' : 'bg-danger-soft text-danger',
      )}
    >
      {ok ? (
        <Check className="size-3" strokeWidth={3} />
      ) : (
        <CircleX className="size-3.5" strokeWidth={2.6} />
      )}
    </span>
  );
}

function PvCell({ value, bad, primary }: { value: string; bad?: boolean; primary?: boolean }) {
  return (
    <span
      className={cn(
        'truncate text-[12.5px] max-md:col-start-2',
        bad
          ? 'font-semibold text-danger'
          : primary
            ? 'font-medium text-fg max-md:text-[13.5px]'
            : 'max-md:text-fg-subtle',
      )}
    >
      {value || '—'}
    </span>
  );
}

export function PreviewTable({ rows }: { rows: PreviewRow[] }) {
  return (
    <div>
      <div className="hidden grid-cols-[36px_1.4fr_1.2fr_1fr_1fr] gap-3 border-b-[0.5px] border-border px-3.5 py-2.5 text-[10.5px] font-bold uppercase tracking-[0.5px] text-fg-subtle md:grid">
        <span />
        <span>Имя</span>
        <span>Телефон</span>
        <span>Абонемент</span>
        <span>Email</span>
      </div>
      {rows.map((r, i) => (
        <div
          key={i}
          className={cn(
            'grid grid-cols-[22px_minmax(0,1fr)] items-start gap-x-3 gap-y-1 border-b-[0.5px] border-border px-3.5 py-2.5 last:border-b-0 md:grid-cols-[36px_1.4fr_1.2fr_1fr_1fr] md:items-center md:gap-3',
            !r.ok && 'bg-danger-soft dark:bg-danger/[0.08]',
          )}
        >
          <StatusDot ok={r.ok} />
          <PvCell value={r.name} bad={r.bad.includes(0)} primary />
          <PvCell value={r.phone} bad={r.bad.includes(1)} />
          <PvCell value={r.plan} bad={r.bad.includes(2)} />
          <PvCell value={r.email} bad={r.bad.includes(3)} />
        </div>
      ))}
    </div>
  );
}

/* ---------- Errors pane ---------- */

export function ErrorRowItem({ row, onSkip }: { row: ErrorRow; onSkip: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b-[0.5px] border-border py-3 last:border-b-0">
      <span className="grid size-[30px] shrink-0 place-items-center rounded-lg bg-danger-soft text-[11px] font-bold tabular-nums text-danger">
        {row.line}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-semibold">{row.title}</div>
        <div className="mt-px text-[11.5px] text-fg-subtle">{row.detail}</div>
      </div>
      <Btn variant="ghost" sm onClick={onSkip} className="max-sm:w-full">
        Пропустить
      </Btn>
    </div>
  );
}

/* ---------- Export pane ---------- */

export function FormatCard({
  icon: Icon,
  name,
  sub,
  active,
  onClick,
}: {
  icon: LucideIcon;
  name: string;
  sub: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex flex-col items-center gap-2 rounded-xl border bg-surface p-3.5 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active
          ? 'border-[1.5px] border-fg bg-surface-2 dark:border-primary'
          : 'border-border-strong hover:border-fg-subtle',
      )}
    >
      <span
        className={cn(
          'grid size-[38px] place-items-center rounded-[11px]',
          active
            ? 'bg-primary-soft text-primary-deep dark:text-primary'
            : 'bg-surface-3 text-fg-muted',
        )}
      >
        <Icon className="size-[18px]" strokeWidth={2} />
      </span>
      <span className="text-[13px] font-[650]">{name}</span>
      <span className="text-[11px] text-fg-subtle">{sub}</span>
    </button>
  );
}

export function ChecklistItem({
  label,
  checked,
  onToggle,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={checked}
      className="flex w-full items-center gap-2.5 py-2.5 text-left text-[13px] focus-visible:outline-none"
    >
      <span
        className={cn(
          'grid size-[18px] shrink-0 place-items-center rounded-[5px] border-[1.5px] transition-colors',
          checked
            ? 'border-fg bg-fg text-bg dark:border-primary dark:bg-primary dark:text-[#06120c]'
            : 'border-border-strong text-transparent',
        )}
      >
        <Check className="size-3" strokeWidth={3} />
      </span>
      {label}
    </button>
  );
}
