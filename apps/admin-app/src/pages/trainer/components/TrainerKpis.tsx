import type { LucideIcon } from 'lucide-react';
import { Activity, Clock, Users, Wallet } from '@/components/icons';
import { KpiTile } from '@/components/ui/KpiTile';
import { formatInt } from '@/lib/format';
import type { TrainerDetail, TrainerKpiIcon } from '@/features/trainers/detail';

const ICON: Record<TrainerKpiIcon, LucideIcon> = {
  clients: Users,
  trainings: Activity,
  fill: Clock,
  earnings: Wallet,
};

export function TrainerKpis({ kpis }: { kpis: TrainerDetail['kpis'] }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {kpis.map((k) => (
        <KpiTile
          key={k.id}
          icon={ICON[k.icon]}
          label={k.label}
          value={typeof k.value === 'number' ? formatInt(k.value) : k.value}
          unit={k.unit}
          delta={k.delta}
          footNote={k.footNote}
          chips={k.chips}
        />
      ))}
    </div>
  );
}
