import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { pluralRu } from '@/lib/format';
import { Checkbox } from '@/components/ui/Checkbox';
import { Users, User, CreditCard, Calendar, Undo2, Trash2 } from '@/components/icons';
import type { TrashItem, TrashType } from '@/features/trash/types';

const TYPE_META: Record<TrashType, { label: string; icon: LucideIcon }> = {
  client: { label: 'Клиент', icon: Users },
  trainer: { label: 'Тренер', icon: User },
  plan: { label: 'Тариф', icon: CreditCard },
  session: { label: 'Тренировка', icon: Calendar },
};

function ItemIcon({ item }: { item: TrashItem }) {
  if (item.gradient) {
    return (
      <span
        style={{ background: item.gradient }}
        className="grid size-9 shrink-0 place-items-center rounded-[10px] text-[12px] font-bold text-white"
      >
        {item.initials}
      </span>
    );
  }
  const Icon = TYPE_META[item.type].icon;
  return (
    <span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-surface-3 text-fg-muted">
      <Icon className="size-4" strokeWidth={2} />
    </span>
  );
}

function TypeChip({ type }: { type: TrashType }) {
  const { label, icon: Icon } = TYPE_META[type];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-3 px-2.5 py-[3px] text-[11px] font-semibold text-fg-muted">
      <Icon className="size-3" strokeWidth={2} />
      {label}
    </span>
  );
}

const ROW_BTN =
  'inline-flex h-8 items-center justify-center gap-1.5 rounded-[9px] border-[0.5px] border-border-strong bg-surface px-2.5 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

export function TrashRow({
  item,
  selected,
  onToggle,
  onRestore,
  onDelete,
}: {
  item: TrashItem;
  selected: boolean;
  onToggle: () => void;
  onRestore: () => void;
  onDelete: () => void;
}) {
  const soon = item.daysLeft <= 3;
  return (
    <div className="relative grid grid-cols-1 gap-2.5 border-b-[0.5px] border-border px-4 py-3 transition-colors last:border-b-0 hover:bg-surface-2 md:grid-cols-[24px_minmax(0,1fr)_120px_150px_auto] md:items-center md:gap-3.5">
      <div className="absolute right-3 top-3 md:static">
        <Checkbox
          checked={selected}
          onCheckedChange={onToggle}
          aria-label={`Выбрать ${item.name}`}
        />
      </div>

      <div className="flex min-w-0 items-center gap-3 pr-8 md:pr-0">
        <ItemIcon item={item} />
        <div className="min-w-0">
          <div className="truncate text-[13.5px] font-semibold">{item.name}</div>
          <div className="truncate text-[11.5px] text-fg-subtle">{item.sub}</div>
        </div>
      </div>

      <div>
        <TypeChip type={item.type} />
      </div>

      <div className={cn('text-[12.5px] tabular-nums', soon && 'text-danger')}>
        <span className="text-fg-subtle md:hidden">Удалится через: </span>
        <b className="font-bold">{item.daysLeft}</b>{' '}
        {pluralRu(item.daysLeft, ['день', 'дня', 'дней'])}
        <span className={cn('block text-[11px]', soon ? 'text-danger/80' : 'text-fg-subtle')}>
          в корзине с {item.deletedAt}
        </span>
      </div>

      <div className="flex gap-1.5 max-md:mt-1">
        <button type="button" onClick={onRestore} className={cn(ROW_BTN, 'max-md:flex-1')}>
          <Undo2 className="size-3.5" strokeWidth={2} />
          Вернуть
        </button>
        <button
          type="button"
          onClick={onDelete}
          title="Удалить навсегда"
          aria-label={`Удалить «${item.name}» навсегда`}
          className={cn(ROW_BTN, 'px-2 text-danger hover:bg-danger-soft')}
        >
          <Trash2 className="size-3.5" strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}

export interface PillTab {
  key: string;
  label: string;
  count: number;
}

export function PillTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: PillTab[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={cn(
              'inline-flex shrink-0 items-center gap-2 rounded-full border-[0.5px] px-3.5 py-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'border-fg bg-fg text-bg dark:border-border-strong dark:bg-surface-3 dark:text-fg'
                : 'border-border bg-surface text-fg-muted hover:border-border-strong hover:text-fg',
            )}
          >
            {t.label}
            <span
              className={cn(
                'rounded-full px-[7px] py-px text-[11px] font-bold tabular-nums',
                active ? 'bg-white/20 dark:bg-surface' : 'bg-surface-3 text-fg-muted',
              )}
            >
              {t.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
