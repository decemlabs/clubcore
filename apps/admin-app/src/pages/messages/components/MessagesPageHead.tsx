import { useState } from 'react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Plus } from '@/components/icons';

type Owner = 'me' | 'team' | 'all';

export function MessagesPageHead({ unread, mine }: { unread: number; mine: number }) {
  const [owner, setOwner] = useState<Owner>('me');
  const options: SegmentedOption<Owner>[] = [
    { value: 'me', label: `Я · ${mine}` },
    { value: 'team', label: 'Команда' },
    { value: 'all', label: 'Все' },
  ];
  return (
    <PageHeader
      title="Сообщения"
      subtitle={
        <>
          <b className="font-semibold text-fg">{unread}</b> непрочитанных диалогов
        </>
      }
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Segmented options={options} value={owner} onChange={setOwner} ariaLabel="Чьи диалоги" />
          <Button
            onClick={() => toast('Новый диалог', { description: 'Выберите клиента или канал' })}
            className="h-[34px] shrink-0 gap-1.5 rounded-full px-3.5 text-[13px] font-semibold"
          >
            <Plus className="size-3.5" strokeWidth={2.4} />
            <span className="max-sm:hidden">Новый диалог</span>
          </Button>
        </div>
      }
    />
  );
}
