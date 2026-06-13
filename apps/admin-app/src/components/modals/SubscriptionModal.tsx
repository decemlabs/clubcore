import { useEffect, useState, type ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { formatInt } from '@/lib/format';
import {
  Check,
  CircleX,
  CreditCard,
  History,
  Info,
  RefreshCw,
  Snowflake,
  SquarePen,
  Sun,
  TriangleAlert,
  Wallet,
} from '@/components/icons';
import type { SubscriptionScreen } from './modals-context';
import { AdaptiveModal } from './AdaptiveModal';
import {
  Callout,
  ChipGroup,
  Field,
  FieldRow,
  IconChip,
  ModalButton,
  ModalInput,
  ModalSelect,
  PlanCards,
  Section,
  StatRow,
  ToggleRow,
} from './fields';

const rub = (n: number) => `${formatInt(n)} ₽`;

function SumBox({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3.5 rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 py-1.5">
      {children}
    </div>
  );
}

function SumLine({
  k,
  sub,
  v,
  minus,
  total,
}: {
  k: ReactNode;
  sub?: string;
  v: ReactNode;
  minus?: boolean;
  total?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex items-center py-1.5 text-[13px]',
        total && 'mt-1 border-t border-border pt-3',
      )}
    >
      <div className={cn('text-fg-muted', total && 'font-bold text-fg')}>
        {k}
        {sub ? <div className="mt-px text-[11.5px] text-fg-subtle">{sub}</div> : null}
      </div>
      <div
        className={cn(
          'ml-auto font-semibold tabular-nums',
          minus && 'text-primary-deep dark:text-primary',
          total && 'text-lg font-bold tracking-[-0.3px]',
        )}
      >
        {v}
      </div>
    </div>
  );
}

type ScreenProps = { open: boolean; onOpenChange: (open: boolean) => void };

const CANCEL_BTN = (onOpenChange: (o: boolean) => void) => (
  <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
    Отмена
  </ModalButton>
);

/* ───────────────────────── Оформить ───────────────────────── */

const CREATE_TARIFFS = [
  { value: 'm1', name: 'Месяц', price: '3 500 ₽', sub: 'безлимит' },
  { value: 'm3', name: '3 месяца', price: '9 000 ₽', sub: '3 000 ₽/мес', tag: 'Хит' },
  { value: 'm12', name: 'Год', price: '24 000 ₽', sub: '2 000 ₽/мес' },
];
const CREATE_PRICE: Record<string, number> = { m1: 3500, m3: 9000, m12: 24000 };
const CREATE_NAME: Record<string, string> = { m1: 'Месяц', m3: '3 месяца', m12: 'Год' };

const CREATE_PLAN_DEFAULT = 'm3';

