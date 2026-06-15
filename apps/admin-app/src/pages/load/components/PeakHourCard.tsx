/**
 * PeakHourCard — peak-hour KPI tile for the Load page (Phase 114 / ANL-01).
 *
 * Displays the hour of day with the most visits as a KpiTile inside a Card.
 * Falls back to "—" with no unit when derivePeakHour returns null (all-zero).
 *
 * Data: derived client-side from VisitsReportHourlyBucket[] via derivePeakHour.
 * No network calls, no hooks.
 */
import { Card, CardHeader } from '@/components/layout/Card'
import { KpiTile } from '@/components/ui/KpiTile'
import { Clock } from '@/components/icons'
import type { VisitsReportHourlyBucket } from '@/features/reports/schemas'
import { derivePeakHour } from './derive'

export function PeakHourCard({ hourly }: { hourly: VisitsReportHourlyBucket[] }) {
  const peak = derivePeakHour(hourly)

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Пиковый час"
        subtitle="Час дня с наибольшим числом визитов"
      />
      <div className="px-5 pb-4 pt-0">
        <KpiTile
          icon={Clock}
          label="Пиковое время"
          value={peak ? `${peak.hour}:00–${peak.hour + 1}:00` : '—'}
          unit={peak ? `${peak.count} визитов` : undefined}
        />
      </div>
    </Card>
  )
}
