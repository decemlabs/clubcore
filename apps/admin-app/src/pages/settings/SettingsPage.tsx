import { useCallback, useMemo, useRef, useState } from 'react';
import { useBlocker, type BlockerFunction } from 'react-router-dom';
import { toast } from 'sonner';
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

// Per-section save/cancel handlers registered by wired sections on mount/change.
type SectionHandlers = {
  save: () => Promise<void>;
  cancel: () => void;
};

export function SettingsPage() {
  // ProfileSection and SecuritySection are self-fetching (Plan 104-04).
  // AppSection/BillingSection/IntegrationsSection still use mock data.
  const { data, isPending, isError, refetch } = useMockSettingsData();
  const [dirty, setDirty] = useState<Set<string>>(() => new Set());

  // Handler registry: wired sections register save/cancel on every state change.
  const handlersRef = useRef<Map<string, SectionHandlers>>(new Map());

  function registerSave(sectionId: string) {
    return (fn: () => Promise<void>) => {
      const existing = handlersRef.current.get(sectionId);
      handlersRef.current.set(sectionId, { save: fn, cancel: existing?.cancel ?? (() => {}) });
    };
  }

  function registerCancel(sectionId: string) {
    return (fn: () => void) => {
      const existing = handlersRef.current.get(sectionId);
      handlersRef.current.set(sectionId, { save: existing?.save ?? (() => Promise.resolve()), cancel: fn });
    };
  }

  const ctx = useMemo(
    () => ({
      markDirty: (id: string) => setDirty((prev) => (prev.has(id) ? prev : new Set(prev).add(id))),
    }),
    [],
  );

  // Navigate-away guard: prompt when there are unsaved changes
  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) => {
      return dirty.size > 0 && currentLocation.pathname !== nextLocation.pathname;
    },
    [dirty],
  );
  const blocker = useBlocker(shouldBlock);

  async function handleSave(): Promise<boolean> {
    const dirtyIds = Array.from(dirty);
    const results = await Promise.allSettled(
      dirtyIds.map((id) => handlersRef.current.get(id)?.save() ?? Promise.resolve()),
    );

    const failed: string[] = [];
    for (let i = 0; i < results.length; i++) {
      if (results[i]?.status === 'rejected') {
        const id = dirtyIds[i];
        if (id) failed.push(id);
      }
    }

    if (failed.length === 0) {
      toast.success('Настройки сохранены');
      setDirty(new Set());
      return true;
    } else {
      toast.error('Некоторые изменения не удалось сохранить. Проверьте ошибки в разделах.');
      return false;
    }
  }

  function handleCancel() {
    for (const id of dirty) {
      handlersRef.current.get(id)?.cancel();
    }
    setDirty(new Set());
  }

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
            {/* BranchSection, HoursSection, BookingSection wired (Plan 108-05) */}
            <BranchSection
              registerSave={registerSave('branch')}
              registerCancel={registerCancel('branch')}
            />
            <HoursSection
              registerSave={registerSave('hours')}
              registerCancel={registerCancel('hours')}
            />
            <BookingSection
              registerSave={registerSave('booking')}
              registerCancel={registerCancel('booking')}
            />
            <PaymentsSection />
            {/* NotificationsSection wired (Plan 108-05) */}
            <NotificationsSection
              registerSave={registerSave('notifications')}
              registerCancel={registerCancel('notifications')}
            />
            <AppSection data={data} />
            {/* TeamSection self-fetches (Plan 104-05) */}
            <TeamSection />
            <IntegrationsSection data={data} />
            <BillingSection data={data} />
            <DangerSection />
          </div>
        </div>

        <SaveBar
          count={dirty.size}
          onSave={() => void handleSave()}
          onCancel={handleCancel}
        />

        {/* Navigate-away guard dialog */}
        {blocker.state === 'blocked' ? (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="nav-guard-title"
            className="fixed inset-0 z-[120] flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center"
          >
            <div className="w-full max-w-sm rounded-t-2xl bg-surface p-6 shadow-xl sm:rounded-2xl">
              <div
                id="nav-guard-title"
                className="mb-1 text-[16px] font-bold"
              >
                Есть несохранённые изменения
              </div>
              <p className="mb-5 text-[13.5px] leading-relaxed text-fg-muted">
                Если уйти без сохранения, все изменения будут потеряны.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row-reverse">
                <button
                  type="button"
                  onClick={() => {
                    void handleSave().then((savedOk) => {
                      if (savedOk) {
                        blocker.proceed?.();
                      }
                      // else: stay on page — error toast already shown per section
                    });
                  }}
                  className="h-[42px] w-full rounded-xl bg-primary px-4 text-[14px] font-semibold text-[#06120c] transition-opacity hover:opacity-90 sm:w-auto"
                >
                  Сохранить и уйти
                </button>
                <button
                  type="button"
                  onClick={() => blocker.proceed?.()}
                  className="h-[42px] w-full rounded-xl bg-surface-2 px-4 text-[14px] font-semibold text-fg transition-colors hover:bg-surface-3 sm:w-auto"
                >
                  Уйти без сохранения
                </button>
                <button
                  type="button"
                  onClick={() => blocker.reset?.()}
                  className="h-[42px] w-full rounded-xl border-[0.5px] border-border bg-transparent px-4 text-[14px] font-semibold text-fg-muted hover:text-fg sm:w-auto"
                >
                  Остаться
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </SettingsContext.Provider>
  );
}
