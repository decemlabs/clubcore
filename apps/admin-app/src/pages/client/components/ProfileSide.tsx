import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { useModals } from '@/components/modals/modals-context';
import { Check } from '@/components/icons';
import type { ClientDetail } from '@/features/clients/detail';
import { Chip, MiniButton, SideCard, SideCardLink } from './shared';

function SubscriptionCard({ client }: { client: ClientDetail }) {
  const s = client.subscription;
  const { open } = useModals();
  return (
    <SideCard
      title="Текущий абонемент"
      action={
        <SideCardLink onClick={() => open('subscription', { subscription: { screen: 'edit' } })}>
          Изменить
        </SideCardLink>
      }
    >
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div className="text-[17px] font-bold tracking-[-0.3px]">{s.name}</div>
        <div className="text-[18px] font-bold tabular-nums tracking-[-0.4px]">{s.amount}</div>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className={cn('h-full rounded-full', s.urgent ? 'bg-danger' : 'bg-primary')}
          style={{ width: `${s.fillPct}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[11.5px] tabular-nums text-fg-muted">
        <span>
          <b className="font-semibold text-fg">
            {s.daysUsed} / {s.daysTotal}
          </b>{' '}
          дней
        </span>
        <span className={s.urgent ? 'text-danger' : undefined}>
          истекает <b className="font-semibold">{s.expiresLabel}</b>
        </span>
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-1.5 border-t-[0.5px] border-border pt-3">
        {s.features.map((f) => (
          <div key={f} className="flex items-center gap-1.5 text-xs text-fg-muted">
            <Check
              className="size-[13px] shrink-0 text-primary-deep dark:text-primary"
              strokeWidth={2.4}
            />
            {f}
          </div>
        ))}
      </div>

      <div className="mt-3.5 flex gap-2">
        <MiniButton onClick={() => open('subscription', { subscription: { screen: 'renew' } })}>
          Продлить
        </MiniButton>
        <MiniButton onClick={() => open('subscription', { subscription: { screen: 'freeze' } })}>
          Заморозить
        </MiniButton>
        <MiniButton
          danger
          onClick={() => open('subscription', { subscription: { screen: 'cancel' } })}
        >
          Отменить
        </MiniButton>
      </div>
    </SideCard>
  );
}

function TrainerCard({ client }: { client: ClientDetail }) {
  const t = client.trainer;
  return (
    <SideCard title="Персональный тренер" action={<SideCardLink>Сменить</SideCardLink>}>
      <div className="mb-3.5 flex items-center gap-3">
        <Initials initials={t.initials} color={t.color} className="size-10 text-sm" />
        <div className="min-w-0">
          <div className="text-sm font-bold tracking-[-0.2px]">{t.name}</div>
          <div className="mt-0.5 text-[11.5px] text-fg-subtle">{t.spec}</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 border-t-[0.5px] border-border pt-3">
        {t.stats.map((st) => (
          <div key={st.label} className="flex flex-col gap-px">
            <span className="text-[15px] font-bold tabular-nums tracking-[-0.2px]">{st.value}</span>
            <span className="text-[10.5px] font-medium text-fg-subtle">{st.label}</span>
          </div>
        ))}
      </div>
    </SideCard>
  );
}

function ContactCard({ client }: { client: ClientDetail }) {
  return (
    <SideCard title="Контакт и источник">
      <div className="grid grid-cols-[90px_1fr] gap-x-3 gap-y-[7px] text-[12.5px]">
        {client.contact.map((row) => (
          <div key={row.k} className="contents">
            <div className="text-fg-subtle">{row.k}</div>
            <div className="text-fg">
              {row.v}
              {row.muted ? <span className="text-fg-subtle"> {row.muted}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </SideCard>
  );
}

function GoalsCard({ client }: { client: ClientDetail }) {
  return (
    <SideCard title="Цели и здоровье" action={<SideCardLink>Править</SideCardLink>}>
      {client.goals.map((g, i) => (
        <div key={g.label} className={cn(i > 0 && 'mt-3.5 border-t-[0.5px] border-border pt-3.5')}>
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.4px] text-fg-subtle">
            {g.label}
          </div>
          {g.body ? <div className="text-[13px] leading-relaxed text-fg">{g.body}</div> : null}
          {g.chips ? (
            <div className="flex flex-wrap gap-1.5">
              {g.chips.map((c) => (
                <Chip key={c.label} warn={c.warn}>
                  {c.label}
                </Chip>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </SideCard>
  );
}

export function ProfileSide({ client }: { client: ClientDetail }) {
  return (
    <aside className="flex flex-col gap-4">
      <SubscriptionCard client={client} />
      <TrainerCard client={client} />
      <ContactCard client={client} />
      <GoalsCard client={client} />
    </aside>
  );
}
