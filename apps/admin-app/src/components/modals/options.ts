/**
 * Статические опции для модалок действий (планы, оплата, тренеры, слоты).
 * Портированы из Client.html. Цены — для живого подсчёта «к оплате».
 */
import { ArrowRightLeft, Banknote, CreditCard, Link2 } from '@/components/icons';
import type { ChipOption, PickOption, PlanOption } from './fields';

export const PLAN_PRICE: Record<string, number> = { month: 4900, half: 24600, year: 42000 };

export const NEW_CLIENT_PLANS: PlanOption[] = [
  { value: 'month', name: 'Месячный', price: '4 900 ₽', sub: '30 дней · все направления' },
  {
    value: 'half',
    name: 'Полугодовой',
    price: '24 600 ₽',
    sub: '180 дней · экономия 4 800 ₽',
    tag: '−15%',
  },
  {
    value: 'year',
    name: 'Годовой',
    price: '42 000 ₽',
    sub: '365 дней · экономия 16 800 ₽',
    tag: '−28%',
  },
];

export const EXTEND_PLANS: PlanOption[] = [
  { value: 'month', name: 'Месячный', price: '4 900 ₽', sub: '+30 дней' },
  { value: 'half', name: 'Полугодовой', price: '24 600 ₽', sub: '+180 дней', tag: '−15%' },
  { value: 'year', name: 'Годовой', price: '42 000 ₽', sub: '+365 дней', tag: '−28%' },
];

export const PAYMENT_METHODS: ChipOption[] = [
  { value: 'card', label: 'Карта', icon: CreditCard },
  { value: 'cash', label: 'Наличные', icon: Banknote },
  { value: 'transfer', label: 'Перевод', icon: ArrowRightLeft },
  { value: 'link', label: 'Ссылка на оплату', icon: Link2 },
];

export const SOURCE_OPTIONS = [
  'Друзья / реферал',
  'Instagram',
  'Google / Яндекс',
  'Прошёл мимо',
  'Сайт',
  'Telegram',
];

export const TRAINER_SELECT_OPTIONS = [
  '— Не выбран —',
  'Аня Соколова · силовые',
  'Денис Кравцов · бокс, ММА',
  'Марк Левин · кроссфит',
  'Лиза Орлова · йога',
  'Игорь Раш · бодибилдинг',
];

export interface ClientSuggestion {
  initials: string;
  color: string;
  name: string;
  meta: string;
  aside: string;
  asideTone: 'danger' | 'warn';
}

export const EXTEND_SUGGESTIONS: ClientSuggestion[] = [
  {
    initials: 'ОИ',
    color: '#0ea5e9',
    name: 'Олег Ивлев',
    meta: 'Месячный · истекает 2 мая · 7 мес с нами',
    aside: '2 дня',
    asideTone: 'danger',
  },
  {
    initials: 'КЛ',
    color: '#f59e0b',
    name: 'Карина Левчук',
    meta: 'Полугодовой · истекает 3 мая · 2 года с нами',
    aside: '3 дня',
    asideTone: 'danger',
  },
  {
    initials: 'ЮЗ',
    color: '#a855f7',
    name: 'Юлия Зайцева',
    meta: 'Месячный · истекает 5 мая · 11 мес с нами',
    aside: '5 дней',
    asideTone: 'warn',
  },
];

export interface RecentCheckin {
  initials: string;
  color: string;
  name: string;
  meta: string;
  time: string;
  ago: string;
  now?: boolean;
}

export const RECENT_CHECKINS: RecentCheckin[] = [
  {
    initials: 'МЛ',
    color: '#0ea5e9',
    name: 'Марк Левин',
    meta: 'Годовой · истекает 14 окт',
    time: '15:24',
    ago: 'сейчас',
    now: true,
  },
  {
    initials: 'ЛО',
    color: '#a855f7',
    name: 'Лиза Орлова',
    meta: 'Полугодовой · истекает 2 авг',
    time: '15:18',
    ago: '6 мин',
  },
  {
    initials: 'КЛ',
    color: '#f59e0b',
    name: 'Карина Левчук',
    meta: 'Полугодовой · истекает 3 мая',
    time: '15:02',
    ago: '22 мин',
  },
  {
    initials: 'АШ',
    color: '#10b981',
    name: 'Артур Шах',
    meta: 'Месячный · истекает 9 мая',
    time: '14:47',
    ago: '37 мин',
  },
];

export const BOOK_TYPES: ChipOption[] = [
  { value: 'personal', label: 'Персональная' },
  { value: 'group', label: 'Групповая' },
  { value: 'check', label: 'Пробная' },
];

export const TRAINER_PICKS: PickOption[] = [
  { value: 'anya', initials: 'АС', color: '#f59e0b', name: 'Аня С.', sub: 'Силовые' },
  { value: 'denis', initials: 'ДК', color: '#dc2626', name: 'Денис К.', sub: 'Бокс' },
  { value: 'mark', initials: 'МЛ', color: '#0ea5e9', name: 'Марк Л.', sub: 'Кроссфит' },
  { value: 'liza', initials: 'ЛО', color: '#a855f7', name: 'Лиза О.', sub: 'Йога' },
  { value: 'igor', initials: 'ИР', color: '#6366f1', name: 'Игорь Р.', sub: 'Бодибилд.' },
  { value: 'sonya', initials: 'СБ', color: '#10b981', name: 'Соня Б.', sub: 'Пилатес' },
];

export const BOOK_DAYS: ChipOption[] = [
  { value: 'today', label: 'Сегодня · ср' },
  { value: 'tomorrow', label: 'Завтра · чт' },
  { value: 'fri', label: 'Пт, 2 мая' },
  { value: 'sat', label: 'Сб, 3 мая' },
  { value: 'other', label: 'Другая…' },
];

export const BOOK_SLOTS: ChipOption[] = [
  { value: '16', label: '16:00' },
  { value: '17', label: '17:00' },
  { value: '18', label: '18:00' },
  { value: '19', label: '19:00' },
  { value: '21', label: '21:00', sub: 'занят' },
];
