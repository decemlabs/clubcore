import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { Switch } from '@/components/settings/controls';
import {
  Banknote,
  UserPlus,
  Clock,
  CreditCard,
  Calendar,
  BarChart3,
  Star,
  Moon,
} from '@/components/icons';
import {
  CHANNEL_LABEL,
  type Channel,
  type HistItem,
  type NotifItem,
  type NotifTone,
  type Recipient,
  type TplItem,
  type DeliveryStat,
} from '@/features/notifications/types';

/* ---------- Tabs ---------- */

export interface NTab {
  key: string;
  label: string;
  badge?: number;
}

export function NotifTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: NTab[];
  value: string;
  onChange: (k: string) => void;
}) {
  return (
    <div className="inline-flex max-w-full gap-1 self-start overflow-x-auto rounded-[11px] bg-surface-3 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={cn(
              'inline-flex h-[34px] shrink-0 items-center gap-2 rounded-lg px-[15px] text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg',
            )}
          >
            {t.label}
            {t.badge ? (
              <span className="grid h-4 min-w-4 place-items-center rounded-full bg-primary px-1.5 text-[10.5px] font-bold text-[#06120c]">
                {t.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Atoms ---------- */

const CH_CLS: Record<Channel, string> = {
  sms: 'bg-primary-soft text-primary-deep dark:text-primary',
  push: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300',
  email: 'bg-warning-soft text-warning-deep',
};

export function ChannelChip({ ch }: { ch: Channel }) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.3px]',
        CH_CLS[ch],
      )}
    >
      {CHANNEL_LABEL[ch]}
    </span>
  );
}

/** Текст с подсветкой {переменных}. */
export function Vars({ text }: { text: string }) {
  const parts = text.split(/(\{[^}]+\})/g);
  return (
    <>
      {parts.map((p, i) =>
        /^\{[^}]+\}$/.test(p) ? (
          <span key={i} className="font-semibold text-primary-deep dark:text-primary">
            {p}
          </span>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

export { Panel, PanelHead } from '@/components/layout/Panel';

export const GHOST_SM =
  'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[9px] border-[0.5px] border-border-strong bg-surface px-2.5 text-[12px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/* ---------- Feed ---------- */

const NOTIF_ICON: Record<string, LucideIcon> = {
  money: Banknote,
  'user-plus': UserPlus,
  clock: Clock,
  card: CreditCard,
  calendar: Calendar,
  chart: BarChart3,
  star: Star,
  backup: Moon,
};
const TONE_CLS: Record<NotifTone, string> = {
  success: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
  danger: 'bg-danger-soft text-danger',
  info: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300',
};

export function NotifRow({ n }: { n: NotifItem }) {
  const Icon = NOTIF_ICON[n.icon] ?? Banknote;
  return (
    <div
      className={cn(
        'relative flex gap-3 border-b-[0.5px] border-border px-[18px] py-3 last:border-b-0',
        n.unread &&
          'bg-[color-mix(in_oklab,var(--primary-soft)_30%,transparent)] dark:bg-primary/[0.06]',
      )}
    >
      {n.unread ? (
        <span className="absolute left-[7px] top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-primary" />
      ) : null}
      <span
        className={cn('grid size-9 shrink-0 place-items-center rounded-[10px]', TONE_CLS[n.tone])}
      >
        <Icon className="size-[17px]" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold leading-snug">
          {n.lead}
          <b className="font-bold">{n.bold}</b>
          {n.tail}
        </div>
        <div className="mt-0.5 text-[12px] text-fg-subtle">{n.body}</div>
      </div>
      <span className="shrink-0 whitespace-nowrap text-[11.5px] tabular-nums text-fg-subtle">
        {n.time}
      </span>
    </div>
  );
}

/* ---------- History table ---------- */

const HCOLS = 'md:grid-cols-[1.6fr_0.9fr_0.8fr_1.1fr_110px]';

export function HistoryTable({ rows, onRow }: { rows: HistItem[]; onRow: (r: HistItem) => void }) {
  return (
    <div>
      <div
        className={cn(
          'hidden border-b-[0.5px] border-border px-[18px] py-2.5 text-[10.5px] font-bold uppercase tracking-[0.5px] text-fg-subtle md:grid md:items-center md:gap-3.5',
          HCOLS,
        )}
      >
        <span>Рассылка</span>
        <span>Канал</span>
        <span>Аудитория</span>
        <span>Отправлено</span>
        <span className="md:text-right">Доставка</span>
      </div>
      {rows.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={() => onRow(r)}
          className={cn(
            'grid w-full cursor-pointer grid-cols-2 gap-x-3 gap-y-2 border-b-[0.5px] border-border px-[18px] py-3 text-left transition-colors last:border-b-0 hover:bg-surface-2 md:items-center md:gap-3.5',
            HCOLS,
          )}
        >
          <div className="col-span-2 min-w-0 md:col-span-1">
            <div className="truncate text-[13.5px] font-semibold">{r.name}</div>
            <div className="truncate text-[11.5px] text-fg-subtle">{r.sub}</div>
          </div>
          <div>
            <ChannelChip ch={r.ch} />
          </div>
          <div className="min-w-0">
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.4px] text-fg-subtle md:hidden">
              Аудитория:{' '}
            </span>
            <span className="text-[12.5px] text-fg-muted">{r.aud}</span>
          </div>
          <div className="min-w-0">
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.4px] text-fg-subtle md:hidden">
              Отправлено:{' '}
            </span>
            <span className="text-[12.5px] tabular-nums text-fg-muted">{r.sent}</span>
          </div>
          <div className="col-span-2 flex items-center gap-2 md:col-span-1">
            <span className="h-1.5 min-w-[40px] flex-1 overflow-hidden rounded-full bg-surface-3">
              <span
                className="block h-full rounded-full bg-primary"
                style={{ width: `${r.pct}%` }}
              />
            </span>
            <span className="text-[11.5px] font-[650] tabular-nums text-fg-muted">{r.pct}%</span>
          </div>
        </button>
      ))}
    </div>
  );
}

