/**
 * AtRiskWidget — at-risk churn members list for the Load page (Phase 115-03 / ANL-02).
 *
 * Shows a count badge + up to 5 member rows with name, membership type, last-visit label.
 * "И ещё N клиентов →" overflow line when count > 5.
 * Zero-risk empty state when count === 0 ("Отток под контролем").
 * Data source: GET /api/v1/reports/at-risk via useAtRiskMembers (owner-gated).
 *
 * T-115-F3: rows are read-only divs — no client-detail navigation in this phase.
 */
import { Card, CardHeader } from '@/components/layout/Card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { CheckCircle2, TriangleAlert } from '@/components/icons';
import type { AtRiskData } from '@/features/reports/schemas';

interface AtRiskWidgetProps {
  data: AtRiskData | undefined;
  isPending: boolean;
  isError?: boolean;
}

export function AtRiskWidget({ data, isPending, isError }: AtRiskWidgetProps) {
  const count = data?.count ?? 0;
  const thresholdDays = data?.thresholdDays ?? 14;

  const countBadge =
    !isPending && !isError && data ? (
      <span
        className="inline-flex items-center rounded-full bg-warning-soft px-2 py-0.5 text-[11.5px] font-semibold tabular-nums text-warning-deep"
        aria-label={`Клиентов под риском: ${count}`}
      >
        {count}
      </span>
    ) : null;

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Клиенты под риском оттока"
        subtitle={`Активный абонемент, последний визит более ${thresholdDays} дней назад`}
        action={countBadge}
      />

      {isPending ? (
        <div className="flex flex-col gap-2 px-5 py-3">
          <Skeleton className="h-[52px] w-full rounded-xl" />
          <Skeleton className="h-[52px] w-full rounded-xl" />
          <Skeleton className="h-[52px] w-full rounded-xl" />
        </div>
      ) : isError ? (
        <EmptyState
          icon={TriangleAlert}
          title="Не удалось загрузить данные"
          message="Обновите страницу или повторите попытку позже."
          className="py-8"
        />
      ) : !data || count === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="Отток под контролем"
          message="Нет клиентов с активным абонементом без визитов более 14 дней."
          className="py-8"
        />
      ) : (
        <div>
          {data.items.slice(0, 5).map((item, i) => (
            <div
              key={item.clientId}
              className={
                'grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-2' +
                (i < data.items.slice(0, 5).length - 1 || count > 5
                  ? ' border-b-[0.5px] border-border'
                  : '')
              }
            >
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold">{item.name}</div>
                <div className="truncate text-[11.5px] text-fg-subtle">
                  {item.membershipType}
                </div>
              </div>
              <span className="shrink-0 whitespace-nowrap tabular-nums text-[11.5px] text-fg-muted">
                {item.lastVisitLabel}
              </span>
            </div>
          ))}

          {count > 5 ? (
            <div className="px-5 py-3 text-[12px] text-fg-muted">
              И ещё {count - 5} клиентов →
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}
