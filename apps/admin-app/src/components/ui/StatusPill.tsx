import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Тон статусной пилюли. Домены задают тонкий map (enum статуса → tone + label)
 * и рендерят эту базовую пилюлю — см. features/clients StatusPill.
 */
export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'lead' | 'neutral';

const TONE: Record<StatusTone, { cls: string; dot: string }> = {
  success: {
    cls: 'bg-primary-soft text-primary-deep dark:text-primary',
    dot: 'bg-primary-deep dark:bg-primary',
  },
  warning: { cls: 'bg-warning-soft text-warning-deep', dot: 'bg-warning-deep' },
  danger: { cls: 'bg-danger-soft text-danger', dot: 'bg-danger' },
  info: { cls: 'bg-info-soft text-info', dot: 'bg-info' },
  lead: { cls: 'bg-lead-soft text-lead', dot: 'bg-lead' },
  neutral: { cls: 'bg-surface-3 text-fg-muted', dot: 'bg-fg-subtle' },
};

/** Пилюля статуса с цветной точкой (tone-based). `dot={false}` — без точки. */
export function StatusPill({
  tone = 'neutral',
  dot = true,
  className,
  children,
}: {
  tone?: StatusTone;
  dot?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const t = TONE[tone];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-[5px] whitespace-nowrap rounded-full py-[3px] text-[11.5px] font-semibold tracking-[-0.1px]',
        dot ? 'pl-[7px] pr-[9px]' : 'px-[9px]',
        t.cls,
        className,
      )}
    >
      {dot ? <span className={cn('size-1.5 shrink-0 rounded-full', t.dot)} /> : null}
      {children}
    </span>
  );
}
