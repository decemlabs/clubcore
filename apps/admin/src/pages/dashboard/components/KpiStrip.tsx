import { StatStrip } from '@/components/layout/StatStrip';
import { KpiTile } from '@/components/ui/KpiTile';
import { Activity, LogIn, Users, Wallet } from '@/components/icons';
import { formatRub } from '@/lib/format';

export interface KpiStripData {
  /** Net revenue in kopecks (today). Guard: undefined/null/NaN → 0. */
  netKopecks: number | undefined | null;
  /** Total visits today. Guard: undefined/null/NaN → 0. */
  visitsToday: number | undefined | null;
  /** Expiring memberships within 7 days. */
  expiringCount: number | undefined | null;
  /** Confirmed bookings today. */
  bookingsToday: number | undefined | null;
}

function safeInt(v: number | undefined | null): number {
  if (v == null || !Number.isFinite(v)) return 0;
  return Math.round(v);
}

export function KpiStrip({ data }: { data: KpiStripData }) {
  const netRub = safeInt((data.netKopecks ?? 0) / 100);
  const visits = safeInt(data.visitsToday);
  const expiring = safeInt(data.expiringCount);
  const bookings = safeInt(data.bookingsToday);

  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiTile
        icon={Wallet}
        label="Выручка сегодня"
        value={formatRub(netRub)}
      />
      <KpiTile
        icon={LogIn}
        label="Посещений сегодня"
        value={String(visits)}
      />
      <KpiTile
        icon={Users}
        label="Истекают (7 дней)"
        value={String(expiring)}
      />
      <KpiTile
        icon={Activity}
        label="Тренировок сегодня"
        value={String(bookings)}
      />
    </StatStrip>
  );
}
