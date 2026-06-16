import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { formatInt } from '@/lib/format';
import { Search } from '@/components/icons';
import { AdaptiveModal } from './AdaptiveModal';
import {
  ChipGroup,
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  ModalSelect,
  PlanCards,
  ResultItem,
  ResultList,
  Section,
} from './fields';
import { EXTEND_PLANS, EXTEND_SUGGESTIONS, PAYMENT_METHODS, PLAN_PRICE } from './options';

export interface ExtendPayload {
  clientName?: string;
}

export function ExtendModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: ExtendPayload;
}) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(0);
  const [plan, setPlan] = useState('month');
  const [discount, setDiscount] = useState(10);
  const [method, setMethod] = useState('card');

  // Предвыбор клиента при каждом открытии (модалка остаётся смонтированной).
  useEffect(() => {
    if (!open || !payload?.clientName) return;
    const i = EXTEND_SUGGESTIONS.findIndex((s) => s.name === payload.clientName);
    if (i >= 0) setSelected(i);
  }, [open, payload?.clientName]);

  const { total, saved } = useMemo(() => {
    const base = PLAN_PRICE[plan] ?? 0;
    const d = Math.min(50, Math.max(0, Number.isFinite(discount) ? discount : 0));
    const saved = Math.round((base * d) / 100);
    return { total: base - saved, saved };
  }, [plan, discount]);

  const visible = EXTEND_SUGGESTIONS.filter(
    (s) => !search || s.name.toLowerCase().includes(search.trim().toLowerCase()),
  );

  const submit = () => {
    toast.success('Оплата принята', {
      description: `${EXTEND_SUGGESTIONS[selected]?.name ?? 'Клиент'} · ${formatInt(total)} ₽`,
    });
    onOpenChange(false);
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      title="Продление абонемента"
      description="Выберите клиента и условия — оплата за минуту"
      footerInfo={
        <>
          К&nbsp;оплате: <b className="font-[650] text-fg">{formatInt(total)} ₽</b>
          {saved > 0 ? (
            <span className="text-fg-subtle"> · скидка −{formatInt(saved)} ₽</span>
          ) : null}
        </>
      }
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton onClick={submit}>Принять оплату</ModalButton>
        </>
      }
    >
      <Section>Клиент</Section>
      <Field>
        <ModalInput
          icon={Search}
          placeholder="Имя, телефон или номер карты…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Field>
      <ResultList>
        {visible.map((s) => {
          const idx = EXTEND_SUGGESTIONS.indexOf(s);
          return (
            <ResultItem
              key={s.name}
              initials={s.initials}
              color={s.color}
              name={s.name}
              meta={s.meta}
              active={idx === selected}
              onClick={() => setSelected(idx)}
              aside={
                <span className={s.asideTone === 'danger' ? 'text-danger' : 'text-warning-deep'}>
                  {s.aside}
                </span>
              }
            />
          );
        })}
      </ResultList>

      <Section>Новый план</Section>
      <PlanCards options={EXTEND_PLANS} value={plan} onChange={setPlan} />

      <div className="mt-3.5">
        <FieldRow>
          <Field label="Скидка лояльности" hint="Клиент с нами 7 мес — рекомендуем 10%">
            <ModalInput
              type="number"
              min={0}
              max={50}
              suffix="%"
              value={discount}
              onChange={(e) => setDiscount(e.target.valueAsNumber)}
            />
          </Field>
          <Field label="Метка">
            <ModalSelect defaultValue="Без метки">
              <option>Без метки</option>
              <option>VIP</option>
              <option>Постоянный</option>
              <option>Корпоративный</option>
            </ModalSelect>
          </Field>
        </FieldRow>
      </div>

      <Section>Оплата</Section>
      <ChipGroup options={PAYMENT_METHODS} value={method} onChange={setMethod} />
    </AdaptiveModal>
  );
}
