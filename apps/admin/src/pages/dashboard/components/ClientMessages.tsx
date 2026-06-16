import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { Reply } from '@/components/icons';
import type { ClientMessage } from '@/features/dashboard/types';
import { CardLink, DashboardCard, Initials } from './shared';

function MessageRow({ message, first }: { message: ClientMessage; first: boolean }) {
  return (
    <Link
      to={ROUTES.messages}
      className={cn(
        'grid grid-cols-[32px_minmax(0,1fr)_auto] items-start gap-3 px-5 py-3 transition-colors hover:bg-surface-2',
        !first && 'border-t-[0.5px] border-border',
        message.unread && 'bg-[color-mix(in_oklab,var(--primary-soft)_35%,transparent)]',
      )}
    >
      <Initials initials={message.initials} color={message.color} className="size-8 text-[11px]" />

      <div className="min-w-0">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="truncate text-[13px] font-semibold">{message.name}</span>
          <span className="ml-auto shrink-0 text-[11px] text-fg-subtle">{message.time}</span>
        </div>
        <div className="mt-[3px] line-clamp-2 text-[12.5px] leading-[1.35] text-fg-muted">
          {message.body}
        </div>
      </div>

      <span
        aria-hidden
        className="grid h-[30px] items-center gap-1.5 self-center rounded-lg bg-fg px-3 text-xs font-semibold text-bg dark:bg-primary dark:text-[#06120c] grid-flow-col @max-[400px]:w-[34px] @max-[400px]:px-0"
      >
        <Reply className="size-[13px]" strokeWidth={2.2} />
        <span className="@max-[400px]:hidden">Ответить</span>
      </span>
    </Link>
  );
}

export function ClientMessages({ messages }: { messages: ClientMessage[] }) {
  const unread = messages.filter((m) => m.unread).length;
  return (
    <DashboardCard
      title="Обращения клиентов"
      subtitle={`${unread} новых · ответили на 12 за день`}
      action={<CardLink to={ROUTES.messages}>Чат</CardLink>}
    >
      <div className="@container">
        {messages.map((message, i) => (
          <MessageRow key={message.id} message={message} first={i === 0} />
        ))}
      </div>
    </DashboardCard>
  );
}
