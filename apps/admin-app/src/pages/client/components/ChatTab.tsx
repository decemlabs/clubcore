import { cn } from '@/lib/cn';
import { Send } from '@/components/icons';
import type { ChatEntry, ChatTabData } from '@/features/clients/detail';
import { Card, CardHead, CardLink } from './shared';

function Bubble({ entry }: { entry: Extract<ChatEntry, { kind: 'msg' }> }) {
  if (entry.side === 'system') {
    return (
      <div className="max-w-[85%] self-center rounded-xl border-[0.5px] border-border bg-surface-2 px-3 py-1.5 text-center text-xs text-fg-muted">
        {entry.text}
      </div>
    );
  }

  const me = entry.side === 'me';
  return (
    <div
      className={cn(
        'relative max-w-[85%] rounded-2xl px-3 pb-[22px] pt-2.5 text-[13.5px] leading-snug @[480px]:max-w-[70%]',
        me
          ? 'self-end rounded-br-md bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
          : entry.unread
            ? 'self-start rounded-bl-md border-[0.5px] border-transparent bg-primary-soft text-fg'
            : 'self-start rounded-bl-md border-[0.5px] border-border bg-surface text-fg',
      )}
    >
      {entry.text}
      {entry.time ? (
        <span
          className={cn(
            'absolute bottom-1.5 right-3 text-[10.5px] font-medium',
            me
              ? 'text-bg/50 dark:text-[#06120c]/55'
              : entry.unread
                ? 'font-semibold text-primary-deep dark:text-primary'
                : 'text-fg-subtle',
          )}
        >
          {entry.time}
        </span>
      ) : null}
    </div>
  );
}

export function ChatTab({ data }: { data: ChatTabData }) {
  return (
    <Card>
      <CardHead
        title="Чат с клиентом"
        sub={data.lastActivity}
        action={<CardLink>Открыть полностью →</CardLink>}
        className="border-b-[0.5px] border-border"
      />
      <div className="flex max-h-[480px] flex-col gap-2.5 overflow-y-auto bg-bg px-5 py-4">
        {data.entries.map((entry) =>
          entry.kind === 'day' ? (
            <div
              key={entry.id}
              className="my-2 self-center rounded-full bg-surface-2 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.4px] text-fg-subtle"
            >
              {entry.label}
            </div>
          ) : (
            <Bubble key={entry.id} entry={entry} />
          ),
        )}
      </div>
      <form
        className="flex gap-2 border-t-[0.5px] border-border bg-surface px-4 py-3"
        onSubmit={(e) => e.preventDefault()}
      >
        <input
          placeholder={data.composePlaceholder}
          className="h-[38px] flex-1 rounded-full border-[0.5px] border-border bg-surface-2 px-3.5 text-[13px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle focus:bg-surface"
        />
        <button
          type="submit"
          className="inline-flex h-[38px] items-center gap-1.5 rounded-full bg-fg px-4 text-[13px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
        >
          <Send className="size-[14px]" strokeWidth={2.4} />
          Отправить
        </button>
      </form>
    </Card>
  );
}
