import { useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { formatInt } from '@/lib/format';
import { AdaptiveModal } from '@/components/modals/AdaptiveModal';
import {
  Callout,
  ChipGroup,
  Field,
  IconChip,
  ModalButton,
  ModalInput,
  ModalSelect,
} from '@/components/modals/fields';
import { Banknote, Reply, Check, TriangleAlert } from '@/components/icons';
import type { PayRow, RegRow } from '@/features/finance/types';
import { FinStatus } from './parts';

const f = (n: number) => formatInt(n);

function DRow({
  k,
  v,
  strong,
  border,
}: {
  k: string;
  v: ReactNode;
  strong?: boolean;
  border?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 py-2.5',
        border
          ? 'mt-1 border-t-[0.5px] border-border pt-3'
          : 'border-b border-dashed border-border last:border-b-0',
      )}
    >
      <span className="text-[12.5px] text-fg-subtle">{k}</span>
      <span
        className={cn(
          'tabular-nums',
          strong ? 'text-[18px] font-bold tracking-[-0.3px]' : 'text-[13px] font-semibold',
        )}
      >
        {v}
      </span>
    </div>
  );
}

/* ---------- Transaction detail + refund (shared overlay) ---------- */

export function TxModal({
  row,
  screen,
  onScreen,
  onClose,
}: {
  row: RegRow | null;
  screen: 'detail' | 'refund';
  onScreen: (s: 'detail' | 'refund') => void;
  onClose: () => void;
}) {
  // refund-screen local state
  const [mode, setMode] = useState('full');
  const [partial, setPartial] = useState('');

  if (!row) return null;
  const open = true;

  const commission = Math.round(row.amount * 0.02);
  const credited = row.amount - commission;
  const txnId = '#TXN-48201';
  const refundAmount = mode === 'full' ? row.amount : Number(partial) || Math.round(row.amount / 2);

  if (screen === 'refund') {
    return (
      <AdaptiveModal
        open={open}
        onOpenChange={onClose}
        icon={<IconChip tone="warn" icon={Reply} />}
        title="Возврат средств"
        description={`${txnId} · ${f(row.amount)} ₽`}
        footerActions={
          <>
            <ModalButton variant="ghost" onClick={onClose}>
              Отмена
            </ModalButton>
            <ModalButton
              variant="danger"
              onClick={() => {
                toast.success(`Возврат ${f(refundAmount)} ₽ оформлен`);
                onClose();
              }}
            >
              Вернуть {f(refundAmount)} ₽
            </ModalButton>
          </>
        }
      >
        <Field label="Сумма возврата">
          <ChipGroup
            value={mode}
            onChange={setMode}
            options={[
              { value: 'full', label: `Полный · ${f(row.amount)} ₽` },
              { value: 'partial', label: 'Частичный' },
            ]}
          />
        </Field>
        {mode === 'partial' ? (
          <Field label="Сумма">
            <ModalInput
              type="text"
              inputMode="numeric"
              value={partial}
              placeholder={String(Math.round(row.amount / 2))}
              onChange={(e) => setPartial(e.target.value)}
              suffix="₽"
            />
          </Field>
        ) : null}
        <Field label="Причина">
          <ModalSelect defaultValue="Клиент отказался от абонемента">
            <option>Клиент отказался от абонемента</option>
            <option>Ошибка при оплате</option>
            <option>Двойное списание</option>
            <option>Другое</option>
          </ModalSelect>
        </Field>
        <Callout tone="danger" icon={TriangleAlert}>
          Деньги вернутся на карту •• 4417 за <b>3–5 дней</b>. Абонемент станет неактивным.
        </Callout>
      </AdaptiveModal>
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onClose}
      icon={<IconChip tone="accent" icon={Banknote} />}
      title="Транзакция"
      description={txnId}
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => toast('Чек отправлен повторно')}>
            Чек
          </ModalButton>
          <ModalButton variant="ghost" onClick={() => onScreen('refund')}>
            Оформить возврат
          </ModalButton>
        </>
      }
    >
      <div className="text-[30px] font-bold tabular-nums tracking-[-0.6px]">
        {row.status === 'refund' ? '−' : ''}
        {f(row.amount)} ₽
      </div>
      <div className="mt-2">
        <FinStatus status={row.status} />
      </div>
      <div className="mt-3.5">
        <DRow k="Клиент" v={<span className="font-semibold">{row.name}</span>} />
        <DRow k="Назначение" v={<span className="font-semibold">{row.desc}</span>} />
        <DRow k="Способ" v={<span className="font-semibold">{row.method}</span>} />
        <DRow k="Комиссия эквайринга" v={`−${f(commission)} ₽ (2%)`} />
        <DRow k="Зачислено" v={`${f(credited)} ₽`} />
        <DRow k="Дата" v={`${row.date} 2026, ${row.time}`} />
      </div>
      <div className="mb-2 mt-4 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
        Журнал
      </div>
      <div className="flex flex-col gap-2.5">
        {[
          { t: 'Платёж подтверждён банком', tm: '14:12:08' },
          { t: 'Чек отправлен на email', tm: '14:12:10' },
        ].map((e) => (
          <div key={e.tm} className="flex items-center gap-2.5">
            <span className="grid size-4 shrink-0 place-items-center rounded-full bg-primary-soft text-primary-deep dark:text-primary">
              <Check className="size-2.5" strokeWidth={3} />
            </span>
            <span className="text-[12.5px]">{e.t}</span>
            <span className="ml-auto font-mono text-[11px] text-fg-subtle">{e.tm}</span>
          </div>
        ))}
      </div>
    </AdaptiveModal>
  );
}

/* ---------- Trainer payout ---------- */

export function PayoutModal({ row, onClose }: { row: PayRow | null; onClose: () => void }) {
  if (!row) return null;
  return (
    <AdaptiveModal
      open
      onOpenChange={onClose}
      icon={<IconChip tone="accent" icon={Banknote} />}
      title="Выплата тренеру"
      description={`${row.name} · апрель 2026`}
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={onClose}>
            Отмена
          </ModalButton>
          <ModalButton
            onClick={() => {
              toast.success(`Выплата ${f(row.payout)} ₽ проведена`);
              onClose();
            }}
          >
            Выплатить
          </ModalButton>
        </>
      }
    >
      <DRow k="Начислено за тренировки" v="152 250 ₽" />
      <DRow k="Бонус за заполняемость" v="7 650 ₽" />
      <DRow k="Удержан НДФЛ (6%)" v="−8 568 ₽" />
      <DRow k="Комиссия зала (30%)" v="−45 900 ₽" />
      <DRow k="К выплате" v={`${f(row.payout)} ₽`} strong border />
      <div className="mt-3.5">
        <Field label="Способ выплаты">
          <ModalSelect defaultValue="Карта •• 8842">
            <option>Карта •• 8842</option>
            <option>СБП по телефону</option>
            <option>Наличные из кассы</option>
          </ModalSelect>
        </Field>
      </div>
    </AdaptiveModal>
  );
}
