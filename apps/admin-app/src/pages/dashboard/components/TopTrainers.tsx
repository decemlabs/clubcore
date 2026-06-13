import { Link } from 'react-router-dom';
import { ROUTES } from '@/app/routes';
import { ChevronRight } from '@/components/icons';
import type { TopTrainer } from '@/features/dashboard/types';
import { CardLink, DashboardCard, Initials } from './shared';

function TrainerRow({ trainer, first }: { trainer: TopTrainer; first: boolean }) {
  return (
    <Link
      to={ROUTES.trainers}
      className={`grid grid-cols-[32px_minmax(0,1fr)_auto_auto] items-center gap-3 px-5 py-[11px] transition-colors hover:bg-surface-2 ${
        first ? '' : 'border-t-[0.5px] border-border'
      }`}
    >
      <Initials initials={trainer.initials} color={trainer.color} className="size-8 text-[11px]" />

      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold">{trainer.name}</div>
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full bg-fg dark:bg-primary"
            style={{ width: `${trainer.barPct}%` }}
          />
        </div>
        <div className="mt-1 text-[11.5px] tabular-nums text-fg-subtle">{trainer.meta}</div>
      </div>

      <div className="text-right text-[13px] font-bold tracking-[-0.2px] tabular-nums">
        {trainer.amountLabel}
        <small className="block text-[10.5px] font-medium tracking-normal text-fg-subtle">
          {trainer.rankLabel}
        </small>
      </div>

      <span
        aria-hidden
        className="grid size-[30px] place-items-center rounded-lg bg-fg text-bg dark:bg-primary dark:text-[#06120c] @max-[400px]:hidden"
      >
        <ChevronRight className="size-[14px]" strokeWidth={2.4} />
      </span>
    </Link>
  );
}

export function TopTrainers({ trainers }: { trainers: TopTrainer[] }) {
  return (
    <DashboardCard
      title="Топ тренеры · апрель"
      subtitle="По выручке"
      action={<CardLink to={ROUTES.trainers}>Все</CardLink>}
    >
      <div className="@container pb-1">
        {trainers.map((trainer, i) => (
          <TrainerRow key={trainer.id} trainer={trainer} first={i === 0} />
        ))}
      </div>
    </DashboardCard>
  );
}
