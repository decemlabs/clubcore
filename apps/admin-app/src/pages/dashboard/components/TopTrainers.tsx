import { ROUTES } from '@/app/routes';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ChevronRight, Users } from '@/components/icons';
import { cn } from '@/lib/cn';
import { formatRub, getInitials } from '@/lib/format';
import type { TrainersReportData, TrainerRow } from '@/features/reports/schemas';
import { CardLink, DashboardCard, Initials } from './shared';

interface TopTrainersProps {
  data: TrainersReportData | undefined;
  isPending: boolean;
  month: string; // e.g. "июнь 2026"
}

const COLORS = [
  '#4f46e5',
  '#0891b2',
  '#059669',
  '#d97706',
  '#dc2626',
];

function TrainerRowItem({ trainer, first, maxRevenue }: { trainer: TrainerRow; first: boolean; maxRevenue: number }) {
  const initials = getInitials(trainer.name);
  const colorIdx = trainer.trainerId.charCodeAt(0) % COLORS.length;
  const color = COLORS[colorIdx] ?? '#4f46e5';
  const barPct = maxRevenue > 0 ? Math.round((trainer.totalRevenueKopecks / maxRevenue) * 100) : 0;
  const revenueRub = Number.isFinite(trainer.totalRevenueKopecks)
    ? Math.max(Math.round(trainer.totalRevenueKopecks / 100), 0)
    : 0;

  return (
    <div
      className={cn(
        'grid grid-cols-[32px_minmax(0,1fr)_auto_auto] items-center gap-3 px-5 py-[11px] transition-colors hover:bg-surface-2',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      <Initials initials={initials} color={color} className="size-8 text-[11px]" />

      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold">{trainer.name}</div>
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full bg-fg dark:bg-primary"
            style={{ width: `${barPct}%` }}
          />
        </div>
        <div className="mt-1 text-[11.5px] tabular-nums text-fg-subtle">
          {trainer.sessionCount} сессий · {trainer.utilizationPct}% загруженность
        </div>
      </div>

      <div className="text-right text-[13px] font-bold tracking-[-0.2px] tabular-nums">
        {formatRub(revenueRub)}
        <small className="block text-[10.5px] font-medium tracking-normal text-fg-subtle">
          выручка
        </small>
      </div>

      <span
        aria-hidden
        className="grid size-[30px] place-items-center rounded-lg bg-fg text-bg dark:bg-primary dark:text-[#06120c] @max-[400px]:hidden"
      >
        <ChevronRight className="size-[14px]" strokeWidth={2.4} />
      </span>
    </div>
  );
}

export function TopTrainers({ data, isPending, month }: TopTrainersProps) {
  const rows = data?.rows ?? [];
  const sorted = [...rows]
    .sort((a, b) => b.totalRevenueKopecks - a.totalRevenueKopecks)
    .slice(0, 5);
  const maxRevenue = sorted[0]?.totalRevenueKopecks ?? 1;

  return (
    <DashboardCard
      title={`Топ тренеры · ${month}`}
      subtitle="По выручке"
      action={<CardLink to={ROUTES.trainers}>Все</CardLink>}
    >
      {isPending ? (
        <div className="flex flex-col gap-2 px-5 py-3">
          <Skeleton className="h-[52px] w-full rounded-xl" />
          <Skeleton className="h-[52px] w-full rounded-xl" />
          <Skeleton className="h-[52px] w-full rounded-xl" />
        </div>
      ) : sorted.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Нет данных о тренерах"
          message="За выбранный период данные о тренерах отсутствуют."
        />
      ) : (
        <div className="@container pb-1">
          {sorted.map((trainer, i) => (
            <TrainerRowItem
              key={trainer.trainerId}
              trainer={trainer}
              first={i === 0}
              maxRevenue={maxRevenue}
            />
          ))}
        </div>
      )}
    </DashboardCard>
  );
}
