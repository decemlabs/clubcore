/**
 * FrequencyCard — daily-volume frequency histogram for the Load page (Phase 114 / ANL-01).
 *
 * Shows how many days in the selected period fell into each visit-count bucket
 * (0–4, 5–9, 10–14, 15–19, 20–24, 25+). Rendered as a categorical BAR chart over
 * the 6 fixed frequency buckets from deriveFrequency — a frequency distribution
 * over discrete bins must not be interpolated (no smooth area between bins).
 *
 * Data: derived client-side from VisitsReportDailyBucket[] via deriveFrequency.
 * No network calls, no hooks.
 */
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { Card, CardHeader } from '@/components/layout/Card';
import { ChartContainer, type ChartConfig } from '@/components/ui/chart';
import type { VisitsReportDailyBucket } from '@/features/reports/schemas';
import { deriveFrequency } from './derive';

const CONFIG: ChartConfig = { value: { label: 'Дней', color: 'var(--primary-deep)' } };

export function FrequencyCard({ daily }: { daily: VisitsReportDailyBucket[] }) {
  const buckets = deriveFrequency(daily);
  const data = buckets.map((b) => ({ label: b.label, value: b.count }));

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Распределение дневной посещаемости"
        subtitle="Сколько дней приходится на каждый диапазон визитов"
      />
      <div className="px-5 pb-4">
        <ChartContainer config={CONFIG} className="aspect-auto w-full" style={{ height: 160 }}>
          <BarChart data={data} margin={{ top: 10, right: 12, left: 8, bottom: 0 }}>
            <CartesianGrid
              vertical={false}
              stroke="var(--border)"
              strokeDasharray="3 4"
              strokeOpacity={0.7}
            />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tick={{ fontSize: 10 }}
            />
            <YAxis hide domain={[0, 'auto']} />
            <Bar
              dataKey="value"
              fill="var(--primary-deep)"
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ChartContainer>
      </div>
    </Card>
  );
}
