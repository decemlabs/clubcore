import { useMemo, useState } from 'react';
import { useMockSettingsData } from '@/features/settings/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { SettingsContext } from '@/components/settings/context';
import { ScrollspyNav as SettingsNav } from '@/components/settings/ScrollspyNav';
import { SaveBar } from '@/components/settings/SaveBar';
import { SettingsPageHead } from './components/SettingsPageHead';
import {
  BookingSection,
  BranchSection,
  HoursSection,
  PaymentsSection,
  ProfileSection,
  SecuritySection,
} from './components/SectionsTop';
import {
  AppSection,
  BillingSection,
  DangerSection,
  IntegrationsSection,
  NotificationsSection,
  TeamSection,
} from './components/SectionsBottom';

export function SettingsPage() {
  // ProfileSection and SecuritySection are self-fetching (Plan 104-04).
  // Other sections still use mock data until their wiring plans run.
  const { data, isPending, isError, refetch } = useMockSettingsData();
  const [dirty, setDirty] = useState<Set<string>>(() => new Set());

  const ctx = useMemo(
    () => ({
      markDirty: (id: string) => setDirty((prev) => (prev.has(id) ? prev : new Set(prev).add(id))),
    }),
    [],
  );

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  return (
    <SettingsContext.Provider value={ctx}>
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
        <SettingsPageHead summary={data.summary} />

        <div className="grid items-start gap-7 lg:grid-cols-[224px_minmax(0,1fr)]">
          <SettingsNav groups={data.nav} />
          <div className="flex min-w-0 flex-col gap-[18px]">
            {/* ProfileSection and SecuritySection self-fetch (Plan 104-04) */}
            <ProfileSection />
            <SecuritySection />
            <BranchSection />
            <HoursSection />
            <BookingSection />
            <PaymentsSection />
            <NotificationsSection data={data} />
            <AppSection data={data} />
            {/* TeamSection will be wired in Plan 104-05 */}
            <TeamSection data={data} />
            <IntegrationsSection data={data} />
            <BillingSection data={data} />
            <DangerSection />
          </div>
        </div>

        <SaveBar
          count={dirty.size}
          onSave={() => setDirty(new Set())}
          onCancel={() => setDirty(new Set())}
        />
      </div>
    </SettingsContext.Provider>
  );
}
