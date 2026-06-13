import { Link, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { FileText } from '@/components/icons';
import { Initials } from '@/components/ui/initials';
import type { Client } from '@/features/clients/types';
import { PlanBar, RowActions } from './parts';
import { STATUS_STRIPE, URGENCY_CARD } from './status-styles';

export function ClientCard({ client: c, variant }: { client: Client; variant: 'list' | 'grid' }) {
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (
      (e.target as HTMLElement).closest('a,button,input,label,[data-slot="dropdown-menu-trigger"]')
    )
      return;
    navigate(ROUTES.client(c.id));
  };

  return (
    <div
      onClick={handleClick}
      className={cn(
        'relative flex cursor-pointer flex-col gap-2 transition-colors',
        variant === 'list'
          ? 'border-b-[0.5px] border-border px-4 py-3 pl-[18px] last:border-b-0 active:bg-surface-2'
          : 'overflow-hidden rounded-lg border-[0.5px] border-border bg-surface p-4 pl-[18px] shadow-1 hover:border-border-strong',
      )}
    >
      <span
        className={cn(
          'absolute left-0 w-[3px] rounded-r-[3px]',
          variant === 'list' ? 'inset-y-3' : 'inset-y-0',
          STATUS_STRIPE[c.status],
        )}
      />

      <div className="flex items-center gap-3">
        <Initials initials={c.initials} color={c.color} className="size-10 text-sm" />
        <div className="min-w-0 flex-1">
          <Link
            to={ROUTES.client(c.id)}
            className="flex items-center gap-1.5 text-[14.5px] font-[650] leading-[1.2] tracking-[-0.2px]"
          >
            <span className="truncate">{c.name}</span>
            {c.hasNote && (
              <FileText className="size-3 shrink-0 text-fg-subtle/70" aria-label="Есть заметка" />
            )}
          </Link>
          <div className="mt-0.5 truncate text-xs tabular-nums text-fg-subtle">
            {c.phone} · {c.tenure}
          </div>
        </div>
        <RowActions clientId={c.id} className="-mr-1 shrink-0" />
      </div>

      {c.plan ? (
        <div className="ml-[52px] grid grid-cols-[auto_1fr_auto] items-center gap-2.5">
          <span
            className={cn(
              'whitespace-nowrap text-xs font-semibold tracking-[-0.1px]',
              c.plan.muted ? 'text-fg-subtle' : 'text-fg',
            )}
          >
            {c.plan.name}
          </span>
          <PlanBar pct={c.plan.fillPct} tone={c.plan.tone} className="h-[3px] min-w-0" />
          <span className="whitespace-nowrap text-[11px] tabular-nums text-fg-subtle">
            {c.plan.daysLabel}
          </span>
        </div>
      ) : (
        <div className="ml-[52px] text-xs text-fg-subtle">{c.planNote}</div>
      )}

      {c.expiry && (
        <div
          className={cn(
            'ml-[52px] inline-flex items-center gap-[7px] text-xs font-semibold tabular-nums',
            URGENCY_CARD[c.expiry.urgency],
          )}
        >
          <span className="size-[5px] shrink-0 rounded-full bg-current opacity-75" />
          {c.expiry.top}
          <span className="font-medium text-fg-subtle">{c.expiry.sub}</span>
        </div>
      )}
    </div>
  );
}
