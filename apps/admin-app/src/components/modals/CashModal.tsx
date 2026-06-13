import { useEffect, useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Clock,
  FileText,
  Info,
  Power,
  TriangleAlert,
} from '@/components/icons';
import type { CashScreen } from './modals-context';
import { AdaptiveModal } from './AdaptiveModal';
import { Callout, Field, IconChip, ModalButton, ModalSelect } from './fields';

const EXPECTED = 42800;
const num = (v: string) => parseInt(v.replace(/\D/g, ''), 10) || 0;
const rub = (n: number) =>
  `${n < 0 ? '−' : ''}${Math.abs(n).toLocaleString('ru-RU').replace(/,/g, ' ')} ₽`;

type ScreenProps = { open: boolean; onOpenChange: (open: boolean) => void };

/** Крупное поле ввода суммы с суффиксом ₽. */
function MoneyInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="relative">
      <input
        inputMode="numeric"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-14 w-full rounded-xl border-[0.5px] border-border-strong bg-surface-2 pl-3.5 pr-9 text-[24px] font-bold tabular-nums tracking-[-0.5px] text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
      />
      <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[15px] text-fg-subtle">
        ₽
      </span>
    </div>
  );
}

function SumRows({ children }: { children: ReactNode }) {
  return (
    <div className="mt-2 rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-0.5">
      {children}
    </div>
  );
}

function SumRow({
  k,
  v,
  total,
  diff,
  bad,
}: {
  k: ReactNode;
  v: ReactNode;
  total?: boolean;
  diff?: boolean;
  bad?: boolean;
}) {
  return (
    <div className="flex items-center border-b-[0.5px] border-dashed border-border py-2 text-[13px] last:border-b-0">
      <span className={cn(total ? 'font-bold text-fg' : 'text-fg-muted')}>{k}</span>
      <span
        className={cn(
          'ml-auto font-[650] tabular-nums',
          total && 'text-[17px]',
          diff && (bad ? 'text-danger' : 'text-primary-deep dark:text-primary'),
        )}
      >
        {v}
      </span>
    </div>
  );
}

const footer = (onOpenChange: (o: boolean) => void, action: ReactNode, cancelLabel = 'Отмена') => (
  <>
    <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
      {cancelLabel}
    </ModalButton>
    {action}
  </>
);

const IN_AMOUNT_DEFAULT = '5 000';
const OUT_AMOUNT_DEFAULT = '12 000';
const RECON_FACT_DEFAULT = '42 800';
const OPENSHIFT_AMOUNT_DEFAULT = '5 000';

/* ── Приход ── */
function InScreen({ open, onOpenChange }: ScreenProps) {
  const [amount, setAmount] = useState(IN_AMOUNT_DEFAULT);

  useEffect(() => {
    if (open) {
      setAmount(IN_AMOUNT_DEFAULT);
    }
  }, [open]);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={ArrowUp} />}
      title="Приход в кассу"
      description="Внесение наличных"
      footerActions={footer(
        onOpenChange,
        <ModalButton
          onClick={() => {
            toast.success(
              `Приход ${num(amount).toLocaleString('ru-RU').replace(/,/g, ' ')} ₽ проведён`,
            );
            onOpenChange(false);
          }}
        >
          Провести приход
        </ModalButton>,
      )}
    >
      <Field label="Сумма">
        <MoneyInput value={amount} onChange={setAmount} />
      </Field>
      <Field label="Категория">
        <ModalSelect defaultValue="Внесение разменных">
          <option>Внесение разменных</option>
          <option>Возврат подотчётных</option>
          <option>Прочий приход</option>
        </ModalSelect>
      </Field>
      <Field label="Комментарий">
        <input
          placeholder="Необязательно"
          className="h-[42px] w-full rounded-xl border-[0.5px] border-border-strong bg-surface-2 px-3.5 text-sm text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
        />
      </Field>
    </AdaptiveModal>
  );
}

/* ── Расход ── */
function OutScreen({ open, onOpenChange }: ScreenProps) {
  const [amount, setAmount] = useState(OUT_AMOUNT_DEFAULT);

  useEffect(() => {
    if (open) {
      setAmount(OUT_AMOUNT_DEFAULT);
    }
  }, [open]);

  const left = EXPECTED - num(amount);
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="danger" icon={ArrowDown} />}
      title="Расход из кассы"
      description="Выдача наличных"
      footerActions={footer(
        onOpenChange,
        <ModalButton
          variant="danger"
          onClick={() => {
            toast.success(
              `Расход ${num(amount).toLocaleString('ru-RU').replace(/,/g, ' ')} ₽ проведён`,
            );
            onOpenChange(false);
          }}
        >
          Провести расход
        </ModalButton>,
      )}
    >
      <Field label="Сумма">
        <MoneyInput value={amount} onChange={setAmount} />
      </Field>
      <Field label="Категория">
        <ModalSelect defaultValue="Инкассация">
          <option>Инкассация</option>
          <option>Хозяйственные нужды</option>
          <option>Зарплата / аванс</option>
          <option>Возврат клиенту</option>
        </ModalSelect>
      </Field>
      <Field label="Комментарий">
        <input
          placeholder="Основание расхода"
          className="h-[42px] w-full rounded-xl border-[0.5px] border-border-strong bg-surface-2 px-3.5 text-sm text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
        />
      </Field>
      <Callout tone="warn" icon={TriangleAlert}>
        В кассе сейчас <b>{rub(EXPECTED)}</b>. После расхода останется <b>{rub(left)}</b>.
      </Callout>
    </AdaptiveModal>
  );
}

