import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { CardLink } from '@/components/layout/Card';
import { Initials } from '@/components/ui/initials';
import type { TrainerDetail, TrainerSession } from '@/features/trainers/detail';
import { Panel, PanelBody, PanelHead } from './shared';

const BAR: Record<TrainerSession['bar'], string> = {
  accent: 'bg-primary',
  group: 'bg-warning',
  done: 'bg-border-strong',
};

const TAG: Record<TrainerSession['tagTone'], string> = {
  now: 'bg-primary-soft text-primary-deep dark:text-primary',
  done: 'bg-surface-3 text-fg-subtle',
  default: 'bg-surface-3 text-fg-muted',
};

export function OverviewTab({ trainer: t }: { trainer: TrainerDetail }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr] lg:items-start">
      <Panel>
        <PanelHead
          title={`Расписание · ${t.scheduleDateLabel}`}
          action={<CardLink to={ROUTES.schedule}>Всё расписание</CardLink>}
        />
        <PanelBody>
          {t.schedule.map((s, i) => (
            <div
              key={i}
              className="flex items-center gap-3 border-b-[0.5px] border-border py-3 last:border-b-0"
            >
              <div className="w-12 shrink-0 text-[13px] font-bold tabular-nums tracking-[-0.3px]">
                {s.time}
              </div>
              <div className={cn('w-[3px] self-stretch rounded-full', BAR[s.bar])} />
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-semibold tracking-[-0.1px]">{s.title}</div>
                <div className="mt-px text-[11.5px] text-fg-subtle">{s.sub}</div>
              </div>
              <span
                className={cn(
                  'shrink-0 rounded-full px-[9px] py-[3px] text-[11px] font-semibold',
                  TAG[s.tagTone],
                )}
              >
                {s.tag}
              </span>
            </div>
          ))}
        </PanelBody>
      </Panel>

      <div className="flex flex-col gap-4">
        <Panel>
          <PanelHead
            title="Постоянные клиенты"
            action={
              <span className="rounded-full bg-surface-3 px-[7px] py-px text-[11px] font-bold tabular-nums text-fg-muted">
                {t.regularsCount}
              </span>
            }
          />
          <PanelBody>
            {t.regulars.map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 border-b-[0.5px] border-border py-[9px] last:border-b-0"
              >
                <Initials initials={c.initials} color={c.color} className="size-8 text-[11.5px]" />
                <div className="min-w-0 flex-1">
                  <div className={cn('text-[13px] font-semibold', c.muted && 'text-fg-muted')}>
                    {c.name}
                  </div>
                  {c.sub ? <div className="text-[11px] text-fg-subtle">{c.sub}</div> : null}
                </div>
              </div>
            ))}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHead title="Условия и ставки" />
          <PanelBody>
            {t.terms.map((r, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 border-b-[0.5px] border-dashed border-border py-2.5 text-[13px] last:border-b-0"
              >
                <span className="w-[130px] shrink-0 text-fg-subtle">{r.k}</span>
                <span className="font-semibold">{r.v}</span>
              </div>
            ))}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
