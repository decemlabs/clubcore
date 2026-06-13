/**
 * TrainerPage — Phase 102-02 TRN-01.
 *
 * Wired to real GET /api/v1/trainers/{id} via useTrainer().
 * TrainerHero: real fullName/specialization/photoUrl/isActive.
 * TrainerKpis: hidden (deferred — no aggregate endpoint in Phase 102).
 * OverviewTab today-schedule: interim EmptyState (bookings hook lands in Plan 102-03).
 * PayoutsTab: untouched — Plan 102-04 owns payroll wiring.
 * HistoryTab: stays on mock — no dedicated history endpoint in Phase 102.
 *              // TODO Phase 104: wire history to real endpoint
 */
import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { useTrainer } from '@/features/trainers/api'
import { useSession } from '@/features/auth/api'
import { PageLoading, PageError } from '@/components/feedback/PageState'
import { TrainerHero } from './components/TrainerHero'
import { OverviewTab } from './components/OverviewTab'
import { PayoutsTab } from './components/PayoutsTab'
import { HistoryTab } from './components/HistoryTab'
import { DetailTabs } from './components/shared'
import { trainerDetail } from '@/mocks/trainer-detail'

type TabKey = 'overview' | 'payouts' | 'history'

const TABS: { value: TabKey; label: string }[] = [
  { value: 'overview', label: 'Обзор' },
  { value: 'payouts', label: 'Выплаты' },
  { value: 'history', label: 'История' },
]

export function TrainerPage() {
  const { trainerId = '' } = useParams<{ trainerId: string }>()
  const { hash } = useLocation()
  const { data: trainer, isPending, isError, refetch } = useTrainer(trainerId)
  const sessionQuery = useSession()
  const role = sessionQuery.data?.role ?? 'reception'
  const [tab, setTab] = useState<TabKey>('overview')

  // Поддержка прямых ссылок на вкладки (#payouts / #history).
  useEffect(() => {
    const h = hash.replace('#', '')
    if (h === 'payouts' || h === 'history') setTab(h)
  }, [hash])

  if (isPending) return <PageLoading />
  if (isError || !trainer) return <PageError onRetry={() => void refetch()} />

  return (
    <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <TrainerHero trainer={trainer} role={role} />
      {/* TrainerKpis hidden — no aggregate KPI endpoint in Phase 102 (deferred Phase 104) */}
      <DetailTabs
        options={TABS}
        value={tab}
        onChange={setTab}
        ariaLabel="Разделы профиля тренера"
      />

      {tab === 'overview' && <OverviewTab trainerId={trainerId} />}
      {/* PayoutsTab: wired to real /api/v1/payroll/* (Plan 102-04) */}
      {tab === 'payouts' && <PayoutsTab trainerId={trainerId} />}
      {/* HistoryTab stays on mock — no dedicated history endpoint in Phase 102 */}
      {/* TODO Phase 104: wire history to real endpoint */}
      {tab === 'history' && <HistoryTab groups={trainerDetail.timeline} />}
    </div>
  )
}
