import { useState } from 'react';
import { useMessages } from '@/features/messages/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { MessagesPageHead } from './components/MessagesPageHead';
import { MessageTabs } from './components/MessageTabs';
import { ConversationList } from './components/ConversationList';
import { ThreadPane } from './components/ThreadPane';
import { ClientPanel } from './components/ClientPanel';

export function MessagesPage() {
  const { data, isPending, isError, refetch } = useMessages();
  const [activeId, setActiveId] = useState('c1');
  const [read, setRead] = useState<Set<string>>(() => new Set());

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;
  if (data.conversations.length === 0) return null;

  const activeConv = data.conversations.find((c) => c.id === activeId) ?? data.conversations[0]!;
  const onSelect = (id: string) => {
    setActiveId(id);
    setRead((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <MessagesPageHead unread={data.unreadDialogs} mine={data.mineCount} />

      <MessageTabs tabs={data.statusTabs} />

      <div className="grid h-[680px] grid-cols-1 overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1 md:grid-cols-[300px_minmax(0,1fr)] xl:h-[720px] xl:grid-cols-[320px_minmax(0,1fr)_340px]">
        <ConversationList
          convs={data.conversations}
          activeId={activeId}
          read={read}
          onSelect={onSelect}
          className="hidden md:flex"
        />
        <ThreadPane
          conv={activeConv}
          threadMeta={data.threadMeta}
          seed={data.thread}
          draft={data.draft}
          quickReplies={data.quickReplies}
        />
        <ClientPanel client={data.client} className="hidden xl:flex" />
      </div>
    </div>
  );
}
