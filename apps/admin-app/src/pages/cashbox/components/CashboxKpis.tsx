import type { LucideIcon } from 'lucide-react';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Banknote, CreditCard, Trash2, Wallet } from '@/components/icons';
import type { CashKpi, CashKpiIcon } from '@/features/cashbox/types';

const ICONS: Record<CashKpiIcon, LucideIcon> = {
  revenue: Banknote,
  cash: Wallet,
  card: CreditCard,
  refund: Trash2,
};

export function CashboxKpis({ kpis }: { kpis: CashKpi[] }) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((k) => (
        <KpiTile
          key={k.id}
          icon={ICONS[k.icon]}
          label={k.label}
          value={k.valueDanger ? <span className="text-danger">{k.value}</span> : k.value}
          unit={k.unit}
          delta={k.delta}
          footNote={k.footNote}
        />
      ))}
    </StatStrip>
  );
}
