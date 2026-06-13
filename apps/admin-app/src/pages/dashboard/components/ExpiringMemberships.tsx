import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { MessageSquare, RefreshCw } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';
import type { ExpiringMembership, ExpiryUrgency } from '@/features/dashboard/types';
import { CardLink, DashboardCard, Initials, ListButton } from './shared';

const URGENCY_TOP: Record<ExpiryUrgency, string> = {
  urgent: 'text-danger',
  soon: 'text-warning',
  normal: 'text-fg',
};

function ExpiringRow({ item, first }: { item: ExpiringMembership; first: boolean }) {
  const { open } = useModals();
  return (
    <div
      className={cn(
        'grid grid-cols-[32px_minmax(0,1fr)_auto_auto] items-center gap-3 px-5 py-3',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      <Initials initials={item.initials} color={item.color} className="size-8 text-[11px]" />

      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">{item.name}</div>
        <div className="mt-px truncate text-xs text-fg-muted">{item.meta}</div>
      </div>

      <div className="text-right text-xs font-semibold tabular-nums">
        <div className={URGENCY_TOP[item.urgency]}>{item.whenTop}</div>
        <div className="text-[11px] font-medium text-fg-subtle">{item.whenDate}</div>
      </div>

      <div className="flex items-center gap-1.5">
        <ListButton
          onClick={() => open('extend', { extend: { clientName: item.name } })}
          className="@max-[420px]:w-[30px] @max-[420px]:gap-0 @max-[420px]:px-0"
        >
          <RefreshCw className="size-[13px]" strokeWidth={2.2} />
          <span className="@max-[420px]:hidden">Продлить</span>
        </ListButton>
        <ListButton
          variant="icon"
          aria-label="Написать клиенту"
          title="Написать клиенту"
          className="@max-[320px]:hidden"
        >
          <MessageSquare className="size-[14px]" strokeWidth={2} />
        </ListButton>
      </div>
    </div>
  );
}

export function ExpiringMemberships({
  items,
  daysAhead,
  totalClients,
}: {
  items: ExpiringMembership[];
  daysAhead: number;
  totalClients: number;
}) {
  return (
    <DashboardCard
      title="Истекающие абонементы"
      subtitle={`Ближайшие ${daysAhead} дней · ${totalClients} клиентов`}
      action={<CardLink to={ROUTES.clients}>Все</CardLink>}
    >
      <div className="@container pb-2">
        {items.map((item, i) => (
          <ExpiringRow key={item.id} item={item} first={i === 0} />
        ))}
      </div>
    </DashboardCard>
  );
}
