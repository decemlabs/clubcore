import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Card } from '@/components/layout/Card';
import type { Rich } from '@/features/trainers/detail';

export { Card };

/** Панель детальной страницы: карточка-оболочка с бордер-шапкой и телом. */
export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return <Card className={className}>{children}</Card>;
}

export function PanelHead({ title, action }: { title: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 border-b-[0.5px] border-border px-[18px] py-[13px]">
      <h2 className="text-sm font-bold tracking-[-0.2px]">{title}</h2>
      {action ? <div className="ml-auto flex shrink-0 items-center">{action}</div> : null}
    </div>
  );
}

export function PanelBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('px-[18px] pb-3.5 pt-1.5', className)}>{children}</div>;
}

/** Лёгкая bold-разметка строки таймлайна. */
export function RichText({ value }: { value: Rich }) {
  if (typeof value === 'string') return <>{value}</>;
  return (
    <>
      {value.map((s, i) =>
        s.b ? (
          <b key={i} className="font-bold text-fg">
            {s.t}
          </b>
        ) : (
          <span key={i}>{s.t}</span>
        ),
      )}
    </>
  );
}

const TAB_BTN =
  'h-[34px] shrink-0 whitespace-nowrap rounded-lg px-[18px] text-[13px] font-semibold transition-[background-color,color,box-shadow] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/** Сегмент-переключатель вкладок детальной страницы (как `.tabs` в макете). */
export function DetailTabs<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
}) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex max-w-full gap-[3px] self-start overflow-x-auto rounded-[11px] bg-surface-3 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              TAB_BTN,
              active ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg',
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
