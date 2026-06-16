import { useBranches } from '@/features/branches/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { PageHeader } from '@/components/layout/PageHeader';
import { StatStrip } from '@/components/layout/StatStrip';
import { Button } from '@/components/ui/button';
import { Plus } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';
import { formatInt } from '@/lib/format';
import { SummaryTile, BranchCard, DraftCard } from './components/parts';

export function BranchesPage() {
  const { data, isPending, isError, refetch } = useBranches();
  const { open } = useModals();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;
  const { summary, branches } = data;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Филиалы"
        subtitle={
          <>
            <b className="font-semibold text-fg">{summary.branchesActive} действующих</b> филиала и{' '}
            {summary.branchesUpcoming} в подготовке. Управляйте картотекой, командой и настройками
            каждого зала.
          </>
        }
        actions={
          <Button
            onClick={() => open('branch')}
            className="h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold"
          >
            <Plus className="size-[15px]" strokeWidth={2.4} />
            Добавить филиал
          </Button>
        }
      />

      <StatStrip className="grid-cols-2 gap-3 lg:grid-cols-4">
        <SummaryTile
          label="Филиалов"
          value={String(summary.branchesActive)}
          unit={` + ${summary.branchesUpcoming}`}
        />
        <SummaryTile label="Клиентов всего" value={formatInt(summary.clientsTotal)} />
        <SummaryTile label="Тренеров" value={String(summary.trainersTotal)} />
        <SummaryTile label="Выручка · апрель" value={formatInt(summary.revenueApril)} unit=" ₽" />
      </StatStrip>

      <div className="grid grid-cols-1 gap-4 min-[560px]:[grid-template-columns:repeat(auto-fill,minmax(330px,1fr))]">
        {branches.map((b) => (
          <BranchCard key={b.id} branch={b} />
        ))}
        <DraftCard />
      </div>
    </div>
  );
}