function CreateScreen({ open, onOpenChange }: ScreenProps) {
  const [plan, setPlan] = useState(CREATE_PLAN_DEFAULT);

  useEffect(() => {
    if (open) {
      setPlan(CREATE_PLAN_DEFAULT);
    }
  }, [open]);

  const base = CREATE_PRICE[plan] ?? 0;
  const total = Math.round(base * 0.95);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      size="wide"
      icon={<IconChip icon={CreditCard} />}
      title="Оформить абонемент"
      description="Анна Петрова · выберите тариф и примите оплату"
      footerActions={
        <>
          {CANCEL_BTN(onOpenChange)}
          <ModalButton
            onClick={() => {
              toast.success('Абонемент оформлен', { description: `К оплате ${rub(total)}` });
              onOpenChange(false);
            }}
          >
            Создать и принять оплату
          </ModalButton>
        </>
      }
    >
      <Section>Тариф</Section>
      <PlanCards options={CREATE_TARIFFS} value={plan} onChange={setPlan} />
      <div className="mt-3.5">
        <FieldRow>
          <Field label="Дата старта">
            <ModalInput defaultValue="30.04.2026" />
          </Field>
          <Field label="Способ оплаты">
            <ModalSelect defaultValue="Карта · терминал">
              <option>Карта · терминал</option>
              <option>Наличные</option>
              <option>Перевод (СБП)</option>
              <option>Онлайн-ссылка</option>
            </ModalSelect>
          </Field>
        </FieldRow>
      </div>
      <Field label="Промокод">
        <ModalInput placeholder="Например, STUDENT20" />
      </Field>
      <SumBox>
        <SumLine k={`Тариф «${CREATE_NAME[plan]}»`} v={rub(base)} />
        <SumLine k="Скидка лояльности" sub="постоянный клиент" v={`−${rub(base - total)}`} minus />
        <SumLine k="К оплате" v={rub(total)} total />
      </SumBox>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Редактировать ───────────────────────── */

function EditScreen({ open, onOpenChange }: ScreenProps) {
  const [autorenew, setAutorenew] = useState(true);

  useEffect(() => {
    if (open) {
      setAutorenew(true);
    }
  }, [open]);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={SquarePen} />}
      title="Редактировать абонемент"
      description="Анна Петрова · «12 месяцев» · #SUB-4471"
      footerInfo={
        <button
          type="button"
          aria-label="Удалить абонемент"
          onClick={() => toast('Откроется удаление абонемента')}
          className="grid size-9 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-danger hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <CircleX className="size-[15px]" />
        </button>
      }
      footerActions={
        <>
          {CANCEL_BTN(onOpenChange)}
          <ModalButton
            onClick={() => {
              toast.success('Изменения сохранены');
              onOpenChange(false);
            }}
          >
            <Check className="size-3.5" strokeWidth={2.6} />
            Сохранить
          </ModalButton>
        </>
      }
    >
      <Field label="Тариф">
        <ModalSelect defaultValue="«12 месяцев» · безлимит">
          <option>«12 месяцев» · безлимит</option>
          <option>«6 месяцев» · безлимит</option>
          <option>«3 месяца» · 12 визитов</option>
        </ModalSelect>
      </Field>
      <FieldRow>
        <Field label="Действует с">
          <ModalInput defaultValue="14.02.2026" />
        </Field>
        <Field label="Действует до">
          <ModalInput defaultValue="14.02.2027" />
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Лимит заморозки, дней">
          <ModalInput defaultValue="30" inputMode="numeric" />
        </Field>
        <Field label="Гостевые визиты">
          <ModalInput defaultValue="2" inputMode="numeric" />
        </Field>
      </FieldRow>
      <ToggleRow
        title="Автопродление"
        sub="Списывать с карты за 3 дня до окончания"
        checked={autorenew}
        onChange={setAutorenew}
      />
      <div className="mt-3.5">
        <Callout tone="warn" icon={TriangleAlert}>
          Изменение тарифа задним числом пересчитает остаток. Клиент получит уведомление.
        </Callout>
      </div>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Продлить ───────────────────────── */

const RENEW_OPTS = [
  { value: '1', label: '1 месяц', price: 3500, end: '14 мар 2027' },
  { value: '3', label: '3 месяца', price: 9000, end: '14 мая 2027' },
  { value: '6', label: '6 месяцев', price: 16000, end: '14 авг 2027' },
  { value: '12', label: 'Год', price: 24000, end: '14 фев 2028' },
];

const RENEW_SEL_DEFAULT = '3';

function RenewScreen({ open, onOpenChange }: ScreenProps) {
  const [sel, setSel] = useState(RENEW_SEL_DEFAULT);
  const [keepPrice, setKeepPrice] = useState(true);

  useEffect(() => {
    if (open) {
      setSel(RENEW_SEL_DEFAULT);
      setKeepPrice(true);
    }
  }, [open]);

  const opt = RENEW_OPTS.find((o) => o.value === sel);
  if (!opt) return null;

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={RefreshCw} />}
      title="Продлить абонемент"
      description="Сейчас действует до 14 фев 2027"
      footerActions={
        <>
          {CANCEL_BTN(onOpenChange)}
          <ModalButton
            onClick={() => {
              toast.success('Абонемент продлён', { description: `до ${opt.end}` });
              onOpenChange(false);
            }}
          >
            Продлить · {rub(opt.price)}
          </ModalButton>
        </>
      }
    >
      <Section>Продлить на</Section>
      <ChipGroup
        options={RENEW_OPTS.map((o) => ({ value: o.value, label: o.label }))}
        value={sel}
        onChange={setSel}
      />
      <StatRow label="Новая дата окончания" value={opt.end} accent />
      <ToggleRow
        title="Сохранить цену тарифа"
        sub="Зафиксировать текущую цену на продление"
        checked={keepPrice}
        onChange={setKeepPrice}
      />
      <SumBox>
        <SumLine k={`Продление · ${opt.label}`} v={rub(opt.price)} />
        <SumLine k="К оплате" v={rub(opt.price)} total />
      </SumBox>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Заморозить ───────────────────────── */

const FREEZE_OPTS = [
  { value: '7', label: '7 дней', end: '21 фев 2027' },
  { value: '14', label: '14 дней', end: '28 фев 2027' },
  { value: '30', label: '30 дней', end: '16 мар 2027' },
];

const FREEZE_SEL_DEFAULT = '14';

function FreezeScreen({ open, onOpenChange }: ScreenProps) {
  const [sel, setSel] = useState(FREEZE_SEL_DEFAULT);

  useEffect(() => {
    if (open) {
      setSel(FREEZE_SEL_DEFAULT);
    }
  }, [open]);

  const opt = FREEZE_OPTS.find((o) => o.value === sel);
  if (!opt) return null;

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="indigo" icon={Snowflake} />}
      title="Заморозить абонемент"
      description="Срок продлится на дни заморозки"
      footerActions={
        <>
          {CANCEL_BTN(onOpenChange)}
          <ModalButton
            onClick={() => {
              toast.success('Абонемент заморожен', { description: `${opt.label} · до ${opt.end}` });
              onOpenChange(false);
            }}
          >
            Заморозить на {opt.label}
          </ModalButton>
        </>
      }
    >
      <Section>Срок заморозки</Section>
      <ChipGroup
        options={FREEZE_OPTS.map((o) => ({ value: o.value, label: o.label }))}
        value={sel}
        onChange={setSel}
      />
      <StatRow label="Новая дата окончания" value={opt.end} accent />
      <div className="mt-3.5">
        <Field label="Причина (необязательно)">
          <ModalSelect defaultValue="Отпуск">
            <option>Отпуск</option>
            <option>Болезнь / травма</option>
            <option>Командировка</option>
            <option>Другое</option>
          </ModalSelect>
        </Field>
      </div>
      <Callout tone="accent" icon={Info}>
        Доступно <b>21 из 30 дней</b> в этом году. Разморозить можно досрочно в любой момент.
      </Callout>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Разморозить ───────────────────────── */

function UnfreezeScreen({ open, onOpenChange }: ScreenProps) {
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={Sun} />}
      title="Разморозить абонемент"
      description="Анна Петрова · «12 месяцев»"
      footerActions={
        <>
          {CANCEL_BTN(onOpenChange)}
          <ModalButton
            onClick={() => {
              toast.success('Абонемент разморожен');
              onOpenChange(false);
            }}
          >
            Разморозить сейчас
          </ModalButton>
        </>
      }
    >
      <div className="mt-1 flex items-center gap-3.5 rounded-xl bg-indigo-500/15 px-3.5 py-3.5">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-indigo-500/20 text-indigo-600 dark:text-indigo-300">
          <Snowflake className="size-[18px]" />
        </span>
        <div>
          <div className="text-[13.5px] font-semibold text-indigo-600 dark:text-indigo-300">
            Заморожен до 28 фев 2027
          </div>
          <div className="mt-0.5 text-xs text-indigo-600/80 dark:text-indigo-300/80">
            Прошло 6 из 14 дней · осталось 8 дней
          </div>
        </div>
      </div>
      <StatRow label="Вернётся в лимит заморозки" value="+8 дней" accent />
      <StatRow label="Новая дата окончания" value="22 фев 2027" />
      <div className="mt-3.5">
        <Callout icon={Info}>
          Абонемент станет активным сегодня. Неиспользованные <b>8 дней</b> заморозки вернутся
          клиенту.
        </Callout>
      </div>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Отменить ───────────────────────── */

const REFUND_OPTS = [
  { value: 'none', label: 'Без возврата' },
  { value: 'part', label: 'Частичный' },
  { value: 'full', label: 'Полный' },
];

const REFUND_DEFAULT = 'none';

function CancelScreen({ open, onOpenChange }: ScreenProps) {
  const [refund, setRefund] = useState(REFUND_DEFAULT);

  useEffect(() => {
    if (open) {
      setRefund(REFUND_DEFAULT);
    }
  }, [open]);

  const refundSum = refund === 'full' ? 15200 : refund === 'part' ? 9000 : 0;

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="danger" icon={CircleX} />}
      title="Отменить абонемент?"
      description="Анна Петрова · «12 месяцев» · осталось 231 день"
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Не отменять
          </ModalButton>
          <ModalButton
            variant="danger"
            onClick={() => {
              toast.success(
                'Абонемент отменён',
                refundSum ? { description: `Возврат ${rub(refundSum)}` } : undefined,
              );
              onOpenChange(false);
            }}
          >
            Отменить абонемент
          </ModalButton>
        </>
      }
    >
      <Section>Возврат средств</Section>
      <ChipGroup options={REFUND_OPTS} value={refund} onChange={setRefund} />
      {refundSum > 0 ? <StatRow label="Сумма к возврату" value={rub(refundSum)} /> : null}
      <div className="mt-3.5">
        <Field label="Причина отмены">
          <ModalSelect defaultValue="Клиент отказался">
            <option>Клиент отказался</option>
            <option>Переезд</option>
            <option>Недоволен качеством</option>
            <option>Перевод в другой филиал</option>
            <option>Другое</option>
          </ModalSelect>
        </Field>
      </div>
      <Callout tone="danger" icon={TriangleAlert}>
        Абонемент станет неактивным сразу. Будущие записи в расписании <b>отменятся</b>. Действие
        необратимо.
      </Callout>
    </AdaptiveModal>
  );
}

