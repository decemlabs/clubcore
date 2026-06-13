import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { CreditCard, ShoppingBag, Undo2, User } from '@/components/icons';
import type { PaymentIcon, PaymentItem, PaymentsTabData } from '@/features/clients/detail';
import { Card, CardHead, CardLink } from './shared';

const PAY_ICON: Record<PaymentIcon, LucideIcon> = {
  card: CreditCard,
  trainer: User,
  shop: ShoppingBag,
  refund: Undo2,
};

function PaymentRow({ item }: { item: PaymentItem }) {
  const Icon = PAY_ICON[item.icon];
  return (
    <div className="grid grid-cols-[32px_1fr_auto] items-center gap-3.5 border-t-[0.5px] border-border px-4 py-3 first:border-t-0 sm:px-5">
      <span
        className={cn(
          'grid size-8 place-items-center rounded-[10px]',
          item.refund ? 'bg-danger-soft text-danger' : 'bg-surface-3 text-fg',
        )}
      >
        <Icon className="size-[14px]" strokeWidth={2.2} />
      </span>
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">{item.title}</div>
        <div className="mt-0.5 truncate text-[11.5px] tabular-nums text-fg-subtle">{item.meta}</div>
      </div>
      <div
        className={cn(
          'whitespace-nowrap text-sm font-bold tabular-nums tracking-[-0.2px]',
          item.refund && 'text-danger',
        )}
      >
        {item.amount}
      </div>
    </div>
  );
}

export function PaymentsTab({ data }: { data: PaymentsTabData }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 @[560px]:grid-cols-4 @[560px]:gap-4">
        {data.summary.map((cell) => (
          <div
            key={cell.label}
            className="rounded-lg border-[0.5px] border-border bg-surface px-[18px] py-3.5 shadow-1"
          >
            <div className="text-[11.5px] font-semibold uppercase tracking-[0.5px] text-fg-subtle">
              {cell.label}
            </div>
            <div className="mt-2 text-[19px] font-bold tabular-nums tracking-[-0.4px]">
              {cell.value}
            </div>
            <div className="mt-1 text-[11.5px] text-fg-muted">{cell.foot}</div>
          </div>
        ))}
      </div>

      <Card>
        <CardHead title={data.title} sub={data.sub} action={<CardLink>Экспорт CSV</CardLink>} />
        <div className="border-t-[0.5px] border-border">
          {data.items.map((item) => (
            <PaymentRow key={item.id} item={item} />
          ))}
        </div>
        <button
          type="button"
          className="w-full border-t-[0.5px] border-border py-3.5 text-[12.5px] font-semibold text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
        >
          {data.moreLabel}
        </button>
      </Card>
    </div>
  );
}
