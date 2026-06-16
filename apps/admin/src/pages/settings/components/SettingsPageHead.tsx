import type { LucideIcon } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { HelpCircle, History } from '@/components/icons';
import type { SettingsData } from '@/features/settings/types';

function HeadBtn({ icon: Icon, children }: { icon: LucideIcon; children: string }) {
  return (
    <button
      type="button"
      className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-border bg-surface px-[14px] text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-sm:px-0 max-sm:w-[38px] max-sm:justify-center"
    >
      <Icon className="size-[14px]" />
      <span className="max-sm:hidden">{children}</span>
    </button>
  );
}

export function SettingsPageHead({ summary }: { summary: SettingsData['summary'] }) {
  return (
    <PageHeader
      title="Настройки"
      subtitle={
        <>
          Сеть «{summary.network}» · <b className="font-semibold text-fg">{summary.branches}</b> ·{' '}
          {summary.clients} клиентов · {summary.trainers} тренеров ·{' '}
          <span className="font-semibold text-primary-deep dark:text-primary">
            ● все изменения сохранены
          </span>{' '}
          <span className="text-fg-subtle">{summary.updated}</span>
        </>
      }
      actions={
        <>
          <HeadBtn icon={History}>История изменений</HeadBtn>
          <HeadBtn icon={HelpCircle}>Помощь</HeadBtn>
        </>
      }
    />
  );
}
