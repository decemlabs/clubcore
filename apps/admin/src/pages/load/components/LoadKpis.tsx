/**
 * LoadKpis — KPI strip for the visits load dashboard (Phase 103-03).
 *
 * Replaced mock LoadKpi[] structure with real values from the visits report:
 *   - Среднее в день: averagePerDay from the report response
 *   - Всего визитов: sum of daily.count across the range
 */
import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Activity, TrendingUp } from '@/components/icons';

export function LoadKpis({
  averagePerDay,
  totalVisits,
}: {
  averagePerDay: number;
  totalVisits: number;
}) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2">
      <KpiTile
        icon={TrendingUp}
        label="Среднее в день"
        value={averagePerDay.toFixed(1)}
        unit="визитов"
      />
      <KpiTile
        icon={Activity}
        label="Всего визитов"
        value={String(totalVisits)}
        unit="визитов"
      />
    </StatStrip>
  );
}
