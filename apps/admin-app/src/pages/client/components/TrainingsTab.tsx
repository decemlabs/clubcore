/**
 * Trainings tab — real PT-packages via usePtPackagesByClient (Phase 101-04).
 *
 * Per-tab inline error/empty states (UI-SPEC §Surface 1):
 *   - loading: Skeleton rows
 *   - error: inline <PageError onRetry/> (NOT full-page)
 *   - empty: inline EmptyState (no icon tile) «Нет тренировок» / «Персональные тренировки появятся здесь.»
 *   - data: real PtPackageData rows (planSnapshot.name, sessionsRemaining, status)
 *
 * Read-only display of PT-package data. No lifecycle actions here —
 * those live in SubscriptionModal (101-03 scope).
 */
import { usePtPackagesByClient } from '@/features/pt-packages/api';
import { formatKopecks, formatDateRu } from '@/lib/format';
import { PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';
import { Card, CardHead } from './shared';

const STATUS_LABEL: Record<string, string> = {
  active: 'Активный',
  exhausted: 'Исчерпан',
  expired: 'Истёк',
  cancelled: 'Отменён',
};

const STATUS_TONE: Record<string, string> = {
  active: 'bg-primary-soft text-primary-deep dark:text-primary',
  exhausted: 'bg-surface-3 text-fg-muted',
  expired: 'bg-surface-3 text-fg-muted',
  cancelled: 'bg-danger-soft text-danger',
};

function PtPackageRow({
  item,
}: {
  item: {
    id: string;
    planSnapshot: { name: string; priceKopecks: number };
    sessionsRemaining: number;
    sessionsTotal: number;
    amountKopecks: number;
    status: string;
    createdAt: string;
  };
}) {
  const tone = STATUS_TONE[item.status] ?? 'bg-surface-3 text-fg-muted';
  const statusLabel = STATUS_LABEL[item.status] ?? item.status;

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-t-[0.5px] border-border px-4 py-3 first:border-t-0 sm:px-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">
            {item.planSnapshot.name}
          </div>
          <span
            className={cn('shrink-0 rounded-full px-[7px] py-px text-[11px] font-semibold', tone)}
          >
            {statusLabel}
          </span>
        </div>
        <div className="mt-0.5 text-[11.5px] tabular-nums text-fg-subtle">
          Занятий: {item.sessionsRemaining} из {item.sessionsTotal}
          {' · '}
          {formatDateRu(item.createdAt, 'd MMM yyyy')}
        </div>
      </div>
      <div className="shrink-0 text-sm font-bold tabular-nums tracking-[-0.2px]">
        {formatKopecks(item.amountKopecks)}
      </div>
    </div>
  );
}

export function TrainingsTab({ clientId }: { clientId: string }) {
  const { data, isPending, isError, refetch } = usePtPackagesByClient(clientId);

  if (isPending) {
    return (
      <Card className="px-4 py-4 sm:px-5">
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <PageError onRetry={() => void refetch()} />
      </Card>
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <Card>
        <EmptyState
          className="py-12"
          title="Нет тренировок"
          message="Персональные тренировки появятся здесь."
        />
      </Card>
    );
  }

  return (
    <Card>
      <CardHead title="Пакеты тренировок" sub={`${items.length} пакет(ов)`} />
      <div className="border-t-[0.5px] border-border">
        {items.map((item) => (
          <PtPackageRow key={item.id} item={item} />
        ))}
      </div>
    </Card>
  );
}
