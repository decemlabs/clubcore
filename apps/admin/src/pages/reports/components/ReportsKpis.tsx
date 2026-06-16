import type { LucideIcon } from 'lucide-react';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Banknote, CreditCard, Heart, UserPlus } from '@/components/icons';
import type { ReportKpi, ReportKpiIcon } from '@/features/reports/types';

const ICONS: Record<ReportKpiIcon, LucideIcon> = {
  revenue: Banknote,
  newClients: UserPlus,
  retention: Heart,
  avgCheck: CreditCard,
};

export function ReportsKpis({ kpis }: { kpis: ReportKpi[] }) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((k) => (
        <KpiTile
          key={k.id}
          icon={ICONS[k.icon]}
          label={k.label}
          value={k.value}
          unit={k.unit}
          delta={k.delta}
          footNote={k.footNote}
        />
      ))}
    </StatStrip>
  );
}
