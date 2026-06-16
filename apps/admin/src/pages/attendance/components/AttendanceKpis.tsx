import type { LucideIcon } from 'lucide-react';
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Activity, CircleX, LogIn, Users } from '@/components/icons';
import type { AttKpi, AttKpiIcon } from '@/features/attendance/types';

const ICONS: Record<AttKpiIcon, LucideIcon> = {
  visits: LogIn,
  active: Users,
  avg: Activity,
  noshow: CircleX,
};

export function AttendanceKpis({ kpis }: { kpis: AttKpi[] }) {
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
          footNote={
            <>
              {k.foot.pre}
              {k.foot.strong ? <b className="font-semibold text-fg">{k.foot.strong}</b> : null}
              {k.foot.post}
            </>
          }
        />
      ))}
    </StatStrip>
  );
}
