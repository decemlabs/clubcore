/**
 * DurationPlaceholderCard — coming-soon placeholder for the duration widget (Phase 114 / ANL-01).
 *
 * The GET /api/v1/reports/visits aggregate has no duration field — this card renders
 * an honest coming-soon state with NO numeric or mock data. Muted surface only,
 * no accent, not an error state.
 *
 * No props. No network calls. No fabricated data.
 */
import { Card, CardHeader } from '@/components/layout/Card'
import { Clock } from '@/components/icons'

export function DurationPlaceholderCard() {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Время пребывания"
        subtitle="Аналитика по времени визитов"
      />
      <div className="px-5 pb-5 pt-2 flex flex-col items-center text-center gap-3">
        <Clock className="size-8 text-fg-subtle" strokeWidth={1.5} />
        <p className="text-[13px] text-fg-muted leading-snug max-w-[260px]">
          Эта аналитика появится после добавления данных о продолжительности визитов.
        </p>
        <span className="inline-flex items-center rounded-full bg-surface-2 border-[0.5px] border-border px-3 py-1 text-[11.5px] text-fg-muted font-medium">
          Скоро
        </span>
      </div>
    </Card>
  )
}
