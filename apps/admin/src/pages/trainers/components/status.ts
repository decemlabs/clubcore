/**
 * Цветовые карты и хелперы статусов тренера (вынесены из компонентов ради react-refresh).
 */
import type {
  LoadTone,
  StatTrend,
  TrainerCategory,
  TrainerStatusKind,
} from '@/features/trainers/types';

/** Цвет точки-индикатора статуса на аватаре тренера. */
export const STATUS_DOT: Record<TrainerStatusKind, string> = {
  on: 'bg-primary',
  'shift-later': 'bg-fg-subtle',
  vacation: 'bg-warning',
  sick: 'bg-danger',
  new: 'bg-info',
};

/** Заполнение полосы недельной загрузки (горячая/обычная/простой). */
export const LOAD_FILL: Record<LoadTone, string> = {
  hot: 'bg-primary',
  normal: 'bg-fg',
  low: 'bg-fg-subtle',
};

/** Цвет футноута статистики карточки (рост/падение/нейтраль). */
export const TREND_TEXT: Record<StatTrend, string> = {
  up: 'text-primary-deep dark:text-primary',
  down: 'text-danger',
  flat: 'text-fg-subtle',
};

/** Подписи категорий специализации (мини-фильтр ростера). */
export const CATEGORY_LABEL: Record<TrainerCategory, string> = {
  strength: 'Силовые',
  cardio: 'Кардио',
  'mind-body': 'Mind & body',
};

const FORMS_REVIEWS: [string, string, string] = ['отзыв', 'отзыва', 'отзывов'];

/** Русские формы множественного числа: [1, 2–4, 5+]. */
function pluralRu(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

/** «128 отзывов» / «201 отзыв» / «174 отзыва». */
export function pluralReviews(n: number): string {
  return pluralRu(n, FORMS_REVIEWS);
}
