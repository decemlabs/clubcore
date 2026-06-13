import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { Star } from '@/components/icons';
import { formatRub } from '@/lib/format';
import type { ColumnDef } from '@/components/data/DataTable';
import type { Trainer } from '@/features/trainers/types';
import { StatusPill, TrainerActions } from './parts';
import { LOAD_FILL } from './status';

/** Классы скрытия колонок по ширине контейнера таблицы (container queries). */
const HIDE = {
  rating: '@max-[1080px]:hidden',
  experience: '@max-[920px]:hidden',
  rate: '@max-[860px]:hidden',
  trainings: '@max-[760px]:hidden',
  clients: '@max-[680px]:hidden',
  load: '@max-[1180px]:hidden',
} as const;

/** Колонки таблицы тренеров (режим «Таблица») для общего DataTable. */
export const trainerColumns: ColumnDef<Trainer>[] = [
  {
    id: 'name',
    header: 'Тренер',
    sortKey: 'name',
    cell: (t) => (
      <div className="flex min-w-0 items-center gap-3">
        <Initials
          initials={t.initials}
          color={t.avatarGradient}
          className="size-9 rounded-xl text-[12px]"
        />
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold tracking-[-0.1px] text-fg">
            {t.name}
          </div>
          <div className="truncate text-[11.5px] text-fg-subtle">{t.specialization}</div>
        </div>
      </div>
    ),
  },
  {
    id: 'rating',
    header: 'Рейтинг',
    sortKey: 'rating',
    headClassName: HIDE.rating,
    cellClassName: cn(HIDE.rating, 'whitespace-nowrap'),
    cell: (t) => (
      <span className="inline-flex items-center gap-1 text-[13px] font-semibold tabular-nums">
        <Star className="size-3 fill-warning text-warning" />
        {t.rating.toFixed(1)}
        <span className="font-normal text-fg-subtle">· {t.reviews}</span>
      </span>
    ),
  },
  {
    id: 'experience',
    header: 'Стаж',
    headClassName: HIDE.experience,
    cellClassName: cn(HIDE.experience, 'whitespace-nowrap text-[12.5px]'),
    cell: (t) => t.experience,
  },
  {
    id: 'rate',
    header: 'Ставка',
    headClassName: HIDE.rate,
    cellClassName: cn(HIDE.rate, 'whitespace-nowrap text-[12.5px] tabular-nums'),
    cell: (t) => t.rateLabel,
  },
  {
    id: 'status',
    header: 'Статус',
    cell: (t) => <StatusPill status={t.status} label={t.statusLabel} />,
  },
  {
    id: 'trainings',
    header: 'Тренировок',
    sortKey: 'trainings',
    headClassName: HIDE.trainings,
    cellClassName: cn(HIDE.trainings, 'tabular-nums'),
    cell: (t) => <b className="font-semibold tabular-nums text-fg">{t.trainings}</b>,
  },
  {
    id: 'clients',
    header: 'Клиенты',
    headClassName: HIDE.clients,
    cellClassName: cn(HIDE.clients, 'tabular-nums'),
    cell: (t) => <span className="tabular-nums">{t.clients}</span>,
  },
  {
    id: 'revenue',
    header: 'Выручка',
    sortKey: 'revenue',
    cellClassName: 'whitespace-nowrap',
    cell: (t) => <b className="font-semibold tabular-nums text-fg">{formatRub(t.revenue)}</b>,
  },
  {
    id: 'load',
    header: 'Загрузка',
    sortKey: 'load',
    headClassName: HIDE.load,
    cellClassName: cn(HIDE.load, 'min-w-[124px]'),
    cell: (t) => (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-surface-3">
          <div
            className={cn('h-full rounded-full', LOAD_FILL[t.loadTone])}
            style={{ width: `${t.loadPct}%` }}
          />
        </div>
        <span className="whitespace-nowrap text-[11.5px] tabular-nums text-fg-subtle">
          {t.loadNote ?? `${t.loadUsed}/${t.loadTotal}`}
        </span>
      </div>
    ),
  },
  {
    id: 'actions',
    header: '',
    headClassName: 'w-[50px]',
    cellClassName: 'w-[50px] text-right',
    cell: (t) => <TrainerActions trainerId={t.id} className="ml-auto" />,
  },
];
