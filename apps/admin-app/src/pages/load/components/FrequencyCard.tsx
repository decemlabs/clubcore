/**
 * FrequencyCard — daily-volume frequency histogram for the Load page (Phase 114 / ANL-01).
 *
 * Shows how many days in the selected period fell into each visit-count bucket
 * (0–4, 5–9, 10–14, 15–19, 20–24, 25+). Rendered as an AreaTrendChart over the
 * 6 fixed frequency buckets from deriveFrequency.
 *
 * Data: derived client-side from VisitsReportDailyBucket[] via deriveFrequency.
 * No network calls, no hooks.
 */
import { Card, CardHeader } from '@/components/layout/Card'
import { AreaTrendChart } from '@/components/charts/AreaTrendChart'
import type { VisitsReportDailyBucket } from '@/features/reports/schemas'
import { deriveFrequency } from './derive'

export function FrequencyCard({ daily }: { daily: VisitsReportDailyBucket[] }) {
  const buckets = deriveFrequency(daily)

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Распределение дневной посещаемости"
        subtitle="Сколько дней приходится на каждый диапазон визитов"
      />
      <div className="px-5 pb-4">
        <AreaTrendChart
          data={buckets.map((b) => ({ label: b.label, value: b.count }))}
          height={160}
        />
      </div>
    </Card>
  )
}
