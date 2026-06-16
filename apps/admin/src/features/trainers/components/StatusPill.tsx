import { cn } from '@/lib/cn';
import { StatusPill as BaseStatusPill, type StatusTone } from '@/components/ui/StatusPill';
import type { TrainerStatusKind } from '@/features/trainers/types';

/** Доменный map: статус тренера → tone + подпись по умолчанию. */
const TRAINER_STATUS: Record<TrainerStatusKind, { tone: StatusTone; label: string }> = {
  on: { tone: 'success', label: 'в зале' },
  'shift-later': { tone: 'neutral', label: 'смена позже' },
  vacation: { tone: 'warning', label: 'отпуск' },
  sick: { tone: 'danger', label: 'больничный' },
  new: { tone: 'info', label: 'новенький' },
};

/**
 * Пилюля статуса тренера (без точки — индикатор статуса живёт на аватаре).
 * `label` переопределяет подпись по умолчанию (приходит из данных).
 */
export function StatusPill({
  status,
  label,
  className,
}: {
  status: TrainerStatusKind;
  label?: string;
  className?: string;
}) {
  const { tone, label: defaultLabel } = TRAINER_STATUS[status];
  return (
    <BaseStatusPill
      tone={tone}
      dot={false}
      className={cn('text-[10.5px] font-bold uppercase tracking-[0.3px]', className)}
    >
      {label ?? defaultLabel}
    </BaseStatusPill>
  );
}
