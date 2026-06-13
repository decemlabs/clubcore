import { Fragment } from 'react';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import type { ScheduleSession, SessionState, SessionType } from '@/features/dashboard/types';
import { CardLink, DashboardCard, Initials } from './shared';

const ACCENT_BAR: Record<SessionState, string> = {
  done: 'bg-transparent',
  live: 'bg-primary',
  planned: 'bg-border-strong',
  group: 'bg-warning',
};

const CHIP_STYLES: Record<SessionType, string> = {
  pt: 'bg-primary-soft text-primary-deep dark:text-primary',
  gr: 'bg-warning-soft text-[#a36a16] dark:text-[#e9a23b]',
};

const CHIP_LABEL: Record<SessionType, string> = { pt: 'ПТ', gr: 'ГР' };

const STATE_TEXT: Record<SessionState, string> = {
  done: 'text-fg-subtle',
  live: 'font-semibold text-primary-deep dark:text-primary',
  planned: 'text-fg-muted',
  group: 'text-fg-muted',
};

const STATE_DOT: Record<SessionState, string> = {
  done: 'bg-border-strong',
  live: 'animate-pulse bg-primary-deep shadow-[0_0_0_3px_color-mix(in_oklab,var(--primary)_28%,transparent)] dark:bg-primary',
  planned: 'border-[1.5px] border-border-strong bg-transparent',
  group: 'bg-warning',
};

function ScheduleRow({ session, showBorder }: { session: ScheduleSession; showBorder: boolean }) {
  const done = session.state === 'done';
  return (
    <div
      className={cn(
        'relative grid grid-cols-[52px_28px_1fr_auto] items-center gap-3.5 px-5 py-[11px] sm:grid-cols-[56px_28px_1fr_auto]',
        showBorder && 'border-t-[0.5px] border-border',
        session.state === 'live' && 'bg-[color-mix(in_oklab,var(--primary-soft)_55%,transparent)]',
      )}
    >
      <span
        className={cn(
          'absolute bottom-2.5 left-2 top-2.5 w-[3px] rounded-r-sm',
          ACCENT_BAR[session.state],
        )}
      />

      <div className="leading-[1.05] tabular-nums tracking-[-0.3px]">
        <div className={cn('text-[15px] font-[650]', done ? 'text-fg-muted' : 'text-fg')}>
          {session.time}
        </div>
        <div className="mt-[3px] text-[10.5px] font-medium text-fg-subtle">{session.duration}</div>
      </div>

      <Initials initials={session.initials} color={session.color} />

      <div className="min-w-0">
        <div
          className={cn(
            'flex min-w-0 items-center gap-[7px] text-[13.5px] font-semibold tracking-[-0.1px]',
            done && 'text-fg-muted',
          )}
        >
          <span
            className={cn(
              'inline-flex h-[17px] shrink-0 items-center rounded px-1.5 text-[9.5px] font-bold uppercase tracking-[0.5px] tabular-nums',
              CHIP_STYLES[session.type],
            )}
          >
            {CHIP_LABEL[session.type]}
          </span>
          <span className="truncate">{session.who}</span>
        </div>
        <div className="mt-0.5 truncate text-xs text-fg-muted">
          <b className="font-semibold text-fg">{session.whatBold}</b>
          {session.whatRest}
        </div>
      </div>

      <span
        className={cn(
          'inline-flex items-center gap-1.5 whitespace-nowrap text-[11.5px] font-medium tabular-nums',
          STATE_TEXT[session.state],
        )}
      >
        <span className={cn('size-1.5 shrink-0 rounded-full', STATE_DOT[session.state])} />
        {session.stateLabel}
      </span>
    </div>
  );
}

export function ScheduleToday({
  sessions,
  nowLabel,
  total,
  done,
  live,
  planned,
}: {
  sessions: ScheduleSession[];
  nowLabel: string;
  total: number;
  done: number;
  live: number;
  planned: number;
}) {
  const firstLiveIndex = sessions.findIndex((s) => s.state === 'live');

  return (
    <DashboardCard
      title="Расписание тренировок · сегодня"
      subtitle={`${total} сессий · ${done} завершено · ${live} идут · ${planned} запланировано`}
      action={<CardLink to={ROUTES.schedule}>Все</CardLink>}
    >
      <div className="py-1">
        {sessions.map((session, i) => {
          const dividerHere = i === firstLiveIndex && firstLiveIndex > 0;
          // Граница сверху — только если предыдущий элемент тоже строка (разделитель её прерывает).
          const showBorder = i > 0 && i !== firstLiveIndex;
          return (
            <Fragment key={session.id}>
              {dividerHere ? (
                <div className="relative flex items-center gap-3 px-5 py-1.5" aria-hidden>
                  <span className="inline-flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.6px] tabular-nums text-primary-deep dark:text-primary">
                    <span className="size-1.5 rounded-full bg-primary shadow-[0_0_0_3px_color-mix(in_oklab,var(--primary)_30%,transparent)]" />
                    {nowLabel}
                  </span>
                  <span className="h-px flex-1 bg-[linear-gradient(90deg,var(--primary),transparent)] opacity-55" />
                </div>
              ) : null}
              <ScheduleRow session={session} showBorder={showBorder} />
            </Fragment>
          );
        })}
      </div>
    </DashboardCard>
  );
}
