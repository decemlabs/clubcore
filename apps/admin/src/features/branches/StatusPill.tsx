import { cn } from '@/lib/cn';
import type { BranchStatus } from './types';

const MAP: Record<BranchStatus, { label: string; cls: string }> = {
  active: { label: 'Активен', cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
  soon: { label: 'Скоро', cls: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300' },
  paused: { label: 'Пауза', cls: 'bg-warning-soft text-warning-deep' },
};

/** Капс-пилюля статуса филиала (Активен / Скоро / Пауза). */
export function BranchStatusPill({
  status,
  className,
}: {
  status: BranchStatus;
  className?: string;
}) {
  const s = MAP[status];
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.3px]',
        s.cls,
        className,
      )}
    >
      {s.label}
    </span>
  );
}
