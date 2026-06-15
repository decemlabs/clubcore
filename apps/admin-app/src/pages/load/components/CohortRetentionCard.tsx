/**
 * CohortRetentionCard — cohort × month retention grid for the Load page (Phase 115-03 / ANL-02).
 *
 * Displays retention % as a color-scaled grid: rows = cohort start month, columns = M0..M{maxOffset}.
 * Data source: GET /api/v1/reports/cohort via useCohortReport (owner-gated).
 * Wire shape: nested { cohorts: [{ cohortMonth, label, months: [{ offset, retentionPct }] }], maxOffset }
 * per 115-01-SUMMARY.md (authoritative — PATTERNS.md flat rows[] shape is stale).
 */
import { Card, CardHeader } from '@/components/layout/Card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { BarChart3 } from '@/components/icons';
import type { CohortRetentionData } from '@/features/reports/schemas';

interface CohortRetentionCardProps {
  data: CohortRetentionData | undefined;
  isPending: boolean;
  isError?: boolean;
}

/**
 * Color scale function per UI-SPEC Surface 2.
 * null → transparent (no data)
 * <30  → var(--surface-2)
 * 30-69 → color-mix primary 30%
 * >=70 → color-mix primary 75%
 */
function retentionBg(pct: number | null): string {
  if (pct === null) return 'transparent';
  if (pct < 30) return 'var(--surface-2)';
  if (pct < 70) return 'color-mix(in srgb, var(--primary) 30%, transparent)';
  return 'color-mix(in srgb, var(--primary) 75%, transparent)';
}

export function CohortRetentionCard({ data, isPending, isError }: CohortRetentionCardProps) {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Удержание клиентов по когортам"
        subtitle="% клиентов с активным абонементом, совершивших визит в месяц"
      />

      <div className="overflow-x-auto px-5 pb-4 pt-0">
        {isPending ? (
          <Skeleton className="h-[240px] w-full rounded-xl" />
        ) : isError ? (
          <EmptyState
            icon={BarChart3}
            title="Не удалось загрузить данные"
            message="Обновите страницу или повторите попытку позже."
            className="py-8"
          />
        ) : !data || data.cohorts.length === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="Нет данных по когортам"
            message="Когортный анализ появится после накопления данных за несколько месяцев."
            className="py-8"
          />
        ) : (
          <>
            <table
              role="grid"
              aria-label="Таблица удержания"
              className="w-full border-collapse"
            >
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="pb-2 pr-3 text-left text-[11.5px] font-medium text-fg-muted"
                  >
                    Когорта
                  </th>
                  {Array.from({ length: data.maxOffset + 1 }, (_, i) => (
                    <th
                      key={i}
                      scope="col"
                      className="pb-2 text-center text-[11px] font-medium text-fg-muted"
                    >
                      M{i}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.cohorts.map((cohort) => (
                  <tr key={cohort.cohortMonth}>
                    <th
                      scope="row"
                      className="whitespace-nowrap pr-3 text-left text-[11.5px] font-medium text-fg-muted"
                    >
                      {cohort.label}
                    </th>
                    {Array.from({ length: data.maxOffset + 1 }, (_, offset) => {
                      const m = cohort.months.find((mo) => mo.offset === offset);
                      const pct = m?.retentionPct ?? null;
                      return (
                        <td
                          key={offset}
                          className="size-9 rounded-md text-center text-[11px] tabular-nums"
                          style={{ background: retentionBg(pct) }}
                        >
                          <span
                            className={
                              pct !== null && pct >= 70 ? 'font-semibold' : ''
                            }
                          >
                            {pct !== null ? `${pct}%` : '—'}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Legend footer */}
            <footer className="mt-3 flex items-center gap-3 text-[11px] text-fg-muted">
              <div
                className="h-2 w-20 rounded"
                style={{
                  background:
                    'linear-gradient(to right, var(--surface-2), color-mix(in srgb, var(--primary) 30%, transparent), color-mix(in srgb, var(--primary) 75%, transparent))',
                }}
              />
              <span>0%</span>
              <span>…</span>
              <span>100%</span>
            </footer>
          </>
        )}
      </div>
    </Card>
  );
}
