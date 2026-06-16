import type { LucideIcon } from 'lucide-react';
import { formatInt } from '@/lib/format';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Activity, Banknote, CreditCard, TrendingUp } from '@/components/icons';
import type { PlanKpi, PlanKpiIcon } from '@/features/plans/types';

const ICONS: Record<PlanKpiIcon, LucideIcon> = {
  subs: CreditCard,
  mrr: Banknote,
  avg: Activity,
  funnel: TrendingUp,
};

function formatValue(kpi: PlanKpi): string {
  return kpi.valueKind === 'percent' ? `${kpi.value}%` : formatInt(kpi.value);
}

export function PlansKpis({ kpis }: { kpis: PlanKpi[] }) {
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
