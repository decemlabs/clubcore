import { useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Check, ChevronDown, Clock, Wallet } from '@/components/icons';
import type { TrainerDetail } from '@/features/trainers/detail';
import { Panel, PanelBody, PanelHead } from './shared';

export function PayoutsTab({ trainer: t }: { trainer: TrainerDetail }) {
  const [paid, setPaid] = useState(false);
  const p = t.payout;

  const pay = () => {
    setPaid(true);
    toast.success(p.paidToast);
  };

  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelHead
          title={p.title}
          action={
            <div className="relative">
              <select
                aria-label="Период расчёта"
                className="h-8 cursor-pointer appearance-none rounded-lg border-[0.5px] border-border-strong bg-surface pl-3 pr-8 text-xs font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {p.periods.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
              <ChevronDown
                className="pointer-events-none absolute right-2.5 top-1/2 size-3 -translate-y-1/2 text-fg-subtle"
                strokeWidth={2.4}
              />
            </div>
          }
        />
        <div className="grid md:grid-cols-[1.2fr_1fr]">
          <div className="border-b-[0.5px] border-border p-[18px] md:border-b-0 md:border-r-[0.5px]">
            {p.lines.map((l, i) => (
              <div
                key={i}
                className="flex items-start border-b-[0.5px] border-dashed border-border py-[9px] text-[13px] last:border-b-0"
              >
                <div className="text-fg-muted">
                  {l.label}
                  {l.sub ? <div className="mt-px text-[11.5px] text-fg-subtle">{l.sub}</div> : null}
                </div>
                <div
                  className={cn(
                    'ml-auto pl-3 font-semibold tabular-nums',
                    l.minus && 'text-danger',
                  )}
                >
                  {l.value}
                </div>
              </div>
            ))}
            <div className="mt-1.5 flex items-center border-t border-border pt-3.5">
              <div className="text-sm font-bold">{p.totalLabel}</div>
              <div className="ml-auto text-[20px] font-bold tabular-nums tracking-[-0.4px]">
                {p.totalValue}
              </div>
            </div>
          </div>

          <div className="flex flex-col bg-surface-2 p-[18px]">
            {paid ? (
              <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-primary-soft px-[11px] py-[5px] text-xs font-semibold text-primary-deep dark:text-primary">
                <Check className="size-3.5" strokeWidth={2.6} />
                Выплачено
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-warning-soft px-[11px] py-[5px] text-xs font-semibold text-warning-deep">
                <Clock className="size-3.5" />
                {p.statusLabel}
              </span>
            )}
            <div className="mt-3.5 text-[12.5px] leading-relaxed text-fg-muted [&_b]:font-semibold [&_b]:text-fg">
              Период: <b>{p.period}</b>
              <br />
              Выплата: <b>{p.payoutDate}</b>
              <br />
              Способ: <b>{p.method}</b>
            </div>
            <button
              type="button"
              disabled={paid}
              onClick={pay}
              className={cn(
                'mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-full text-[13.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                paid
                  ? 'cursor-default border-[0.5px] border-border bg-surface text-fg-muted opacity-60'
                  : 'bg-fg text-bg hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]',
              )}
            >
              {paid ? (
                p.paidButtonLabel
              ) : (
                <>
                  <Wallet className="size-[15px]" />
                  {p.payButtonLabel}
                </>
              )}
            </button>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHead title="История выплат" />
        <PanelBody>
          {t.payoutHistory.map((h) => (
            <div
              key={h.id}
              className="flex items-center gap-3 border-b-[0.5px] border-border py-3 last:border-b-0"
            >
              <span className="grid size-[34px] shrink-0 place-items-center rounded-[9px] bg-primary-soft text-primary-deep dark:text-primary">
                <Wallet className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold">{h.title}</div>
                <div className="mt-px text-[11.5px] text-fg-subtle">{h.sub}</div>
              </div>
              <div className="font-bold tabular-nums">{h.amount}</div>
            </div>
          ))}
        </PanelBody>
      </Panel>
    </div>
  );
}
