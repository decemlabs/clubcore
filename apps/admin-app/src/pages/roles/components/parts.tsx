import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  Settings,
  Shield,
  Building2,
  ShoppingBag,
  User,
  FileText,
  Minus,
  Eye,
  SquarePen,
} from '@/components/icons';
import type { PermLevel, RoleAvatar, RoleIcoClass } from '@/features/roles/types';

const ROLE_ICON: Record<string, LucideIcon> = {
  shield: Shield,
  gear: Settings,
  building: Building2,
  store: ShoppingBag,
  user: User,
  file: FileText,
};

const ICO_CLASS: Record<RoleIcoClass, string> = {
  owner: 'bg-ink text-primary dark:bg-primary dark:text-[#06120c]',
  admin: 'bg-primary-soft text-primary-deep dark:text-primary',
  purple: 'bg-indigo-500/15 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300',
  amber: 'bg-warning-soft text-warning-deep',
};

/** Цветная иконка-тайл роли. */
export function RoleIco({
  icoClass,
  icon,
  size = 'sm',
}: {
  icoClass: RoleIcoClass;
  icon: string;
  size?: 'sm' | 'lg';
}) {
  const Icon = ROLE_ICON[icon] ?? Shield;
  return (
    <span
      className={cn(
        'grid shrink-0 place-items-center',
        ICO_CLASS[icoClass],
        size === 'lg' ? 'size-[46px] rounded-[13px]' : 'size-[34px] rounded-[10px]',
      )}
    >
      <Icon className={size === 'lg' ? 'size-[22px]' : 'size-[17px]'} strokeWidth={2} />
    </span>
  );
}

/** Перекрывающийся стек аватаров участников роли. */
export function AvatarStack({ avas }: { avas: RoleAvatar[] }) {
  return (
    <div className="flex">
      {avas.map((a, i) => (
        <span
          key={i}
          style={a.gradient ? { background: a.gradient } : undefined}
          className={cn(
            'grid size-[30px] place-items-center rounded-full text-[11px] font-bold ring-2 ring-surface',
            a.gradient ? 'text-white' : 'bg-surface-3 text-fg-muted',
            i > 0 && '-ml-2',
          )}
        >
          {a.initials}
        </span>
      ))}
    </div>
  );
}

/* ---------- Panel head ---------- */

export function PcHead({ title, count }: { title: string; count: number }) {
  return (
    <div className="flex items-center gap-2.5 border-b-[0.5px] border-border px-4 py-3.5">
      <h2 className="text-sm font-bold">{title}</h2>
      <span className="rounded-full bg-surface-3 px-2 py-0.5 text-[11px] font-bold tabular-nums text-fg-subtle">
        {count}
      </span>
    </div>
  );
}

/* ---------- Permission segmented control ---------- */

const LEVELS: { lvl: PermLevel; label: string; icon: LucideIcon }[] = [
  { lvl: 0, label: 'Нет', icon: Minus },
  { lvl: 1, label: 'Просмотр', icon: Eye },
  { lvl: 2, label: 'Управление', icon: SquarePen },
];

export function Seg({
  value,
  onChange,
  disabled,
}: {
  value: PermLevel;
  onChange: (lvl: PermLevel) => void;
  disabled?: boolean;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-3 gap-[3px] rounded-[9px] bg-surface-3 p-[3px]',
        disabled && 'pointer-events-none opacity-60',
      )}
    >
      {LEVELS.map(({ lvl, label, icon: Icon }) => {
        const on = value === lvl;
        return (
          <button
            key={lvl}
            type="button"
            aria-pressed={on}
            disabled={disabled}
            onClick={() => onChange(lvl)}
            className={cn(
              'flex h-[30px] items-center justify-center gap-1.5 rounded-[7px] text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              on
                ? cn(
                    'bg-surface shadow-1',
                    lvl === 0
                      ? 'text-fg-subtle'
                      : lvl === 2
                        ? 'text-primary-deep dark:text-primary'
                        : 'text-fg',
                  )
                : 'text-fg-muted hover:text-fg',
            )}
          >
            <Icon className="size-[13px] max-[420px]:hidden" strokeWidth={2.2} />
            {label}
          </button>
        );
      })}
    </div>
  );
}
