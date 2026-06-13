import type { LucideIcon } from 'lucide-react';
import { formatInt } from '@/lib/format';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Activity, LogIn, Users, Wallet } from '@/components/icons';
import type { KpiCard, KpiIconName } from '@/features/dashboard/types';

const ICONS: Record<KpiIconName, LucideIcon> = {
  members: Users,
  revenue: Wallet,
  trainings: Activity,
  visits: LogIn,
};

export function KpiStrip({ kpis }: { kpis: KpiCard[] }) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <KpiTile
          key={kpi.id}
          icon={ICONS[kpi.icon]}
          label={kpi.label}
          value={formatInt(kpi.value)}
          unit={kpi.unit}
          delta={kpi.delta}
          footNote={kpi.footNote}
          chips={kpi.chips}
        />
      ))}
    </StatStrip>
  );
}
