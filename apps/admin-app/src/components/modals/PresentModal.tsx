import { useEffect, useState } from 'react';
import { ROUTES } from '@/app/routes';
import { router } from '@/app/router';
import { Initials } from '@/components/ui/initials';
import { AdaptiveModal } from './AdaptiveModal';
import { ChipGroup, ModalButton } from './fields';

type Zone = 'all' | 'gym' | 'studio' | 'sauna';

interface Person {
  zone: Exclude<Zone, 'all'>;
  color: string;
  initials: string;
  name: string;
  meta: string;
}

const ZONES: { value: Zone; label: string; sub: string }[] = [
  { value: 'all', label: 'Все', sub: '42' },
  { value: 'gym', label: 'Зал', sub: '31' },
  { value: 'studio', label: 'Студия', sub: '8' },
  { value: 'sauna', label: 'Сауна', sub: '3' },
];

const PEOPLE: Person[] = [
  { zone: 'gym', color: '#0ea5e9', initials: 'МЛ', name: 'Марк Левин', meta: 'с 15:24 · 12 мин' },
  {
    zone: 'studio',
    color: '#a855f7',
    initials: 'ЛО',
    name: 'Лиза Орлова',
    meta: 'с 15:18 · 18 мин',
  },
  {
    zone: 'gym',
    color: '#f59e0b',
    initials: 'КЛ',
    name: 'Карина Левчук',
    meta: 'с 15:02 · 34 мин',
  },
  { zone: 'gym', color: '#10b981', initials: 'АШ', name: 'Артур Шах', meta: 'с 14:47 · 49 мин' },
  { zone: 'gym', color: '#6366f1', initials: 'НС', name: 'Никита Сюй', meta: 'с 14:42 · 54 мин' },
  {
    zone: 'studio',
    color: '#dc2626',
    initials: 'МК',
    name: 'Маша Конева',
    meta: 'с 14:30 · 1 ч 6 мин',
  },
  {
    zone: 'sauna',
    color: '#f59e0b',
    initials: 'ОИ',
    name: 'Олег Ивлев',
    meta: 'с 14:20 · 1 ч 16 мин',
  },
  {
    zone: 'gym',
    color: '#0ea5e9',
    initials: 'ИГ',
    name: 'Иван Гранин',
    meta: 'с 14:14 · 1 ч 22 мин',
  },
  {
    zone: 'gym',
    color: '#a855f7',
    initials: 'ЮЗ',
    name: 'Юлия Зайцева',
    meta: 'с 14:00 · 1 ч 36 мин',
  },
  {
    zone: 'studio',
    color: '#10b981',
    initials: 'СБ',
    name: 'Соня Бек',
    meta: 'с 13:55 · 1 ч 41 мин',
  },
  {
    zone: 'gym',
    color: '#dc2626',
    initials: 'ДК',
    name: 'Денис Кравцов',
    meta: 'с 13:48 · 1 ч 48 мин',
  },
  {
    zone: 'sauna',
    color: '#6366f1',
    initials: 'ИР',
    name: 'Игорь Раш',
    meta: 'с 13:30 · 2 ч 6 мин',
  },
  { zone: 'gym', color: '#f59e0b', initials: 'АС', name: 'Аня Соколова', meta: 'тренер · с 09:00' },
  { zone: 'gym', color: '#0ea5e9', initials: 'МЛ', name: 'Марк Левин', meta: 'тренер · с 12:00' },
  {
    zone: 'gym',
    color: '#0284c7',
    initials: 'КП',
    name: 'Кирилл Петров',
    meta: 'с 13:20 · 2 ч 16 мин',
  },
  {
    zone: 'gym',
    color: '#7c3aed',
    initials: 'ЯТ',
    name: 'Яна Турчанинова',
    meta: 'с 13:10 · 2 ч 26 мин',
  },
];

const PRESENT_ZONE_DEFAULT: Zone = 'all';

export function PresentModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [zone, setZone] = useState<Zone>(PRESENT_ZONE_DEFAULT);

  useEffect(() => {
    if (open) {
      setZone(PRESENT_ZONE_DEFAULT);
    }
  }, [open]);

  const visible = zone === 'all' ? PEOPLE : PEOPLE.filter((p) => p.zone === zone);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      size="wide"
      title="В клубе сейчас · 42 / 80"
      description="Обычно в это время 35 · пик дня 74 в 20:00 · обновлено только что"
      footerInfo={
        <>
          Пиковая загрузка ожидается в <b className="font-[650] text-fg">20:00</b> · ~74 чел
        </>
      }
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Закрыть
          </ModalButton>
          <ModalButton
            onClick={() => {
              onOpenChange(false);
              void router.navigate(ROUTES.attendance);
            }}
          >
            Открыть посещаемость
          </ModalButton>
        </>
      }
    >
      <ChipGroup options={ZONES} value={zone} onChange={(v) => setZone(v as Zone)} />

      <div className="mt-3.5 grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
        {visible.map((p, i) => (
          <div
            key={`${p.initials}-${i}`}
            className="flex items-center gap-2.5 rounded-[10px] border-[0.5px] border-border bg-surface-2 px-2.5 py-2.5"
          >
            <Initials initials={p.initials} color={p.color} className="size-[30px] text-[11px]" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[12.5px] font-semibold tracking-[-0.1px]">{p.name}</div>
              <div className="mt-px text-[10.5px] tabular-nums text-fg-subtle">{p.meta}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 text-center text-xs text-fg-subtle">+ 26 клиентов не показаны</div>
    </AdaptiveModal>
  );
}
