/**
 * Client detail page (Phase 101 CLI-01).
 *
 * Profile head wired to real GET /api/v1/clients/{id} via useClient().
 * Activity/trainings/payments/chat/notes tabs stay on mock data — those are
 * wired in Plan 04 (memberships + visits + payments client-detail reads).
 */
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useClient } from '@/features/clients/api'
import { PageLoading, PageError } from '@/components/feedback/PageState'
import { ProfileHeroReal } from './components/ProfileHeroReal'
import { ProfileTabs, type ProfileTabKey } from './components/ProfileTabs'
import { ActivityTab } from './components/ActivityTab'
import { TrainingsTab } from './components/TrainingsTab'
import { PaymentsTab } from './components/PaymentsTab'
import { ChatTab } from './components/ChatTab'
import { NotesTab } from './components/NotesTab'

// Mock data for tabs — wired to real backend in Plan 04
import { clientDetail } from '@/mocks/client-detail'

export function ClientPage() {
  const { clientId = '' } = useParams<{ clientId: string }>()
  const { data: client, isPending, isError, refetch } = useClient(clientId)
  const [tab, setTab] = useState<ProfileTabKey>('activity')

  if (isPending) return <PageLoading />
  if (isError || !client) return <PageError onRetry={() => void refetch()} />

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      {/* Profile head — real data from GET /api/v1/clients/{id} */}
      <ProfileHeroReal client={client} />

      {/* Tabs — still on mock data until Plan 04 wires them */}
      <section className="@container flex min-w-0 flex-col gap-4">
        <ProfileTabs counts={clientDetail.counts} value={tab} onChange={setTab} />

        {tab === 'activity' && <ActivityTab activity={clientDetail.activity} />}
        {tab === 'trainings' && <TrainingsTab data={clientDetail.trainings} />}
        {tab === 'payments' && <PaymentsTab data={clientDetail.payments} />}
        {tab === 'chat' && <ChatTab data={clientDetail.chat} />}
        {tab === 'notes' && <NotesTab notes={clientDetail.notes} />}
      </section>
    </div>
  )
}
