/**
 * Client detail page (Phase 101 CLI-01, CLI-02).
 *
 * Profile head wired to real GET /api/v1/clients/{client_id} via useClient() (101-01).
 * Memberships tab wired to real useMembershipsByClient (101-03).
 * Activity (visits) tab wired to real useClientVisits (101-04).
 * Trainings (PT-packages) tab wired to real usePtPackagesByClient (101-04).
 * Payments tab wired to real usePaymentsByClient (101-04).
 *
 * Chat and Notes tabs remain on mock data — no backend endpoints in Phase 101 scope.
 *
 * Per-tab error isolation (UI-SPEC §Surface 1): each tab owns its own loading/empty/error
 * state — a single-tab query error does NOT bubble to the full-page error state.
 */
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useClient } from '@/features/clients/api';
import { useMembershipsByClient } from '@/features/memberships/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { ProfileHeroReal } from './components/ProfileHeroReal';
import { ProfileTabs, type ProfileTabKey } from './components/ProfileTabs';
import { ActivityTab } from './components/ActivityTab';
import { TrainingsTab } from './components/TrainingsTab';
import { PaymentsTab } from './components/PaymentsTab';
import { ChatTab } from './components/ChatTab';
import { NotesTab } from './components/NotesTab';
import { Card } from './components/shared';
import { formatDateRu, formatKopecks } from '@/lib/format';
import { cn } from '@/lib/cn';
import { useModals } from '@/components/modals/modals-context';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { CreditCard, MoreHorizontal } from '@/components/icons';
import type { MembershipData } from '@/features/memberships/schemas';
import type { SubscriptionScreen } from '@/components/modals/modals-context';

// Mock data for chat/notes — wired to real backend in a future plan
import { clientDetail } from '@/mocks/client-detail';

// ---------------------------------------------------------------------------
// Memberships sub-section (inside the page, shown above tabs or inline)
// ---------------------------------------------------------------------------

const MEMBERSHIP_STATUS_LABEL: Record<string, string> = {
  active: 'Активный',
  frozen: 'Заморожен',
  expired: 'Истёк',
  cancelled: 'Отменён',
};

const MEMBERSHIP_STATUS_TONE: Record<string, string> = {
  active: 'bg-primary-soft text-primary-deep dark:text-primary',
  frozen: 'bg-info-soft text-info',
  expired: 'bg-surface-3 text-fg-muted',
  cancelled: 'bg-danger-soft text-danger',
};

/** Build the SubscriptionModal membership payload from the flat wire shape. */
function toMembershipPayload(m: MembershipData) {
  return {
    id: m.id,
    clientId: m.clientId,
    priceKopecksSnapshot: m.priceKopecksSnapshot,
    paidAt: m.paidAt,
    planNameSnapshot: m.planNameSnapshot,
    endDate: m.endDate,
    freezeDaysRemaining: m.freezeDaysRemaining,
    currentFreezePeriod: m.currentFreezePeriod,
  };
}

function MembershipsSection({ clientId, clientName }: { clientId: string; clientName: string }) {
  const { data, isPending, isError, refetch } = useMembershipsByClient(clientId);
  const { open } = useModals();
  const role = useSession().data?.role ?? 'reception';

  if (isPending) {
    return (
      <Card className="px-4 py-4 sm:px-5">
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <PageError onRetry={() => void refetch()} />
      </Card>
    );
  }

  const items = data?.items ?? [];
  const active = items.filter((m) => m.status === 'active' || m.status === 'frozen');

  if (active.length === 0) {
    return (
      <Card>
        <EmptyState
          className="py-10"
          title="Нет активных абонементов"
          message="Активные абонементы клиента появятся здесь."
          action={
            <Button
              className="mt-1 gap-2 rounded-full"
              onClick={() =>
                open('subscription', { subscription: { screen: 'create', clientId, clientName } })
              }
            >
              <CreditCard className="size-[15px]" />
              Оформить абонемент
            </Button>
          }
        />
      </Card>
    );
  }

  return (
    <Card>
      {active.map((m) => {
        const tone = MEMBERSHIP_STATUS_TONE[m.status] ?? 'bg-surface-3 text-fg-muted';
        const statusLabel = MEMBERSHIP_STATUS_LABEL[m.status] ?? m.status;
        const isFrozen = m.status === 'frozen';
        const openScreen = (screen: SubscriptionScreen) =>
          open('subscription', {
            subscription: {
              screen,
              clientId,
              clientName,
              membershipId: m.id,
              membership: toMembershipPayload(m),
            },
          });
        return (
          <div
            key={m.id}
            className="grid grid-cols-[1fr_auto] items-center gap-3 border-t-[0.5px] border-border px-4 py-3 first:border-t-0 sm:px-5"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">
                  {m.planNameSnapshot}
                </div>
                <span
                  className={cn(
                    'shrink-0 rounded-full px-[7px] py-px text-[11px] font-semibold',
                    tone,
                  )}
                >
                  {statusLabel}
                </span>
              </div>
              <div className="mt-0.5 text-[11.5px] tabular-nums text-fg-subtle">
                до {formatDateRu(m.endDate, 'd MMMM yyyy')}
                {' · '}
                {formatKopecks(m.priceKopecksSnapshot)}
              </div>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="Действия с абонементом"
                  className="size-[34px] shrink-0 rounded-full"
                >
                  <MoreHorizontal className="size-[15px]" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[190px]">
                <DropdownMenuItem onSelect={() => openScreen('renew')}>Продлить</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => openScreen(isFrozen ? 'unfreeze' : 'freeze')}>
                  {isFrozen ? 'Разморозить' : 'Заморозить'}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => openScreen('refund')}>
                  Оформить возврат
                </DropdownMenuItem>
                {can(role, 'cancel', 'memberships') ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-danger focus:text-danger"
                      onSelect={() => openScreen('cancel')}
                    >
                      Отменить абонемент
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      })}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ClientPage() {
  const { clientId = '' } = useParams<{ clientId: string }>();
  const { data: client, isPending, isError, refetch } = useClient(clientId);
  const [tab, setTab] = useState<ProfileTabKey>('activity');

  if (isPending) return <PageLoading />;
  if (isError || !client) return <PageError onRetry={() => void refetch()} />;

  const clientName = [client.lastName, client.firstName, client.middleName]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      {/* Profile head — real data from GET /api/v1/clients/{client_id} (101-01) */}
      <ProfileHeroReal client={client} />

      {/* Active memberships section — real data from useMembershipsByClient (101-03) */}
      <MembershipsSection clientId={clientId} clientName={clientName} />

      {/* Tabs — activity/trainings/payments on real data (101-04) */}
      <section className="@container flex min-w-0 flex-col gap-4">
        {/* Counts are omitted — tabs load their own data with per-tab states */}
        <ProfileTabs value={tab} onChange={setTab} />

        {/* Activity tab: real visits (useClientVisits) */}
        {tab === 'activity' && <ActivityTab clientId={clientId} />}

        {/* Trainings tab: real PT-packages (usePtPackagesByClient) */}
        {tab === 'trainings' && <TrainingsTab clientId={clientId} />}

        {/* Payments tab: real payments read-only (usePaymentsByClient) — T-101-13-READONLY */}
        {tab === 'payments' && <PaymentsTab clientId={clientId} />}

        {/* Chat/Notes: still on mock data — no backend endpoint in Phase 101 scope */}
        {tab === 'chat' && <ChatTab data={clientDetail.chat} />}
        {tab === 'notes' && <NotesTab notes={clientDetail.notes} />}
      </section>
    </div>
  );
}
