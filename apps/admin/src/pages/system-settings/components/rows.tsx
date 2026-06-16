import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Monitor, Smartphone } from '@/components/icons';
import type { SysSession, SysIntegration, ApiKey, Webhook } from '@/features/system-settings/types';

/* ---------- Pills ---------- */

type TagTone = 'on' | 'warn' | 'off';
const TAG: Record<TagTone, string> = {
  on: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
  off: 'bg-surface-3 text-fg-muted',
};

/** Маленькая капс-пилюля статуса (.pill из мокапа). */
export function TagPill({ tone = 'off', children }: { tone?: TagTone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.3px]',
        TAG[tone],
      )}
    >
      {children}
    </span>
  );
}

/** Акцентная стат-пилюля (баланс SMS и т.п.). */
export function StatPill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-primary-soft px-[11px] py-[5px] text-[12.5px] font-semibold text-primary-deep dark:text-primary">
      {children}
    </span>
  );
}

/* ---------- List rows (divider-separated within a card body) ---------- */

const LIST_ROW = 'flex items-center gap-3 border-b-[0.5px] border-border py-3 last:border-b-0';

/** Ряд «метка/подпись слева — управление справа» (info-trow). */
export function InfoRow({
  title,
  sub,
  aside,
}: {
  title: ReactNode;
  sub?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className={LIST_ROW}>
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold">{title}</div>
        {sub != null ? <div className="mt-0.5 text-[11.5px] text-fg-subtle">{sub}</div> : null}
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}

export function SessionRow({ session, action }: { session: SysSession; action?: ReactNode }) {
  const Icon = session.device === 'phone' ? Smartphone : Monitor;
  return (
    <div className={LIST_ROW}>
      <span className="grid size-[34px] shrink-0 place-items-center rounded-[9px] bg-surface-3 text-fg-muted">
        <Icon className="size-[17px]" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[13.5px] font-semibold">
          <span className="truncate">{session.name}</span>
          {session.current ? <TagPill tone="on">текущая</TagPill> : null}
        </div>
        <div className="mt-0.5 truncate text-[11.5px] text-fg-subtle">{session.meta}</div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function IntegrationRow({ item, action }: { item: SysIntegration; action: ReactNode }) {
  return (
    <div className={LIST_ROW}>
      <span
        style={{ background: item.logoBg, color: item.logoFg ?? '#fff' }}
        className="grid size-[38px] shrink-0 place-items-center rounded-[10px] text-[13px] font-extrabold"
      >
        {item.logo}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] font-semibold">{item.name}</div>
        <div className="mt-0.5 truncate text-[11.5px] text-fg-subtle">{item.desc}</div>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  );
}

/** Бордерная карточка-строка с моно-ключом (API-ключи, webhooks). */
export function MonoRow({
  mono,
  sub,
  pill,
  actions,
}: {
  mono: ApiKey['key'] | Webhook['url'];
  sub: string;
  pill: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center gap-2.5 rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-3 last:mb-0">
      <div className="min-w-0 flex-1">
        <div className="truncate font-mono text-[12.5px] text-fg">{mono}</div>
        <div className="mt-0.5 truncate text-[11px] text-fg-subtle">{sub}</div>
      </div>
      {pill}
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
