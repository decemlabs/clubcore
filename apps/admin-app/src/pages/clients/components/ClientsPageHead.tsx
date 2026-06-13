import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Download, MessageSquare } from '@/components/icons';
import type { ClientsSummary } from '@/features/clients/types';

const ACTION_CLS =
  'h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0';

export function ClientsPageHead({ summary }: { summary: ClientsSummary }) {
  return (
    <PageHeader
      title="Клиенты"
      subtitle={
        <>
          <b className="font-semibold text-fg">{summary.total}</b> клиентов в {summary.branch} ·{' '}
          <b className="font-semibold text-fg">+{summary.weeklyNew}</b> за неделю ·{' '}
          <b className="font-semibold text-fg">{summary.expiringSoon}</b> абонементов истекают в
          ближайшие {summary.expiringDays} дней
        </>
      }
      actions={
        <>
          <Button variant="outline" className={ACTION_CLS}>
            <Download className="size-[14px]" />
            <span className="max-sm:hidden">Экспорт</span>
          </Button>
          <Button variant="outline" className={ACTION_CLS}>
            <MessageSquare className="size-[14px]" />
            <span className="max-sm:hidden">Рассылка</span>
          </Button>
        </>
      }
    />
  );
}
