import { useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { SearchInput } from '@/components/data/Toolbar';
import { Bot, CheckCircle2, Clock, Mail, MessageSquare, Send } from '@/components/icons';
import type { Conversation, ConvChannel, ConvSource } from '@/features/messages/types';
import { TAG_TONE } from './msg-styles';

const CHANNEL_ICON: Record<ConvChannel, { Icon: LucideIcon; title: string }> = {
  app: { Icon: MessageSquare, title: 'Чат в приложении' },
  telegram: { Icon: Send, title: 'Telegram' },
  email: { Icon: Mail, title: 'Email' },
  bot: { Icon: Bot, title: 'Бот' },
};

type SourceFilter = 'all' | ConvSource;
const SOURCE_PILLS: { value: SourceFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'client', label: 'Клиенты' },
  { value: 'trainer', label: 'Тренеры' },
  { value: 'bot', label: 'Боты' },
];

const DAY_LABEL: Record<Conversation['day'], string> = { today: 'Сегодня', yesterday: 'Вчера' };

function ConvRow({
  conv,
  active,
  read,
  onSelect,
}: {
  conv: Conversation;
  active: boolean;
  read: boolean;
  onSelect: () => void;
}) {
  const unread = conv.unread != null && !read && !active;
  const channel = conv.channel ? CHANNEL_ICON[conv.channel] : null;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'relative grid w-full grid-cols-[36px_minmax(0,1fr)_auto] items-start gap-[11px] border-b-[0.5px] border-border px-4 py-3 text-left transition-colors',
        active
          ? 'bg-surface before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:rounded-r before:bg-fg dark:before:bg-primary'
          : unread
            ? 'bg-[color-mix(in_oklab,var(--primary)_8%,var(--surface-2))] hover:bg-surface'
            : 'hover:bg-surface',
      )}
    >
      <span className="relative">
        <Initials initials={conv.initials} color={conv.color} className="size-9 text-[12px]" />
        {conv.verified ? (
          <span className="absolute -bottom-0.5 -right-0.5 grid size-3.5 place-items-center rounded-full bg-primary text-[#06120c] ring-2 ring-surface-2">
            <CheckCircle2 className="size-2.5" strokeWidth={3} />
          </span>
        ) : null}
      </span>

      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={cn('truncate text-[13.5px]', unread ? 'font-extrabold' : 'font-bold')}>
            {conv.name}
          </span>
          {channel ? (
            <channel.Icon className="size-3 shrink-0 text-fg-subtle" aria-label={channel.title} />
          ) : null}
        </div>
        <div className="truncate text-[11px] text-fg-subtle">{conv.sub}</div>
        <div
          className={cn(
            'mt-0.5 line-clamp-2 text-[12.5px]',
            unread ? 'text-fg-muted' : 'text-fg-subtle',
          )}
        >
          {conv.lastPrefix ? (
            <span
              className={cn(
                'font-semibold',
                conv.lastPrefix.tone === 'draft'
                  ? 'text-warning-deep'
                  : 'text-primary-deep dark:text-primary',
              )}
            >
              {conv.lastPrefix.text}{' '}
            </span>
          ) : null}
          {conv.last}
        </div>
        {conv.tags.length > 0 ? (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {conv.tags.map((t) => (
              <span
                key={t.label}
                className={cn(
                  'rounded px-1.5 py-px text-[10px] font-bold uppercase tracking-[0.2px]',
                  TAG_TONE[t.tone],
                )}
              >
                {t.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col items-end gap-1.5">
        <span
          className={cn(
            'text-[11px] tabular-nums',
            unread ? 'font-bold text-primary-deep dark:text-primary' : 'text-fg-subtle',
          )}
        >
          {conv.time}
        </span>
        {conv.snoozed ? (
          <Clock className="size-3.5 text-warning-deep" aria-label="отложено" />
        ) : unread ? (
          <span className="grid min-w-[18px] place-items-center rounded-full bg-primary px-1 text-[10.5px] font-bold text-[#06120c]">
            {conv.unread}
          </span>
        ) : null}
      </div>
    </button>
  );
}

/** Левая колонка инбокса: поиск, фильтр-пилюли источника, диалоги по дням. */
export function ConversationList({
  convs,
  activeId,
  read,
  onSelect,
  className,
}: {
  convs: Conversation[];
  activeId: string;
  read: Set<string>;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const [query, setQuery] = useState('');
  const [source, setSource] = useState<SourceFilter>('all');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return convs.filter((c) => {
      if (source !== 'all' && c.source !== source) return false;
      if (q && !`${c.name} ${c.last}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [convs, query, source]);

  const days = ['today', 'yesterday'] as const;

  return (
    <div
      className={cn('flex min-h-0 flex-col border-r-[0.5px] border-border bg-surface-2', className)}
    >
      <div className="shrink-0 border-b-[0.5px] border-border p-3">
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="Поиск по сообщениям…"
          inputClassName="h-[34px]"
        />
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {SOURCE_PILLS.map((p) => {
            const isActive = source === p.value;
            return (
              <button
                key={p.value}
                type="button"
                onClick={() => setSource(p.value)}
                className={cn(
                  'rounded-full px-2.5 py-1 text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive
                    ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
                    : 'text-fg-muted hover:bg-surface-3 hover:text-fg',
                )}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {visible.length === 0 ? (
          <div className="px-4 py-10 text-center text-[13px] text-fg-subtle">Ничего не найдено</div>
        ) : (
          days.map((day) => {
            const rows = visible.filter((c) => c.day === day);
            if (rows.length === 0) return null;
            return (
              <div key={day}>
                <div className="px-4 pb-1 pt-3 text-[10.5px] font-semibold uppercase tracking-[0.4px] text-fg-subtle">
                  {DAY_LABEL[day]}
                </div>
                {rows.map((c) => (
                  <ConvRow
                    key={c.id}
                    conv={c}
                    active={c.id === activeId}
                    read={read.has(c.id)}
                    onSelect={() => onSelect(c.id)}
                  />
                ))}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
