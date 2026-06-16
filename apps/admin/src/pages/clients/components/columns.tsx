import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { FileText } from '@/components/icons';
import { Initials } from '@/components/ui/initials';
import type { ColumnDef } from '@/components/data/DataTable';
import type { Client } from '@/features/clients/types';
import { PlanBar, RowActions, StatusPill } from './parts';
import { URGENCY_TABLE } from './status-styles';

/** Классы скрытия колонок по ширине контейнера таблицы (container queries). */
const HIDE = {
  visits: '@max-[900px]:hidden',
  trainer: '@max-[780px]:hidden',
  expires: '@max-[680px]:hidden',
  last: '@max-[680px]:hidden',
} as const;

/** Колонки таблицы клиентов для общего DataTable. */
export const clientColumns: ColumnDef<Client>[] = [
  {
    id: 'name',
    header: 'Клиент',
    sortKey: 'name',
    cell: (c) => (
      <div className="flex min-w-0 items-center gap-[11px]">
        <Initials initials={c.initials} color={c.color} className="size-8 text-xs" />
        <div className="min-w-0">
          <Link
            to={ROUTES.client(c.id)}
            className="flex items-center gap-1.5 text-[13.5px] font-semibold leading-[1.25] tracking-[-0.1px] text-fg hover:underline"
          >
            <span className="truncate">{c.name}</span>
            {c.hasNote && (
              <FileText className="size-3 shrink-0 text-fg-subtle" aria-label="Есть заметка" />
            )}
          </Link>
          <div className="mt-px truncate text-[11.5px] tabular-nums text-fg-subtle">
            {c.phone} · {c.tenure}
          </div>
        </div>
      </div>
    ),
  },
  {
    id: 'status',
    header: 'Статус',
    cell: (c) => <StatusPill status={c.status} />,
  },
  {
    id: 'plan',
    header: 'Абонемент',
    cellClassName: 'min-w-0',
    cell: (c) =>
      c.plan ? (
        <div className="min-w-0">
          <div
            className={cn(
              'text-[13px] font-semibold tracking-[-0.1px]',
              c.plan.muted ? 'font-medium text-fg-subtle' : 'text-fg',
            )}
          >
            {c.plan.name}
          </div>
          <PlanBar pct={c.plan.fillPct} tone={c.plan.tone} className="mt-1.5 w-[110px]" />
          <div className="mt-[3px] text-[11px] tabular-nums text-fg-subtle">{c.plan.daysLabel}</div>
        </div>
      ) : (
        <span className="text-[12.5px] text-fg-subtle">{c.planNote}</span>
      ),
  },
  {
    id: 'expires',
    header: 'Истекает',
    sortKey: 'expires',
    headClassName: HIDE.expires,
    cellClassName: HIDE.expires,
    cell: (c) =>
      c.expiry ? (
        <div
          className={cn(
            'whitespace-nowrap text-[13px] font-semibold tabular-nums tracking-[-0.1px]',
            URGENCY_TABLE[c.expiry.urgency],
          )}
        >
          {c.expiry.top}
          <span className="block text-[11px] font-medium text-fg-subtle">{c.expiry.sub}</span>
        </div>
      ) : (
        <span className="text-[12.5px] text-fg-subtle">—</span>
      ),
  },
  {
    id: 'visits',
    header: <>Визитов&nbsp;/&nbsp;мес</>,
    sortKey: 'visits',
    headClassName: HIDE.visits,
    cellClassName: cn(HIDE.visits, 'whitespace-nowrap'),
    cell: (c) => (
      <>
        {c.visits.strong ? (
          <b className="font-semibold tabular-nums text-fg">{c.visits.value}</b>
        ) : (
          <span className="tabular-nums text-fg-subtle">{c.visits.value}</span>
        )}
        {c.visits.total && (
          <span className="text-[12.5px] text-fg-subtle"> · {c.visits.total}</span>
        )}
      </>
    ),
  },
  {
    id: 'trainer',
    header: 'Тренер',
    headClassName: HIDE.trainer,
    cellClassName: HIDE.trainer,
    cell: (c) =>
      c.trainer ? (
        <div className="flex items-center gap-2">
          <Initials
            initials={c.trainer.initials}
            color={c.trainer.color}
            className="size-6 text-[10px]"
          />
          <span className="truncate text-[12.5px]">{c.trainer.name}</span>
        </div>
      ) : (
        <span className="text-[12.5px] text-fg-subtle">—</span>
      ),
  },
  {
    id: 'last',
    header: <>Последний&nbsp;визит</>,
    sortKey: 'last',
    headClassName: HIDE.last,
    cellClassName: cn(HIDE.last, 'whitespace-nowrap text-[12.5px]'),
    cell: (c) => (
      <>
        {c.lastVisit.top}
        <br />
        <span className="text-fg-subtle">{c.lastVisit.sub}</span>
      </>
    ),
  },
  {
    id: 'actions',
    header: '',
    headClassName: 'w-[50px]',
    cellClassName: 'w-[50px] text-right',
    cell: (c) => <RowActions clientId={c.id} className="ml-auto" />,
  },
];
