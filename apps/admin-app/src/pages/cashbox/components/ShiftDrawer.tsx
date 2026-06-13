import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { useModals } from '@/components/modals/modals-context';
import { formatInt } from '@/lib/format';
import {
  ArrowDown,
  ArrowRightLeft,
  ArrowUp,
  CheckCircle2,
  CreditCard,
  FileText,
  LogOut,
  Undo2,
  Wallet,
} from '@/components/icons';
import type { PayMethodRow, Shift, TxMethod } from '@/features/cashbox/types';

const METHOD_ICON: Record<TxMethod, LucideIcon> = {
  card: CreditCard,
  cash: Wallet,
  transfer: ArrowRightLeft,
  refund: Undo2,
};

function PayRow({ p }: { p: PayMethodRow }) {
  const Icon = METHOD_ICON[p.method];
  return (
    <div className="flex items-center gap-3 rounded-lg px-1 py-1.5">
      <span
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-lg',
          p.danger ? 'bg-danger/20 text-[#fca5a5]' : 'bg-white/10 text-white',
        )}
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] font-semibold">{p.label}</div>
        <div className="text-[11px] text-white/50">{p.sub}</div>
      </div>
      <div className="whitespace-nowrap text-right">
        <div className={cn('text-[13px] font-bold tabular-nums', p.danger && 'text-[#fca5a5]')}>
          {p.amount < 0 ? '−' : ''}
          {formatInt(Math.abs(p.amount))} ₽
        </div>
        <div className="text-[11px] tabular-nums text-white/45">{p.pct}</div>
      </div>
    </div>
  );
}

function DarkButton({
  icon: Icon,
  children,
  onClick,
}: {
  icon: LucideIcon;
  children: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/10 py-2.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-white/[0.16] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
    >
      <Icon className="size-4" />
      {children}
    </button>
  );
}

/** Тёмная карточка-«ящик» открытой смены: касса, разбивка по способам, действия. */
export function ShiftDrawer({ shift, onClose }: { shift: Shift; onClose: () => void }) {
  const { open } = useModals();
  return (
    <div
      className="relative overflow-hidden rounded-lg p-5 text-white shadow-2"
      style={{ background: 'linear-gradient(160deg,#1c1917,#2a2826)' }}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 size-44 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(45,212,164,0.22), transparent 70%)' }}
      />

      <div className="relative flex items-center gap-3">
        <Initials
          initials={shift.cashierInitials}
          color="linear-gradient(135deg,#f59e0b,#f97316)"
          className="size-[38px] text-[13px]"
        />
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-semibold">{shift.cashier}</div>
          <div className="text-[11.5px] text-white/55">
            с {shift.openedAt} · {shift.duration}
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/20 px-2 py-1 text-[10.5px] font-bold uppercase tracking-[0.3px] text-primary">
          <span className="size-1.5 animate-pulse rounded-full bg-primary" />в работе
        </span>
      </div>

      <div className="relative mt-5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.5px] text-white/50">
          В кассе
        </div>
        <div className="mt-1 text-[44px] font-bold leading-none tabular-nums">
          {formatInt(shift.drawerTotal)}
          <span className="ml-1.5 text-[20px] font-semibold text-white/50">₽</span>
        </div>
        <div className="mt-2 text-[11.5px] text-white/55">
          начало смены:{' '}
          <b className="font-semibold text-white/85">{formatInt(shift.startCash)} ₽</b> · ожидаемый
          остаток наличных:{' '}
          <b className="font-semibold text-white/85">{formatInt(shift.expectedCash)} ₽</b>
        </div>
      </div>

      <div className="relative mt-4 flex flex-col">
        {shift.pay.map((p) => (
          <PayRow key={p.method} p={p} />
        ))}
      </div>

      <div className="relative mt-4 grid grid-cols-2 gap-2">
        <DarkButton icon={ArrowDown} onClick={() => open('cash', { cash: { screen: 'in' } })}>
          Внести
        </DarkButton>
        <DarkButton icon={ArrowUp} onClick={() => open('cash', { cash: { screen: 'out' } })}>
          Изъять
        </DarkButton>
        <DarkButton icon={CheckCircle2} onClick={() => open('cash', { cash: { screen: 'recon' } })}>
          Сверка
        </DarkButton>
        <DarkButton icon={FileText} onClick={() => open('cash', { cash: { screen: 'zreport' } })}>
          Z-отчёт
        </DarkButton>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="relative mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-danger/15 py-2.5 text-[13px] font-semibold text-[#fca5a5] transition-colors hover:bg-danger/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/50"
      >
        <LogOut className="size-4" />
        Закрыть смену и отправить Z-отчёт
      </button>
    </div>
  );
}
