/**
 * VisitAnomalyCard — daily visit area chart with >sigma anomaly markers (Phase 115-03 / ANL-02).
 *
 * Renders an AreaChart of daily visit counts. Anomaly days are rendered as colored dots
 * via a custom Area dot renderer: spikes = var(--chart-1), drops = var(--chart-4).
 * Summary line + legend chips when anomalies are present.
 * Data source: GET /api/v1/reports/anomaly via useVisitAnomaly (owner-gated).
 */
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart';
import { Card, CardHeader } from '@/components/layout/Card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { TrendingUp } from '@/components/icons';
import type { VisitAnomalyData, VisitAnomalyPoint } from '@/features/reports/schemas';

interface VisitAnomalyCardProps {
  data: VisitAnomalyData | undefined;
  isPending: boolean;
  isError?: boolean;
}

const ANOMALY_CHART_CONFIG: ChartConfig = {
  count: { label: 'Визитов', color: 'var(--primary-deep)' },
};

/** Small colored circle + label legend chip. */
function LegendChip({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] text-fg-muted">
      <span
        aria-hidden
        className="inline-block size-[10px] rounded-full"
        style={{ background: color }}
      />
      {label}
    </span>
  );
}

interface TooltipPayload {
  payload?: VisitAnomalyPoint;
}

function AnomalyTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  return (
    <div className="rounded-lg bg-fg px-2.5 py-1.5 text-[11.5px] font-semibold leading-tight text-bg shadow-lg dark:border-[0.5px] dark:border-border-strong dark:bg-surface dark:text-fg">
      <div className="text-[10px] font-medium uppercase tracking-[0.3px] opacity-70">
        {point.label}
      </div>
      <div className="tabular-nums">{point.count} визитов</div>
      {point.isAnomaly && point.direction ? (
        <div
          className="mt-0.5 text-[10px]"
          style={{ color: point.direction === 'spike' ? 'var(--chart-1)' : 'var(--chart-4)' }}
        >
          {point.direction === 'spike' ? 'Пик' : 'Провал'}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Custom dot renderer for the Area chart.
 * Renders colored dots only on anomaly points; baseline points get no visible dot.
 */
function AnomalyDot(props: {
  cx?: number;
  cy?: number;
  payload?: VisitAnomalyPoint;
}) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload?.isAnomaly) return <g />;
  const fill = payload.direction === 'spike' ? 'var(--chart-1)' : 'var(--chart-4)';
  return <circle cx={cx} cy={cy} r={5} fill={fill} stroke="var(--surface)" strokeWidth={1.5} />;
}

export function VisitAnomalyCard({ data, isPending, isError }: VisitAnomalyCardProps) {
  const subtitle = data
    ? `Дни, отклоняющиеся более чем на ${data.sigmaThreshold}σ от скользящей средней (${data.windowDays} дней)`
    : 'Анализ аномалий посещаемости';

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader title="Аномалии посещаемости" subtitle={subtitle} />

      <div className="px-5 pb-4 pt-0">
        {isPending ? (
          <Skeleton className="h-[180px] w-full rounded-xl" />
        ) : isError ? (
          <EmptyState
            icon={TrendingUp}
            title="Не удалось загрузить данные"
            message="Обновите страницу или повторите попытку позже."
            className="py-8"
          />
        ) : !data || data.points.length === 0 ? (
          <EmptyState
            icon={TrendingUp}
            title="Недостаточно данных"
            message="Для расчёта аномалий нужны данные минимум за 2 недели."
            className="py-8"
          />
        ) : (
          <>
            {/* Anomaly summary line */}
            <p className="mb-3 text-[12.5px] text-fg-muted">
              Найдено аномалий:{' '}
              <b className="font-semibold text-fg">{data.anomalyCount}</b>
            </p>

            {data.anomalyCount === 0 ? (
              <p className="mb-2 text-[11.5px] text-fg-subtle">
                Аномалий не обнаружено за указанный период
              </p>
            ) : null}

            <AnomalyChartBody data={data} />

            {data.anomalyCount > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <LegendChip color="var(--chart-1)" label="Пик" />
                <LegendChip color="var(--chart-4)" label="Провал" />
              </div>
            ) : null}
          </>
        )}
      </div>
    </Card>
  );
}

/** Chart body extracted to avoid inline complexity. */
function AnomalyChartBody({ data }: { data: VisitAnomalyData }) {
  const { points } = data;
  const ticksEvery = Math.max(Math.floor(points.length / 6), 1);

  return (
    <ChartContainer config={ANOMALY_CHART_CONFIG} className="h-[180px] w-full">
      <AreaChart data={points} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="anomalyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--primary-deep)" stopOpacity={0.28} />
            <stop offset="100%" stopColor="var(--primary-deep)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.55} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10 }}
          interval={ticksEvery - 1}
          tickMargin={8}
        />
        <YAxis hide />
        <Area
          type="monotone"
          dataKey="count"
          stroke="var(--primary-deep)"
          strokeWidth={1.5}
          fill="url(#anomalyGrad)"
          isAnimationActive={false}
          dot={<AnomalyDot />}
          activeDot={{
            r: 4,
            fill: 'var(--surface)',
            stroke: 'var(--primary-deep)',
            strokeWidth: 2,
          }}
        />
        <ChartTooltip content={<AnomalyTooltip />} />
      </AreaChart>
    </ChartContainer>
  );
}
