/**
 * Доменные типы страницы «Тренеры». Портированы из Trainers.html как design-spec:
 * ростер карточек, недельная загрузка (heatmap), выручка по тренерам, заявки/заметки.
 * Цвета аватаров (градиенты/сплошные) приходят из данных (per-entity), не токены.
 */

/** Статус тренера — задаёт тон пилюли и цвет точки на аватаре. */
export type TrainerStatusKind = 'on' | 'shift-later' | 'vacation' | 'sick' | 'new';

/** Категория специализации (для мини-фильтра ростера). */
export type TrainerCategory = 'strength' | 'cardio' | 'mind-body';

/** Тон футноута статистики карточки (рост/падение/нейтраль). */
export type StatTrend = 'up' | 'down' | 'flat';

/** Тон полосы недельной загрузки тренера. */
export type LoadTone = 'hot' | 'normal' | 'low';

export interface TrainerStatDelta {
  label: string;
  trend: StatTrend;
}

export interface Trainer {
  id: string;
  initials: string;
  /** CSS-градиент аватара, напр. 'linear-gradient(135deg,#fbbf24,#f59e0b)'. */
  avatarGradient: string;
  /** Сплошной цвет для мелких аватаров (heatmap / выручка). */
  avatarColor: string;
  name: string;
  /** Специализация через « · », напр. «Силовые · функционал · реабилитация». */
  specialization: string;
  category: TrainerCategory;
  rating: number;
  reviews: number;
  /** Стаж, напр. «7 лет». */
  experience: string;
  /** Ставка-подпись, напр. «2 200 ₽/ч». */
  rateLabel: string;
  status: TrainerStatusKind;
  /** Текст пилюли статуса: «в зале», «отпуск · до 12 мая», «смена с 16:00». */
  statusLabel: string;

  trainings: number;
  trainingsDelta?: TrainerStatDelta;
  clients: number;
  /** Подпись под числом клиентов, напр. «3 новых», «из 18». */
  clientsNote?: string;
  /** Выручка за месяц, ₽ (точная). Компактный вид считается на месте. */
  revenue: number;
  /** Подпись доли в карточке, напр. «доля 19.6%». */
  shareLabel: string;
  /** Кол-во персональных тренировок (для переключателя ₽/Шт. в выручке). */
  ptCount: number;

  loadUsed: number;
  loadTotal: number;
  loadPct: number;
  loadTone: LoadTone;
  /** Подпись вместо часов, напр. «отпуск». */
  loadNote?: string;
}

/* ---------- Вкладки-фильтры верхнего уровня ---------- */

export type TrainerTab = 'roster' | 'schedule' | 'load' | 'payouts' | 'requests' | 'archive';

export interface TrainerFilterTab {
  tab: TrainerTab;
  label: string;
  count?: number;
  tone?: 'accent';
}

/* ---------- KPI ---------- */

export type TrainerKpiIcon = 'roster' | 'pt' | 'revenue' | 'rating';
export type TrainerKpiValueKind = 'int' | 'decimal2';

export interface TrainerKpi {
  id: string;
  icon: TrainerKpiIcon;
  label: string;
  value: number;
  valueKind: TrainerKpiValueKind;
  unit?: string;
  delta?: { label: string; direction: 'up' | 'down' | 'flat' };
  footNote?: string;
  chips?: { label: string; tone: 'neutral' | 'accent' | 'warn' }[];
}

/* ---------- Heatmap недельной загрузки ---------- */

export interface HeatmapDay {
  weekday: string;
  date: string;
  today?: boolean;
}

export type HeatLevel = 1 | 2 | 3 | 4;

export interface HeatCell {
  /** Часы (если занят) либо null для выходного/отпуска. */
  hours: number | null;
  level?: HeatLevel;
  /** Подпись пустой ячейки, напр. «вых.», «отп.». */
  offLabel?: string;
}

export interface HeatmapRow {
  trainerId: string;
  initials: string;
  color: string;
  name: string;
  /** Подпись под именем: «26 ч / 30» или «отпуск». */
  totalLabel: string;
  cells: HeatCell[];
}

export interface HeatmapData {
  weekLabel: string;
  days: HeatmapDay[];
  rows: HeatmapRow[];
  freeSlots: number;
  avgLoadPct: number;
  scaleLabel: string;
}

/* ---------- Выручка с тренеров ---------- */

export interface EarningRow {
  trainerId: string;
  initials: string;
  color: string;
  name: string;
  /** Мета-строка, напр. «38 ПТ · 2 200 ₽/ч». */
  meta: string;
  revenue: number;
  ptCount: number;
  /** Доля, %, напр. 19.6. */
  share: number;
}

export interface EarningsData {
  total: number;
  /** Подпись итога, напр. «итого с 6 тренеров». */
  totalLabel: string;
  /** Заметка о выплате, напр. «Выплата 5 мая · комиссия зала 30%». */
  payoutNote: string;
  /** Строки, отсортированные по выручке (по убыванию). */
  rows: EarningRow[];
}

/* ---------- Заявки и заметки ---------- */

export type RequestTone = 'warn' | 'danger' | 'ok' | 'neutral';

export interface RequestAction {
  label: string;
  primary?: boolean;
}

export interface RequestItem {
  id: string;
  tone: RequestTone;
  title: string;
  when: string;
  sub: string;
  actions: RequestAction[];
}

export interface RequestsData {
  pendingCount: number;
  totalCount: number;
  items: RequestItem[];
}

/* ---------- Сводка страницы ---------- */

export interface TrainersSummary {
  branch: string;
  total: number;
  inGymToday: number;
  ptMonth: number;
  avgRating: number;
}

export interface TrainersPageData {
  summary: TrainersSummary;
  kpis: TrainerKpi[];
  tabs: TrainerFilterTab[];
  trainers: Trainer[];
  /** Заголовок секции ростера, напр. «Команда · апрель». */
  rosterTitle: string;
  rosterSubtitle: string;
  heatmap: HeatmapData;
  loadSubtitle: string;
  earnings: EarningsData;
  requests: RequestsData;
}
