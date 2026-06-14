import { ROUTES } from '@/app/routes';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { RefreshCw } from '@/components/icons';
import { cn } from '@/lib/cn';
import { formatDateRu, getInitials } from '@/lib/format';
import type { MembershipData } from '@/features/memberships/schemas';
import { useModals } from '@/components/modals/modals-context';
import { CardLink, DashboardCard, Initials, ListButton } from './shared';

interface ExpiringMembershipsProps {
  items: MembershipData[];
  isPending: boolean;
}

/** Simple hash to pick a deterministic avatar color. */
function colorForId(id: string): string {
  const COLORS = [
    '#4f46e5',
    '#0891b2',
    '#059669',
    '#d97706',
    '#dc2626',
    '#7c3aed',
    '#db2777',
    '#65a30d',
  ];
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return COLORS[h % COLORS.length] ?? '#4f46e5';
}

function daysUntil(dateStr: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const end = new Date(dateStr);
  end.setHours(0, 0, 0, 0);
  return Math.round((end.getTime() - today.getTime()) / 86_400_000);
}

function ExpiringRow({ item, first }: { item: MembershipData; first: boolean }) {
  const { open } = useModals();
  const days = daysUntil(item.endDate);
  const urgency = days <= 2 ? 'text-danger' : days <= 5 ? 'text-warning' : 'text-fg';
  const planName = item.planNameSnapshot;
  // CR-03: clientId is UUIDv4 — use planName for initials until clientFullName is on the wire.
  const initials = getInitials(planName);
  const color = colorForId(item.clientId);

  return (
    <div
      className={cn(
        'grid grid-cols-[32px_minmax(0,1fr)_auto_auto] items-center gap-3 px-5 py-3',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      <Initials initials={initials.slice(0, 2) || '?'} color={color} className="size-8 text-[11px]" />

      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">{planName}</div>
        <div className="mt-px truncate text-xs text-fg-muted">
          до {formatDateRu(item.endDate)}
        </div>
      </div>

      <div className="text-right text-xs font-semibold tabular-nums">
        <div className={urgency}>{days <= 0 ? 'Истёк' : `${days} дн.`}</div>
        <div className="text-[11px] font-medium text-fg-subtle">{item.status}</div>
      </div>

      <ListButton
        onClick={() =>
          open('extend', {
            // CR-03 fix: MembershipData has no clientFullName on the wire shape.
            // Use planSnapshot.name as the human-readable context label so the modal
            // never shows a raw UUID. When clientFullName is added to the payload,
            // change this to item.clientFullName.
            extend: { clientName: planName },
          })
        }
        className="@max-[420px]:w-[30px] @max-[420px]:gap-0 @max-[420px]:px-0"
      >
        <RefreshCw className="size-[13px]" strokeWidth={2.2} />
        <span className="@max-[420px]:hidden">Продлить</span>
      </ListButton>
    </div>
  );
}

export function ExpiringMemberships({ items, isPending }: ExpiringMembershipsProps) {
  return (
    <DashboardCard
      title="Истекающие абонементы"
      subtitle={isPending ? '—' : `Ближайшие 7 дней · ${items.length} абонементов`}
      action={<CardLink to={ROUTES.clients}>Все</CardLink>}
    >
      {isPending ? (
        <div className="flex flex-col gap-2 px-5 py-3">
          <Skeleton className="h-[52px] w-full rounded-xl" />
          <Skeleton className="h-[52px] w-full rounded-xl" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Нет истекающих абонементов"
          message="Все абонементы активны и не истекают в ближайшие 7 дней."
        />
      ) : (
        <div className="@container pb-2">
          {items.map((item, i) => (
            <ExpiringRow key={item.id} item={item} first={i === 0} />
          ))}
        </div>
      )}
    </DashboardCard>
  );
}