/* ---------- Template card ---------- */

export function TemplateCard({
  tpl,
  on,
  onToggle,
  onEdit,
}: {
  tpl: TplItem;
  on: boolean;
  onToggle: (v: boolean) => void;
  onEdit: () => void;
}) {
  return (
    <div className="flex flex-col rounded-[14px] border-[0.5px] border-border bg-surface-2 p-3.5">
      <div className="flex items-start gap-2.5">
        <ChannelChip ch={tpl.ch} />
        <div className="min-w-0">
          <div className="text-[13.5px] font-[650]">{tpl.name}</div>
          <div className="text-[11px] text-fg-subtle">{tpl.trigger}</div>
        </div>
      </div>
      <div className="my-3 flex-1 rounded-[10px] border-[0.5px] border-border bg-surface px-3 py-2.5 text-[12.5px] leading-relaxed text-fg-muted">
        <Vars text={tpl.body} />
      </div>
      <div className="flex items-center gap-2.5">
        <Switch checked={on} onChange={onToggle} ariaLabel={tpl.name} />
        <span className="text-[11.5px] font-semibold text-fg-subtle">
          {on ? 'Включён' : 'Выключен'}
        </span>
        <button type="button" onClick={onEdit} className={cn(GHOST_SM, 'ml-auto')}>
          Изменить
        </button>
      </div>
    </div>
  );
}

/* ---------- Delivery report ---------- */

const DOT: Record<DeliveryStat['key'], string> = {
  sent: 'bg-fg-subtle',
  deliv: 'bg-primary',
  read: 'bg-indigo-500',
  fail: 'bg-danger',
};

const REC_STATUS: Record<Recipient['status'], { cls: string; label: string }> = {
  read: { cls: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300', label: 'Прочитано' },
  deliv: { cls: 'bg-primary-soft text-primary-deep dark:text-primary', label: 'Доставлено' },
  fail: { cls: 'bg-danger-soft text-danger', label: 'Ошибка' },
};

export function DeliveryStats({ stats }: { stats: DeliveryStat[] }) {
  return (
    <div className="grid grid-cols-2 gap-px bg-border lg:grid-cols-4">
      {stats.map((s) => (
        <div key={s.key} className="bg-surface px-4 py-3.5">
          <div className="flex items-center gap-1.5 text-[11.5px] text-fg-muted">
            <span className={cn('size-[7px] rounded-full', DOT[s.key])} />
            {s.label}
          </div>
          <div className="mt-1 text-[22px] font-bold tabular-nums tracking-[-0.4px]">{s.value}</div>
          <div className="text-[11.5px] text-fg-subtle">{s.pct}</div>
        </div>
      ))}
    </div>
  );
}

export function RecipientRow({ r }: { r: Recipient }) {
  const s = REC_STATUS[r.status];
  return (
    <div className="flex items-center gap-3 border-b-[0.5px] border-border px-[18px] py-3 last:border-b-0">
      <Initials initials={r.initials} color={r.gradient} className="size-8 text-[11px]" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold">{r.name}</div>
        <div className="truncate text-[11px] text-fg-subtle">{r.phone}</div>
      </div>
      <span className={cn('shrink-0 rounded-full px-2.5 py-[3px] text-[11.5px] font-[650]', s.cls)}>
        {s.label}
      </span>
    </div>
  );
}
