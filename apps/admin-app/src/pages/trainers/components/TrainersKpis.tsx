import type { LucideIcon } from 'lucide-react';
import { formatInt } from '@/lib/format';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Dumbbell, Star, Users, Wallet } from '@/components/icons';
import type { TrainerKpi, TrainerKpiIcon } from '@/features/trainers/types';

const ICONS: Record<TrainerKpiIcon, LucideIcon> = {
  roster: Users,
  pt: Dumbbell,
  revenue: Wallet,
  rating: Star,
};

function formatValue(kpi: TrainerKpi): string {
  return kpi.valueKind === 'decimal2' ? kpi.value.toFixed(2) : formatInt(kpi.value);
}

export function TrainersKpis({ kpis }: { kpis: TrainerKpi[] }) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <KpiTile
          key={kpi.id}
          icon={ICONS[kpi.icon]}
          label={kpi.label}
          value={formatValue(kpi)}
          unit={kpi.unit}
          delta={kpi.delta}
          footNote={kpi.footNote}
          chips={kpi.chips}
        />
      ))}
    </StatStrip>
  );
}
