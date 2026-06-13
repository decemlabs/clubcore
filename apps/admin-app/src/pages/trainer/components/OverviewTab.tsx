/**
 * OverviewTab — Phase 102-02 TRN-01.
 *
 * Today-schedule: booking-dependency-safe. The bookings query
 * useBookingsByTrainer(trainerId, todayRange) is defined in Plan 102-03
 * (features/bookings/api.ts). Plan 102-02 is wave 1 alongside Plan 102-03 which
 * is wave 2 — bookings hooks do NOT exist yet.
 *
 * Wire the trainer-static parts now.
 * For the today-session list: show EmptyState «Нет записей на сегодня» as interim
 * state until Plan 102-03 lands the hook.
 *
 * // TODO(102-03): wire useBookingsByTrainer(trainerId, todayRange) — see Plan 03
 *
 * Regulars section: no clean endpoint in Phase 102 — stays on mock.
 * // TODO Phase 104: wire regulars to real endpoint when available
 */
import { ROUTES } from '@/app/routes'
import { Initials } from '@/components/ui/initials'
import { CardLink } from '@/components/layout/Card'
import { trainerDetail } from '@/mocks/trainer-detail'
import { Panel, PanelBody, PanelHead } from './shared'

interface Props {
  // trainerId will be used in Plan 102-03 for useBookingsByTrainer
  // TODO(102-03): wire useBookingsByTrainer(trainerId, todayRange) — see Plan 03
  trainerId: string
}

export function OverviewTab({ trainerId }: Props) {
  // trainerId is accepted now for Plan 102-03 to consume; not yet used.
  void trainerId

  // Regulars section stays on mock — no dedicated endpoint in Phase 102.
  // TODO Phase 104: wire regulars to real endpoint when available.
  const t = trainerDetail

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr] lg:items-start">
      {/* Today schedule — interim state (bookings hook ships in Plan 102-03) */}
      {/* TODO(102-03): wire useBookingsByTrainer(trainerId, todayRange) — see Plan 03 */}
      <Panel>
        <PanelHead
          title="Расписание · сегодня"
          action={<CardLink to={ROUTES.schedule}>Всё расписание</CardLink>}
        />
        <PanelBody>
          {/* Skeleton rows placeholder so Plan 102-03 only swaps the data source */}
          {/* TODO(102-03): replace EmptyState with real booking rows from useBookingsByTrainer */}
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
            <span className="text-[13.5px] font-semibold text-fg-muted">Нет записей на сегодня</span>
            <span className="text-[11.5px] text-fg-subtle">
              Расписание появится здесь после подключения брони (Plan 102-03)
            </span>
          </div>
        </PanelBody>
      </Panel>

      <div className="flex flex-col gap-4">
        {/* Regulars — stays on mock, TODO Phase 104 */}
        <Panel>
          <PanelHead
            title="Постоянные клиенты"
            action={
              <span className="rounded-full bg-surface-3 px-[7px] py-px text-[11px] font-bold tabular-nums text-fg-muted">
                {t.regularsCount}
              </span>
            }
          />
          <PanelBody>
            {/* TODO Phase 104: wire regulars to real endpoint when available */}
            {t.regulars.map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 border-b-[0.5px] border-border py-[9px] last:border-b-0"
              >
                <Initials initials={c.initials} color={c.color} className="size-8 text-[11.5px]" />
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold">{c.name}</div>
                  {c.sub ? <div className="text-[11px] text-fg-subtle">{c.sub}</div> : null}
                </div>
              </div>
            ))}
          </PanelBody>
        </Panel>
      </div>
    </div>
  )
}
