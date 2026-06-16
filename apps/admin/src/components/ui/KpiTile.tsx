import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { ChevronDown, ChevronUp } from '@/components/icons';

export type KpiDeltaDirection = 'up' | 'down' | 'flat';
export type KpiChipTone = 'neutral' | 'accent' | 'warn';

export interface KpiTileDelta {
  label: string;
  direction: KpiDeltaDirection;
}
export interface KpiTileChip {
  label: string;
  tone: KpiChipTone;
}

const DELTA_STYLES: Record<KpiDeltaDirection, string> = {
  up: 'bg-primary-soft text-primary-deep dark:text-primary',
  down: 'bg-danger-soft text-danger',
  flat: 'bg-surface-3 text-fg-muted',
};

const CHIP_STYLES: Record<KpiChipTone, string> = {
  neutral: 'bg-surface-3 text-fg-muted',
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
};

/**
 * Метрика-плитка: иконка-чип + капс-метка, крупное значение (+ед.) и футер из
 * дельты / заметки / чипов. Значение форматирует потребитель (целое/дробь/строка).
 * Используется на дашборде (KpiStrip) и странице «Тренеры».
 */
export function KpiTile({
  icon: Icon,
  label,
  value,
  unit,
  delta,
  footNote,
  chips,
  className,
}: {
  icon: LucideIcon;
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: KpiTileDelta;
  footNote?: ReactNode;
  chips?: KpiTileChip[];
  className?: string;
}) {
  const DeltaIcon = delta?.direction === 'down' ? ChevronDown : ChevronUp;

  return (
    <div
      className={cn(
        'flex flex-col rounded-lg border-[0.5px] border-border bg-surface px-5 pb-4 pt-[18px] shadow-1 transition-shadow hover:shadow-2',
        className,
      )}
    >
      <div className="flex items-center gap-2 text-[12.5px] font-medium text-fg-muted">
        <span className="grid size-[26px] shrink-0 place-items-center rounded-[8px] bg-surface-3 text-fg">
          <Icon className="size-[14px]" strokeWidth={2} />
        </span>
        <span className="truncate">{label}</span>
      </div>

      <div className="mt-2.5 text-[30px] font-bold leading-[1.05] tracking-[-0.8px] tabular-nums">
        {value}
        {unit ? (
          <span className="ml-0.5 text-[16px] font-semibold tracking-[-0.2px] text-fg-muted">
            &nbsp;{unit}
          </span>
        ) : null}
      </div>

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-3 text-[12.5px] text-fg-muted">
        {delta ? (
          <span
            className={cn(
              'inline-flex items-center gap-[3px] rounded-full px-[7px] py-0.5 text-xs font-semibold',
              DELTA_STYLES[delta.direction],
            )}
          >
            {delta.direction !== 'flat' ? <DeltaIcon className="size-2.5" strokeWidth={3} /> : null}
            {delta.label}
          </span>
        ) : null}
        {footNote ? <span>{footNote}</span> : null}
        {chips?.map((chip) => (
          <span
            key={chip.label}
            className={cn(
              'inline-flex h-6 items-center rounded-full px-2.5 text-[11.5px] font-semibold',
              CHIP_STYLES[chip.tone],
            )}
          >
            {chip.label}
          </span>
        ))}
      </div>
    </div>
  );
}
