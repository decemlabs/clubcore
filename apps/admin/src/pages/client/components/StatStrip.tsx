import { StatStrip as BaseStatStrip } from '@/components/layout/StatStrip';
import { StatTile } from '@/components/ui/StatTile';
import type { StatCell } from '@/features/clients/detail';

/** Полоса метрик карточки клиента поверх общих StatStrip + StatTile. */
export function StatStrip({ stats }: { stats: StatCell[] }) {
  return (
    <BaseStatStrip className="grid-cols-2 gap-3 @[560px]:grid-cols-4 @[560px]:gap-4">
      {stats.map((s) => (
        <StatTile
          key={s.label}
          label={s.label}
          value={s.value}
          unit={s.unit}
          foot={s.foot}
          footAccent={s.footAccent}
        />
      ))}
    </BaseStatStrip>
  );
}