/* ───────────────────────── История ───────────────────────── */

const HISTORY: {
  id: string;
  icon: LucideIcon;
  tone: 'accent' | 'warn' | 'indigo';
  title: ReactNode;
  meta: string;
  amount?: string;
}[] = [
  {
    id: '1',
    icon: Snowflake,
    tone: 'indigo',
    title: (
      <>
        Заморожен на <b className="font-bold text-fg">14 дней</b> · причина: отпуск
      </>
    ),
    meta: '22 апр 2026 · Маша К.',
  },
  {
    id: '2',
    icon: Wallet,
    tone: 'accent',
    title: (
      <>
        Продлён на <b className="font-bold text-fg">12 месяцев</b>
      </>
    ),
    meta: '14 фев 2026 · карта •• 4417',
    amount: '24 000 ₽',
  },
  {
    id: '3',
    icon: Snowflake,
    tone: 'warn',
    title: (
      <>
        Разморожен досрочно · вернулось <b className="font-bold text-fg">5 дней</b>
      </>
    ),
    meta: '03 дек 2025 · Дмитрий С.',
  },
  {
    id: '4',
    icon: Check,
    tone: 'accent',
    title: <>Абонемент оформлен · «12 месяцев»</>,
    meta: '14 фев 2025 · карта •• 4417',
    amount: '24 000 ₽',
  },
];

