import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Search } from '@/components/icons';
import { AdaptiveModal } from './AdaptiveModal';
import {
  ChipGroup,
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  ModalSelect,
  PickRow,
  Section,
} from './fields';
import { BOOK_DAYS, BOOK_SLOTS, BOOK_TYPES, TRAINER_PICKS } from './options';

const TRAINER_NAME: Record<string, string> = {
  anya: 'Аня Соколова',
  denis: 'Денис Кравцов',
  mark: 'Марк Левин',
  liza: 'Лиза Орлова',
  igor: 'Игорь Раш',
  sonya: 'Соня Бек',
};

const DAY_LABEL: Record<string, string> = {
  today: 'сегодня',
  tomorrow: 'завтра',
  fri: 'пт, 2 мая',
  sat: 'сб, 3 мая',
  other: 'другая дата',
};

const BOOK_TYPE_DEFAULT = 'personal';
const BOOK_TRAINER_DEFAULT = 'anya';
const BOOK_DAY_DEFAULT = 'today';
const BOOK_SLOT_DEFAULT = '18';
const BOOK_DURATION_DEFAULT = '60 минут';

export function BookModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [type, setType] = useState(BOOK_TYPE_DEFAULT);
  const [trainer, setTrainer] = useState(BOOK_TRAINER_DEFAULT);
  const [day, setDay] = useState(BOOK_DAY_DEFAULT);
  const [slot, setSlot] = useState(BOOK_SLOT_DEFAULT);
  const [duration, setDuration] = useState(BOOK_DURATION_DEFAULT);

  useEffect(() => {
    if (open) {
      setType(BOOK_TYPE_DEFAULT);
      setTrainer(BOOK_TRAINER_DEFAULT);
      setDay(BOOK_DAY_DEFAULT);
      setSlot(BOOK_SLOT_DEFAULT);
      setDuration(BOOK_DURATION_DEFAULT);
    }
  }, [open]);

  const submit = () => {
    toast.success('Запись создана', {
      description: `${TRAINER_NAME[trainer]} · ${DAY_LABEL[day]} ${slot}:00`,
    });
    onOpenChange(false);
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      title="Запись на тренировку"
      description="Выберите клиента, тренера и удобный слот"
      footerInfo={
        <>
          <b className="font-[650] text-fg">{TRAINER_NAME[trainer]}</b> · {DAY_LABEL[day]},{' '}
          <b className="font-[650] text-fg">{slot}:00</b> · {duration}
        </>
      }
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton onClick={submit}>Записать</ModalButton>
        </>
      }
    >
      <Section>Клиент</Section>
      <Field>
        <ModalInput icon={Search} placeholder="Найти клиента…" />
      </Field>

      <Section>Тип</Section>
      <ChipGroup options={BOOK_TYPES} value={type} onChange={setType} />

      <Section>Тренер</Section>
      <PickRow options={TRAINER_PICKS} value={trainer} onChange={setTrainer} />

      <Section>Дата</Section>
      <ChipGroup options={BOOK_DAYS} value={day} onChange={setDay} />

      <Section>Свободный слот</Section>
      <ChipGroup options={BOOK_SLOTS} value={slot} onChange={setSlot} />

      <Section>Длительность · Заметка</Section>
      <FieldRow>
        <Field>
          <ModalSelect value={duration} onChange={(e) => setDuration(e.target.value)}>
            <option>60 минут</option>
            <option>75 минут</option>
            <option>90 минут</option>
            <option>45 минут</option>
          </ModalSelect>
        </Field>
        <Field>
          <ModalInput placeholder="Например: ноги + спина" />
        </Field>
      </FieldRow>
    </AdaptiveModal>
  );
}
