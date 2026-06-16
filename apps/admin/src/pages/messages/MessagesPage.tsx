/**
 * MessagesPage — staff chat inbox, wired to real staff endpoints (Phase 116 MSG-01/02).
 *
 * Data source: useThreads / useMarkThreadRead (real hooks, mock removed).
 * Component structure: ConversationList / ThreadPane / ClientPanel reused;
 * only data mapping changes (StaffThread → Conversation, StaffMessage → ThreadItem).
 *
 * RBAC:
 *   Both roles see the inbox (LIST, MESSAGES — not in OWNER_ONLY).
 *   Composer is owner-only — handled inside ThreadPane via can(role,'create','messages').
 */
import { useState } from 'react';
import { isSameDay, parseISO, subDays } from 'date-fns';
import { MessageSquare } from '@/components/icons';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { useThreads, useMarkThreadRead } from '@/features/messages/api';
import { useSession } from '@/features/auth/api';
import { formatRelativeRu } from '@/lib/format';
import type { Conversation, ClientPanelData } from '@/features/messages/types';
import type { StaffThread } from '@/features/messages/types';
import { MessagesPageHead } from './components/MessagesPageHead';
import { MessageTabs } from './components/MessageTabs';
import { ConversationList } from './components/ConversationList';
import { ThreadPane } from './components/ThreadPane';
import { ClientPanel } from './components/ClientPanel';

// ---------------------------------------------------------------------------
// StaffThread → Conversation mapping (for ConversationList props)
// ---------------------------------------------------------------------------

/** Bucket a thread into today/yesterday/earlier for ConversationList grouping. */
function threadDay(lastMessageAt: string | null): 'today' | 'yesterday' | 'earlier' {
  if (!lastMessageAt) return 'today';
  const d = parseISO(lastMessageAt);
  const now = new Date();
  if (isSameDay(d, now)) return 'today';
  if (isSameDay(d, subDays(now, 1))) return 'yesterday';
  // WR-04: anything older than yesterday goes to the "Ранее" bucket, NOT "Вчера".
  return 'earlier';
}

function staffThreadToConversation(t: StaffThread): Conversation {
  return {
    id: t.id,
    initials: t.clientInitials || t.clientName.slice(0, 2).toUpperCase(),
    color: 'var(--primary)', // single colour token; no raw palette
    source: 'client',
    name: t.clientName,
    sub: '',
    last: t.lastMessageBody ?? '',
    lastPrefix:
      t.lastMessageRole === 'staff' ? { text: 'Вы:', tone: 'note' as const } : undefined,
    tags: [],
    time: t.lastMessageAt ? formatRelativeRu(t.lastMessageAt) : '',
    unread: t.staffUnreadCount > 0 ? t.staffUnreadCount : undefined,
    day: threadDay(t.lastMessageAt),
  };
}

// ---------------------------------------------------------------------------
// Minimal ClientPanelData built from the active thread
// (wire shape has no deep client-detail fields; panel shows fallback state)
// ---------------------------------------------------------------------------

function buildClientPanel(t: StaffThread): ClientPanelData {
  return {
    initials: t.clientInitials || t.clientName.slice(0, 2).toUpperCase(),
    gradient: 'linear-gradient(135deg,#cbd5e1 0%,#475569 100%)',
    name: t.clientName,
    ptag: '',
    chips: [],
    plan: { name: '', sub: '', rows: [], barPct: 0 },
    upcoming: [],
  };
}

// Placeholder tab list (status tabs come from a separate endpoint in v2 scope)
const STATUS_TABS = [
  { id: 'open', label: 'Открытые' },
  { id: 'mine', label: 'Мои' },
  { id: 'snoozed', label: 'Отложенные' },
];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export function MessagesPage() {
  const session = useSession();
  const role = session.data?.role ?? 'reception';

  const threadsQuery = useThreads();
  const [activeId, setActiveId] = useState<string | null>(null);
  const markRead = useMarkThreadRead();

  const { data, isPending, isError, refetch } = threadsQuery;

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const threads = data.items;

  // Inbox empty state
  if (threads.length === 0) {
    return (
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
        <MessagesPageHead unread={0} mine={0} />
        <EmptyState
          icon={MessageSquare}
          title="Нет активных диалогов"
          message="Как только клиент напишет, диалог появится здесь."
          className="py-24"
        />
      </div>
    );
  }

  const resolvedActiveId = activeId;
  const activeThread: StaffThread | null = resolvedActiveId
    ? (threads.find((t) => t.id === resolvedActiveId) ?? null)
    : null;

  const conversations: Conversation[] = threads.map(staffThreadToConversation);
  const totalUnread = threads.reduce((s, t) => s + t.staffUnreadCount, 0);

  function onSelect(id: string) {
    setActiveId(id);
    markRead.mutate(id); // fire-and-forget; backend updates staff_last_read_at watermark
  }

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <MessagesPageHead unread={totalUnread} mine={0} />

      <MessageTabs tabs={STATUS_TABS} />

      <div className="grid h-[680px] grid-cols-1 overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1 md:grid-cols-[300px_minmax(0,1fr)] xl:h-[720px] xl:grid-cols-[320px_minmax(0,1fr)_340px]">
        <ConversationList
          convs={conversations}
          activeId={resolvedActiveId ?? ''}
          read={new Set<string>()}
          onSelect={onSelect}
          className="hidden md:flex"
        />
        <ThreadPane activeThread={activeThread} role={role} />
        {activeThread ? (
          <ClientPanel client={buildClientPanel(activeThread)} className="hidden xl:flex" />
        ) : (
          <ClientPanel
            client={buildClientPanel(threads[0]!)}
            className="hidden xl:flex"
          />
        )}
      </div>
    </div>
  );
}
