import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Activity, CreditCard, FileText, MessageSquare, User } from '@/components/icons';
import type { ClientDetail } from '@/features/clients/detail';

export type ProfileTabKey = 'activity' | 'trainings' | 'payments' | 'chat' | 'notes';

interface TabDef {
  key: ProfileTabKey;
  label: string;
  icon: LucideIcon;
  count?: number;
  accent?: boolean;
}

export function ProfileTabs({
  counts,
  value,
  onChange,
}: {
  counts: ClientDetail['counts'];
  value: ProfileTabKey;
  onChange: (key: ProfileTabKey) => void;
}) {
  const tabs: TabDef[] = [
    { key: 'activity', label: 'Активность', icon: Activity },
    { key: 'trainings', label: 'Тренировки', icon: User, count: counts.trainings },
    { key: 'payments', label: 'Платежи', icon: CreditCard, count: counts.payments },
    { key: 'chat', label: 'Чат', icon: MessageSquare, count: counts.chat, accent: true },
    { key: 'notes', label: 'Заметки', icon: FileText, count: counts.notes },
  ];

  return (
    <div
      role="tablist"
      aria-label="Разделы профиля"
      className="-mx-1 flex gap-1 overflow-x-auto border-b-[0.5px] border-border px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {tabs.map((t) => {
        const active = t.key === value;
        const Icon = t.icon;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.key)}
            className={cn(
              'relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap px-3.5 pb-3.5 pt-3 text-[13.5px] font-semibold tracking-[-0.1px] transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'text-fg' : 'text-fg-muted hover:text-fg',
            )}
          >
            <Icon className="size-[13px]" strokeWidth={2} />
            {t.label}
            {t.count != null && (
              <span
                className={cn(
                  'rounded-full px-[7px] py-px text-[11px] font-bold tabular-nums',
                  active
                    ? 'bg-fg text-bg'
                    : t.accent
                      ? 'bg-primary-soft text-primary-deep dark:text-primary'
                      : 'bg-surface-3 text-fg-muted',
                )}
              >
                {t.count}
              </span>
            )}
            {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-t-sm bg-fg" />}
          </button>
        );
      })}
    </div>
  );
}
