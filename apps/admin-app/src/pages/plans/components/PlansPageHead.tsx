import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Download } from '@/components/icons';
import { formatRub } from '@/lib/format';
import type { PlansSummary } from '@/features/plans/types';

export function PlansPageHead({ summary }: { summary: PlansSummary }) {
  return (
    <PageHeader
      title="Абонементы и тарифы"
      subtitle={
        <>
          <b className="font-semibold text-fg">{summary.activeSubs}</b> активных абонементов ·{' '}
          <b className="font-semibold text-fg">MRR {formatRub(summary.mrr)}</b> · {summary.tariffCount}{' '}
          тарифа в продаже
        </>
      }
      actions={
        <Button
          variant="outline"
          onClick={() => toast.success('Экспорт продаж', { description: 'CSV · 6 месяцев' })}
          className="h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0"
        >
          <Download className="size-[14px]" />
          <span className="max-sm:hidden">Экспорт продаж</span>
        </Button>
      }
    />
  );
}