const TL_DOT: Record<'accent' | 'warn' | 'indigo', string> = {
  accent: 'border-transparent bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'border-transparent bg-warning-soft text-warning-deep',
  indigo: 'border-transparent bg-indigo-500/15 text-indigo-600 dark:text-indigo-300',
};

function HistoryScreen({ open, onOpenChange }: ScreenProps) {
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={History} />}
      title="История абонемента"
      description="Анна Петрова · #SUB-4471"
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => toast('Выгрузка в PDF')}>
            Экспорт
          </ModalButton>
          <ModalButton onClick={() => onOpenChange(false)}>Закрыть</ModalButton>
        </>
      }
    >
      <div className="relative mt-2 pl-[30px] before:absolute before:bottom-1 before:left-[9px] before:top-1 before:w-[1.5px] before:bg-border before:content-['']">
        {HISTORY.map((it) => {
          const Icon = it.icon;
          return (
            <div key={it.id} className="relative pb-[18px] last:pb-0.5">
              <span
                className={cn(
                  'absolute -left-[30px] top-0 grid size-5 place-items-center rounded-full border-[1.5px]',
                  TL_DOT[it.tone],
                )}
              >
                <Icon className="size-[11px]" strokeWidth={2.2} />
              </span>
              <div className="text-[13px] font-semibold">
                {it.amount ? (
                  <span className="float-right font-bold tabular-nums">{it.amount}</span>
                ) : null}
                {it.title}
              </div>
              <div className="mt-0.5 text-[11.5px] tabular-nums text-fg-subtle">{it.meta}</div>
            </div>
          );
        })}
      </div>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Диспетчер ───────────────────────── */

export function SubscriptionModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: { screen?: SubscriptionScreen };
}) {
  const screen = payload?.screen ?? 'edit';
  const props = { open, onOpenChange };

  switch (screen) {
    case 'create':
      return <CreateScreen {...props} />;
    case 'renew':
      return <RenewScreen {...props} />;
    case 'freeze':
      return <FreezeScreen {...props} />;
    case 'unfreeze':
      return <UnfreezeScreen {...props} />;
    case 'cancel':
      return <CancelScreen {...props} />;
    case 'history':
      return <HistoryScreen {...props} />;
    case 'edit':
    default:
      return <EditScreen {...props} />;
  }
}
