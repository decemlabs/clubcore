import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Download } from '@/components/icons';
import type { Shift } from '@/features/cashbox/types';

function ShiftPill({ open }: { open: boolean }) {
  if (!open) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-3 px-2.5 py-1 text-[11.5px] font-bold uppercase tracking-[0.3px] text-fg-muted align-middle">
        <span className="size-1.5 rounded-full bg-fg-subtle" />
        смена закрыта
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-2.5 py-1 text-[11.5px] font-bold uppercase tracking-[0.3px] text-primary-deep align-middle dark:text-primary">
      <span className="size-1.5 animate-pulse rounded-full bg-primary-deep dark:bg-primary" />
      смена открыта
    </span>
  );
}

export function CashboxPageHead({ shift, shiftOpen }: { shift: Shift; shiftOpen: boolean }) {
  return (
    <PageHeader
      title={
        <span className="inline-flex flex-wrap items-center gap-3">
          Касса
          <ShiftPill open={shiftOpen} />
        </span>
      }
      subtitle={
        shiftOpen ? (
          <>
            {shift.cashier} · открыта в <b className="font-semibold text-fg">{shift.openedAt}</b> ·
            идёт уже <b className="font-semibold text-fg">{shift.duration}</b>
          </>
        ) : (
          'Смена не открыта — операции недоступны'
        )
      }
      actions={
        <Button
          variant="outline"
          onClick={() =>
            toast.success('Экспорт за день', { description: 'CSV · операции смены №142' })
          }
          className="h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0"
        >
          <Download className="size-[14px]" />
          <span className="max-sm:hidden">Экспорт за день</span>
        </Button>
      }
    />
  );
}
