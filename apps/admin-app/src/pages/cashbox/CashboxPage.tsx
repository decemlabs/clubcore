import { useState } from 'react';
import { useCashbox } from '@/features/cashbox/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { useModals } from '@/components/modals/modals-context';
import { Card } from '@/components/layout/Card';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Wallet } from '@/components/icons';
import { CashboxPageHead } from './components/CashboxPageHead';
import { CashboxKpis } from './components/CashboxKpis';
import { TransactionsCard } from './components/TransactionsCard';
import { ShiftDrawer } from './components/ShiftDrawer';

export function CashboxPage() {
  const { data, isPending, isError, refetch } = useCashbox();
  const { open } = useModals();
  const [shiftOpen, setShiftOpen] = useState(true);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <CashboxPageHead shift={data.shift} shiftOpen={shiftOpen} />

      {shiftOpen ? (
        <>
          <CashboxKpis kpis={data.kpis} />
          <div className="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
            <TransactionsCard data={data} />
            <ShiftDrawer
              shift={data.shift}
              onClose={() =>
                open('cash', { cash: { screen: 'close', onDone: () => setShiftOpen(false) } })
              }
            />
          </div>
        </>
      ) : (
        <Card>
          <EmptyState
            icon={Wallet}
            title="Смена закрыта"
            message="Откройте смену, чтобы принимать платежи и проводить операции."
            action={
              <button
                type="button"
                onClick={() =>
                  open('cash', { cash: { screen: 'openshift', onDone: () => setShiftOpen(true) } })
                }
                className="mt-1 inline-flex h-9 items-center rounded-full bg-fg px-4 text-[13px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
              >
                Открыть смену
              </button>
            }
          />
        </Card>
      )}
    </div>
  );
}