/* ── Сверка ── */
function ReconScreen({ open, onOpenChange }: ScreenProps) {
  const [fact, setFact] = useState(RECON_FACT_DEFAULT);

  useEffect(() => {
    if (open) {
      setFact(RECON_FACT_DEFAULT);
    }
  }, [open]);

  const diff = num(fact) - EXPECTED;
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={CheckCircle2} />}
      title="Сверка кассы"
      description="Пересчёт наличных"
      footerActions={footer(
        onOpenChange,
        <ModalButton
          onClick={() => {
            toast.success('Сверка сохранена');
            onOpenChange(false);
          }}
        >
          Сохранить сверку
        </ModalButton>,
      )}
    >
      <Field label="Фактически в кассе">
        <MoneyInput value={fact} onChange={setFact} />
      </Field>
      <SumRows>
        <SumRow k="Ожидается по системе" v={rub(EXPECTED)} />
        <SumRow k="Внесено фактически" v={rub(num(fact))} />
        <SumRow k="Расхождение" v={`${diff > 0 ? '+' : ''}${rub(diff)}`} diff bad={diff !== 0} />
      </SumRows>
    </AdaptiveModal>
  );
}

/* ── Z-отчёт ── */
function ZReportScreen({ open, onOpenChange }: ScreenProps) {
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="indigo" icon={FileText} />}
      title="Z-отчёт · смена №142"
      description="Тверская · 30 апр 2026"
      footerActions={footer(
        onOpenChange,
        <ModalButton
          onClick={() => {
            toast.success('Z-отчёт сформирован и распечатан');
            onOpenChange(false);
          }}
        >
          Печать Z-отчёта
        </ModalButton>,
        'Закрыть',
      )}
    >
      <SumRows>
        <SumRow k="Продажи (23 чека)" v="199 000 ₽" />
        <SumRow k="— наличными" v="42 800 ₽" />
        <SumRow k="— картой / СБП" v="156 200 ₽" />
        <SumRow k="Возвраты (1)" v="−9 000 ₽" />
        <SumRow k="Приход / расход наличных" v="+5 000 / −12 000 ₽" />
        <SumRow k="Итого выручка" v="190 000 ₽" total />
      </SumRows>
      <div className="mt-3.5">
        <Callout icon={Info}>
          Z-отчёт фиксирует выручку и обнуляет смену в фискальном регистраторе.
        </Callout>
      </div>
    </AdaptiveModal>
  );
}

/* ── Закрытие смены ── */
function CloseScreen({ open, onOpenChange, onDone }: ScreenProps & { onDone?: () => void }) {
  const [fact, setFact] = useState(RECON_FACT_DEFAULT);

  useEffect(() => {
    if (open) {
      setFact(RECON_FACT_DEFAULT);
    }
  }, [open]);

  const diff = num(fact) - EXPECTED;
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="danger" icon={Power} />}
      title="Закрыть смену №142?"
      description="Будет сформирован Z-отчёт"
      footerActions={footer(
        onOpenChange,
        <ModalButton
          variant="danger"
          onClick={() => {
            onDone?.();
            toast.success('Смена №142 закрыта · Z-отчёт сформирован');
            onOpenChange(false);
          }}
        >
          Закрыть смену
        </ModalButton>,
      )}
    >
      <Field label="Фактический остаток наличных">
        <MoneyInput value={fact} onChange={setFact} />
      </Field>
      <SumRows>
        <SumRow k="Ожидается в кассе" v={rub(EXPECTED)} />
        <SumRow k="Расхождение" v={`${diff > 0 ? '+' : ''}${rub(diff)}`} diff bad={diff !== 0} />
        <SumRow k="Выручка за смену" v="190 000 ₽" total />
      </SumRows>
      <Callout tone="warn" icon={TriangleAlert}>
        После закрытия смену нельзя изменить. Новые операции — только в новой смене.
      </Callout>
    </AdaptiveModal>
  );
}

/* ── Открытие смены ── */
function OpenShiftScreen({ open, onOpenChange, onDone }: ScreenProps & { onDone?: () => void }) {
  const [amount, setAmount] = useState(OPENSHIFT_AMOUNT_DEFAULT);

  useEffect(() => {
    if (open) {
      setAmount(OPENSHIFT_AMOUNT_DEFAULT);
    }
  }, [open]);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={Clock} />}
      title="Открыть смену"
      description="Касса · Тверская · смена №143"
      footerActions={footer(
        onOpenChange,
        <ModalButton
          onClick={() => {
            onDone?.();
            toast.success('Смена №143 открыта');
            onOpenChange(false);
          }}
        >
          Открыть смену
        </ModalButton>,
      )}
    >
      <Field label="Разменные на начало">
        <MoneyInput value={amount} onChange={setAmount} />
      </Field>
      <Field label="Кассир">
        <ModalSelect defaultValue="Маша Костина">
          <option>Маша Костина</option>
          <option>Дарья Сомова</option>
          <option>Иван Петров</option>
        </ModalSelect>
      </Field>
      <Callout icon={Info}>Предыдущая смена №142 закрыта в 21:30. Касса готова к работе.</Callout>
    </AdaptiveModal>
  );
}

export function CashModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: { screen?: CashScreen; onDone?: () => void };
}) {
  const screen = payload?.screen ?? 'in';
  const props = { open, onOpenChange };

  switch (screen) {
    case 'out':
      return <OutScreen {...props} />;
    case 'recon':
      return <ReconScreen {...props} />;
    case 'zreport':
      return <ZReportScreen {...props} />;
    case 'close':
      return <CloseScreen {...props} onDone={payload?.onDone} />;
    case 'openshift':
      return <OpenShiftScreen {...props} onDone={payload?.onDone} />;
    case 'in':
    default:
      return <InScreen {...props} />;
  }
}
