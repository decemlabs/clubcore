import { useEffect, useRef, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Archive,
  Check,
  CheckCircle2,
  Clock,
  Info,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Send,
  Smile,
  User,
} from '@/components/icons';
import type { Bubble, Conversation, QuickReply, ThreadItem } from '@/features/messages/types';

type ComposeMode = 'reply' | 'note' | 'resolve';

const HTBTN =
  'grid size-8 shrink-0 place-items-center rounded-lg border-[0.5px] border-border text-fg-muted transition-colors hover:border-border-strong hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function MsgBubble({ b }: { b: Bubble }) {
  if (b.type === 'sys') {
    return (
      <div className="flex justify-center py-1">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-3 px-3 py-1 text-[12px] text-fg-muted">
          <Check className="size-3 text-primary-deep dark:text-primary" strokeWidth={2.6} />
          {b.text}
        </span>
      </div>
    );
  }
  if (b.type === 'note') {
    return (
      <div className="rounded-2xl border border-[#fde68a] bg-[#fffbeb] px-3.5 py-2.5 text-[#713f12] dark:border-[#a16207]/40 dark:bg-[rgba(234,179,8,0.12)] dark:text-[#fde68a]">
        {b.noteHead ? (
          <div className="mb-1 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.3px] opacity-80">
            <Info className="size-3" />
            {b.noteHead}
          </div>
        ) : null}
        <div className="text-[13.5px] leading-relaxed">{b.text}</div>
        {b.meta ? <div className="mt-1 text-[10.5px] opacity-70">{b.meta}</div> : null}
      </div>
    );
  }
  const me = b.type === 'me';
  return (
    <div className={cn('flex', me ? 'justify-end' : 'justify-start')}>
      <div className={cn('max-w-[78%]', me ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'rounded-2xl border px-3.5 py-2.5 text-[13.5px] leading-relaxed',
            me
              ? 'rounded-br-[5px] border-transparent bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
              : 'rounded-bl-[5px] border-border bg-surface text-fg',
          )}
        >
          {b.photo ? (
            <div className="mb-2 overflow-hidden rounded-xl">
              <div
                className="flex h-[140px] w-[220px] max-w-full items-end p-2"
                style={{
                  background: 'linear-gradient(135deg,#cbd5e1 0%,#475569 70%,#1e293b 100%)',
                }}
              >
                <span className="text-[11px] font-medium text-white [text-shadow:0_1px_2px_rgba(0,0,0,0.5)]">
                  {b.photo}
                </span>
              </div>
            </div>
          ) : null}
          {b.text}
        </div>
        {b.meta ? (
          <div className={cn('mt-1 text-[10.5px] text-fg-subtle', me ? 'text-right' : 'text-left')}>
            {b.meta}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ModeTab({
  active,
  icon: Icon,
  label,
  note,
  onClick,
}: {
  active: boolean;
  icon: LucideIcon;
  label: string;
  note?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active
          ? note
            ? 'bg-[#fef3c7] text-[#713f12] dark:bg-[rgba(234,179,8,0.16)] dark:text-[#fde68a]'
            : 'bg-surface-3 text-fg'
          : 'text-fg-muted hover:text-fg',
      )}
    >
      <Icon className="size-3.5" />
      {label}
    </button>
  );
}

/** Центральная колонка: шапка диалога, лента сообщений, composer. */
export function ThreadPane({
  conv,
  threadMeta,
  seed,
  draft,
  quickReplies,
}: {
  conv: Conversation;
  threadMeta: string;
  seed: ThreadItem[];
  draft: string;
  quickReplies: QuickReply[];
}) {
  const [items, setItems] = useState<ThreadItem[]>(seed);
  const [mode, setMode] = useState<ComposeMode>('reply');
  const [text, setText] = useState(draft);
  const msgsRef = useRef<HTMLDivElement>(null);
  const counter = useRef(0);

  useEffect(() => {
    const el = msgsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items]);

  const send = () => {
    const value = text.trim();
    if (!value) return;
    counter.current += 1;
    const isNote = mode === 'note';
    setItems((prev) => [
      ...prev,
      {
        kind: 'msg',
        id: `sent-${counter.current}`,
        type: isNote ? 'note' : 'me',
        text: value,
        noteHead: isNote ? 'Внутренняя заметка' : undefined,
        meta: isNote ? 'только что · видна только администраторам' : 'только что · ✓ отправлено',
      },
    ]);
    setText('');
  };

  return (
    <div className="flex min-h-0 flex-col bg-bg">
      {/* Шапка */}
      <div className="flex shrink-0 items-center gap-3 border-b-[0.5px] border-border bg-surface px-4 py-3">
        <Initials initials={conv.initials} color={conv.color} className="size-9 text-[12px]" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14.5px] font-bold">{conv.name}</div>
          <div className="flex items-center gap-1.5 truncate text-[11.5px] text-fg-subtle">
            <span className="size-1.5 shrink-0 rounded-full bg-primary" />
            {threadMeta}
          </div>
        </div>
        <button
          type="button"
          onClick={() => toast('Переназначить диалог', { description: 'Сейчас: Маша Костина' })}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-fg px-2.5 text-[12px] font-semibold text-bg transition-colors hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8] max-sm:hidden"
        >
          <User className="size-3.5" />
          Маша К.
        </button>
        <button
          type="button"
          className={HTBTN}
          aria-label="Отложить"
          title="Отложить"
          onClick={() => toast.success('Диалог отложен на 3 часа')}
        >
          <Clock className="size-4" />
        </button>
        <button
          type="button"
          className={HTBTN}
          aria-label="Архив"
          title="Архив"
          onClick={() => toast.success('Диалог архивирован')}
        >
          <Archive className="size-4" />
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className={HTBTN} aria-label="Ещё" title="Ещё">
              <MoreHorizontal className="size-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[200px]">
            <DropdownMenuItem onSelect={() => toast.success('Отмечено непрочитанным')}>
              Отметить непрочитанным
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => toast('Профиль клиента')}>
              Профиль клиента
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-danger focus:text-danger"
              onSelect={() => toast.success('Клиент заблокирован')}
            >
              Заблокировать
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Сообщения */}
      <div ref={msgsRef} className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-5 py-4">
        {items.map((item, i) =>
          item.kind === 'daysep' ? (
            <div
              key={`d${i}`}
              className="my-1 flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.3px] text-fg-subtle"
            >
              <span className="h-px flex-1 bg-border" />
              {item.label}
              <span className="h-px flex-1 bg-border" />
            </div>
          ) : (
            <MsgBubble key={item.id} b={item} />
          ),
        )}
      </div>

      {/* Composer */}
      <div className="shrink-0 border-t-[0.5px] border-border bg-surface px-4 pb-3.5 pt-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex gap-1">
            <ModeTab
              active={mode === 'reply'}
              icon={MessageSquare}
              label="Ответ"
              onClick={() => setMode('reply')}
            />
            <ModeTab
              active={mode === 'note'}
              icon={Info}
              label="Заметка"
              note
              onClick={() => setMode('note')}
            />
            <ModeTab
              active={mode === 'resolve'}
              icon={CheckCircle2}
              label="Решить"
              onClick={() => setMode('resolve')}
            />
          </div>
          <div className="text-[11.5px] text-fg-subtle max-md:hidden">
            Ответ на <b className="font-semibold text-fg-muted">{conv.name}</b> · в приложение и
            push
          </div>
        </div>

        <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {quickReplies.map((q) => (
            <button
              key={q.key}
              type="button"
              onClick={() => setText((t) => (t ? `${t} ${q.text}` : q.text))}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full border-[0.5px] border-border px-2.5 py-1 text-[12px] text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
            >
              <span className="font-mono text-[11px] text-fg-subtle">{q.key}</span>
              {q.text}
            </button>
          ))}
          <button
            type="button"
            className="inline-flex shrink-0 items-center rounded-full border-[0.5px] border-dashed border-border px-2.5 py-1 text-[12px] text-fg-subtle transition-colors hover:border-border-strong hover:text-fg"
          >
            + Шаблон
          </button>
        </div>

        <div className="mt-2 flex items-end gap-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                send();
              }
            }}
            rows={2}
            placeholder="Напишите ответ… ⌘↵ — отправить"
            className="min-h-[40px] max-h-[140px] flex-1 resize-none rounded-xl border-[0.5px] border-border bg-surface px-3 py-2 text-[13.5px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle"
          />
          <div className="flex shrink-0 items-center gap-1 pb-0.5">
            <button type="button" className={HTBTN} aria-label="Прикрепить">
              <Paperclip className="size-4" />
            </button>
            <button type="button" className={HTBTN} aria-label="Эмодзи">
              <Smile className="size-4" />
            </button>
            <button
              type="button"
              onClick={send}
              aria-label="Отправить"
              title="Отправить ⌘↵"
              className="grid size-9 place-items-center rounded-xl bg-fg text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
            >
              <Send className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
