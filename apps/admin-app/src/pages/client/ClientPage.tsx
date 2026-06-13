import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useClient } from '@/features/clients/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { ProfileHero } from './components/ProfileHero';
import { ProfileSide } from './components/ProfileSide';
import { StatStrip } from './components/StatStrip';
import { ProfileTabs, type ProfileTabKey } from './components/ProfileTabs';
import { ActivityTab } from './components/ActivityTab';
import { TrainingsTab } from './components/TrainingsTab';
import { PaymentsTab } from './components/PaymentsTab';
import { ChatTab } from './components/ChatTab';
import { NotesTab } from './components/NotesTab';

export function ClientPage() {
  const { clientId = '' } = useParams<{ clientId: string }>();
  const { data: client, isPending, isError, refetch } = useClient(clientId);
  const [tab, setTab] = useState<ProfileTabKey>('activity');

  if (isPending) return <PageLoading />;
  if (isError || !client) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <ProfileHero client={client} />

      <div className="flex flex-col gap-4 xl:grid xl:grid-cols-[340px_minmax(0,1fr)] xl:items-start">
        <ProfileSide client={client} />

        <section className="@container flex min-w-0 flex-col gap-4">
          <StatStrip stats={client.stats} />
          <ProfileTabs counts={client.counts} value={tab} onChange={setTab} />

          {tab === 'activity' && <ActivityTab activity={client.activity} />}
          {tab === 'trainings' && <TrainingsTab data={client.trainings} />}
          {tab === 'payments' && <PaymentsTab data={client.payments} />}
          {tab === 'chat' && <ChatTab data={client.chat} />}
          {tab === 'notes' && <NotesTab notes={client.notes} />}
        </section>
      </div>
    </div>
  );
}
