import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { Initials } from '@/components/ui/initials';
import { useModals } from '@/components/modals/modals-context';
import { Calendar, ChevronRight, MessageSquare, Plus, Star } from '@/components/icons';
import type { Trainer } from '@/features/trainers/types';
import { StatusPill } from './parts';
import { LOAD_FILL, STATUS_DOT, TREND_TEXT, pluralReviews } from './status';

const FOOT_BTN =
  'inline-flex h-[30px] items-center gap-1.5 rounded-lg px-2.5 text-[12px] font-semibold text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function Stat({
  label,
  value,
  foot,
  footClass,
}: {
  label: string;
  value: ReactNode;
  foot?: ReactNode;
  footClass?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.3px] text-fg-subtle">
        {label}
      </div>
      <div className="mt-1 text-[17px] font-bold leading-none tabular-nums">{value}</div>
      {foot ? <div className={cn('mt-1 truncate text-[11px]', footClass)}>{foot}</div> : null}
    </div>
  );
}

/** Карточка тренера в ростере: аватар+статус, метрики, недельная загрузка, действия. */
export function RosterCard({ trainer: t }: { trainer: Trainer }) {
  const navigate = useNavigate();
  const compact = `${Math.round(t.revenue / 1000)}К`;

  return (
    <article
      onClick={() => navigate(ROUTES.trainer(t.id))}
      className="group/card relative flex cursor-pointer flex-col overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1 transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-2"
    >
      <div className="flex items-start gap-3 p-[18px] pb-3.5">
        <div className="relative shrink-0">
          <Initials
            initials={t.initials}
            color={t.avatarGradient}
            className="size-[52px] rounded-2xl text-[18px]"
          />
          <span
            className={cn(
              'absolute -bottom-0.5 -right-0.5 size-3.5 rounded-full ring-[2.5px] ring-surface',
              STATUS_DOT[t.status],
            )}
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="truncate text-[15.5px] font-bold leading-tight tracking-[-0.2px]">
            {t.name}
          </div>
          <div className="mt-0.5 truncate text-[12.5px] text-fg-muted">{t.specialization}</div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[11.5px] text-fg-subtle">
            <span className="inline-flex items-center gap-1">
              <Star className="size-3 shrink-0 fill-warning text-warning" />
              <b className="font-semibold tabular-nums text-fg">{t.rating.toFixed(1)}</b>
            </span>
            <span>
              · {t.reviews} {pluralReviews(t.reviews)} · {t.experience} · {t.rateLabel}
            </span>
          </div>
        </div>

        <StatusPill status={t.status} label={t.statusLabel} className="shrink-0" />
      </div>

      <div className="grid grid-cols-3 gap-2 px-[18px] pb-4">
        <Stat
          label="Тренировок"
          value={t.trainings}
          foot={t.trainingsDelta?.label}
          footClass={t.trainingsDelta ? TREND_TEXT[t.trainingsDelta.trend] : undefined}
        />
        <Stat label="Клиенты" value={t.clients} foot={t.clientsNote} footClass="text-fg-subtle" />
        <Stat
          label="Выручка"
          value={
            <>
              {compact}
              <small className="text-[11px] font-semibold text-fg-subtle"> ₽</small>
            </>
          }
          foot={t.shareLabel}
          footClass="text-fg-subtle"
        />
      </div>

      <div className="border-t-[0.5px] border-border bg-surface-2 px-[18px] py-3">
        <div className="flex items-center justify-between text-[11.5px]">
          <span className="text-fg-muted">Загрузка недели</span>
          <b className="font-semibold tabular-nums">
            {t.loadNote ?? `${t.loadUsed} из ${t.loadTotal} ч`}
          </b>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3">
          <div
            className={cn('h-full rounded-full', LOAD_FILL[t.loadTone])}
            style={{ width: `${t.loadPct}%` }}
          />
        </div>
      </div>

      <div className="mt-auto flex items-center gap-1 border-t-[0.5px] border-border px-3 py-2">
        <button
          type="button"
          className={FOOT_BTN}
          onClick={(e) => {
            e.stopPropagation();
            navigate(ROUTES.schedule);
          }}
        >
          <Calendar className="size-3.5" />
          Расписание
        </button>
        <button
          type="button"
          className={FOOT_BTN}
          onClick={(e) => {
            e.stopPropagation();
            navigate(ROUTES.messages);
          }}
        >
          <MessageSquare className="size-3.5" />
          Написать
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            navigate(ROUTES.trainer(t.id));
          }}
          className="ml-auto inline-flex h-[30px] items-center gap-1 rounded-lg px-3 text-[12px] font-semibold text-fg transition-colors hover:bg-fg hover:text-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-primary dark:hover:text-[#06120c]"
        >
          Профиль
          <ChevronRight className="size-3.5" strokeWidth={2.4} />
        </button>
      </div>
    </article>
  );
}

/** Пунктирная карточка-приглашение «Добавить тренера» в конце ростера. */
export function HireCard() {
  const { open } = useModals();
  return (
    <button
      type="button"
      onClick={() => open('trainer-form')}
      className="group flex min-h-[210px] flex-col items-center justify-center gap-3 rounded-lg border-[1.5px] border-dashed border-border p-6 text-center transition-colors hover:border-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="grid size-11 place-items-center rounded-2xl bg-surface-3 text-fg-muted transition-colors group-hover:bg-fg group-hover:text-bg dark:group-hover:bg-primary dark:group-hover:text-[#06120c]">
        <Plus className="size-5" />
      </span>
      <div>
        <div className="text-[14.5px] font-bold">Добавить тренера</div>
        <div className="mt-1 text-[12px] leading-snug text-fg-muted">
          Открыть вакансию или пригласить из базы · 3 кандидата в работе
        </div>
      </div>
    </button>
  );
}
