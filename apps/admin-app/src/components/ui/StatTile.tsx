import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Компактная карточка-метрика: капс-заголовок + крупное значение (+ед.) + подпись.
 * Базовый «stat tile» для детальных и аналитических страниц.
 */
export function StatTile({
  label,
  value,
  unit,
  foot,
  footAccent,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  foot?: ReactNode;
  /** Акцентный хвост подписи (изумруд). */
  footAccent?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border-[0.5px] border-border bg-surface px-[18px] py-3.5 shadow-1',
        className,
      )}
    >
      <div className="text-[11.5px] font-semibold uppercase tracking-[0.5px] text-fg-subtle">
        {label}
      </div>
      <div className="mt-2 text-[22px] font-bold leading-[1.1] tabular-nums tracking-[-0.5px]">
        {value}
        {unit ? <span className="text-[13px] font-semibold text-fg-subtle">{unit}</span> : null}
      </div>
      {foot || footAccent ? (
        <div className="mt-1 text-[11.5px] text-fg-muted">
          {foot}
          {footAccent ? (
            <span className="font-medium text-primary-deep dark:text-primary">{footAccent}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
