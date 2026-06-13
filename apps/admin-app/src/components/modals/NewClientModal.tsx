import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { formatInt } from '@/lib/format';
import { Camera, CheckCircle2, Phone } from '@/components/icons';
import { AdaptiveModal } from './AdaptiveModal';
import {
  Callout,
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  ModalSelect,
  PlanCards,
  Section,
} from './fields';
import { NEW_CLIENT_PLANS, PLAN_PRICE, SOURCE_OPTIONS, TRAINER_SELECT_OPTIONS } from './options';

function PhotoDrop() {
  return (
    <div className="flex items-center gap-3.5 rounded-xl border border-dashed border-border-strong bg-surface-2 p-[12px_14px]">
      <span className="grid size-14 shrink-0 place-items-center rounded-full bg-surface-3 text-fg-subtle">
        <Camera className="size-[22px]" strokeWidth={2} />
      </span>
      <span className="text-[12.5px] text-fg-muted">
        <b className="block text-[13px] font-[650] text-fg">Загрузить фото</b>
        Или будет автоматически создан аватар по имени
      </span>
    </div>
  );
}

const NEW_CLIENT_PLAN_DEFAULT = 'half';
const NEW_CLIENT_DISCOUNT_DEFAULT = 0;

export function NewClientModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [plan, setPlan] = useState(NEW_CLIENT_PLAN_DEFAULT);
  const [discount, setDiscount] = useState(NEW_CLIENT_DISCOUNT_DEFAULT);

  useEffect(() => {
    if (open) {
      setPlan(NEW_CLIENT_PLAN_DEFAULT);
      setDiscount(NEW_CLIENT_DISCOUNT_DEFAULT);
    }
  }, [open]);

  const total = useMemo(() => {
    const base = PLAN_PRICE[plan] ?? 0;
    const d = Math.min(50, Math.max(0, Number.isFinite(discount) ? discount : 0));
    return base - Math.round((base * d) / 100);
  }, [plan, discount]);

  const submit = () => {
    toast.success('Клиент создан', {
      description: `К оплате ${formatInt(total)} ₽ · SMS отправлено`,
    });
    onOpenChange(false);
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      size="wide"
      title="Новый клиент"
      description="Анкета и выбор абонемента — займёт около минуты"
      footerInfo={
        <>
          К&nbsp;оплате: <b className="font-[650] text-fg">{formatInt(total)} ₽</b>
        </>
      }
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton onClick={submit}>Создать и принять оплату</ModalButton>
        </>
      }
    >
      <Section>Профиль</Section>
      <PhotoDrop />
      <div className="mt-3.5">
        <FieldRow>
          <Field label="Имя">
            <ModalInput placeholder="Алина" autoComplete="given-name" />
          </Field>
          <Field label="Фамилия">
            <ModalInput placeholder="Степанова" autoComplete="family-name" />
          </Field>
        </FieldRow>
      </div>
      <FieldRow>
        <Field label="Телефон">
          <ModalInput icon={Phone} type="tel" placeholder="+7 (___) ___-__-__" autoComplete="tel" />
        </Field>
        <Field label="Email" optional>
          <ModalInput type="email" placeholder="alina@mail.ru" autoComplete="email" />
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Дата рождения">
          <ModalInput type="date" />
        </Field>
        <Field label="Источник">
          <ModalSelect defaultValue={SOURCE_OPTIONS[0]}>
            {SOURCE_OPTIONS.map((o) => (
              <option key={o}>{o}</option>
            ))}
          </ModalSelect>
        </Field>
      </FieldRow>

      <Section>Абонемент</Section>
      <PlanCards options={NEW_CLIENT_PLANS} value={plan} onChange={setPlan} />

      <div className="mt-3.5">
        <FieldRow>
          <Field label="Скидка">
            <ModalInput
              type="number"
              min={0}
              max={50}
              suffix="%"
              placeholder="0"
              value={discount || ''}
              onChange={(e) => setDiscount(e.target.valueAsNumber || 0)}
            />
          </Field>
          <Field label="Персональный тренер">
            <ModalSelect defaultValue={TRAINER_SELECT_OPTIONS[0]}>
              {TRAINER_SELECT_OPTIONS.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </ModalSelect>
          </Field>
        </FieldRow>
      </div>

      <Callout tone="accent" icon={CheckCircle2}>
        Клиент получит SMS со ссылкой на установку PWA и QR-карту в&nbsp;течение минуты.
      </Callout>
    </AdaptiveModal>
  );
}
