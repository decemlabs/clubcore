/** Доменные типы дашборда. Данные приходят через хуки из ./api (пока — моки). */

export type DeltaDirection = 'up' | 'down' | 'flat';

export interface KpiDelta {
  /** Готовая подпись, напр. "+34", "+12%". */
  label: string;
  direction: DeltaDirection;
}

export type ChipTone = 'neutral' | 'accent' | 'warn';

export interface KpiChip {
  label: string;
  tone: ChipTone;
}

export type KpiIconName = 'members' | 'revenue' | 'trainings' | 'visits';

export interface KpiCard {
  id: string;
  label: string;
  icon: KpiIconName;
  /** Основное число (форматируется через formatInt на месте). */
  value: number;
  /** Единица/суффикс рядом со значением, напр. "₽" или "/ 112". */
  unit?: string;
  delta?: KpiDelta;
  footNote?: string;
  chips?: KpiChip[];
}

export type DashboardPeriod = 'day' | 'week' | 'month' | 'year';

export interface DashboardOverview {
  /** Заголовок-дата, напр. "Среда, 30 апреля". */
  dateLabel: string;
  greetingName: string;
  trainingsToday: number;
  expectedVisits: number;
  defaultPeriod: DashboardPeriod;
  kpis: KpiCard[];
}

/* ---------- Заполняемость по часам ---------- */

export type HourState = 'past' | 'now' | 'future';

export interface HourBar {
  /** Час суток 7..23. */
  hour: number;
  /** Высота столбца, 0..100 (%). */
  value: number;
  state: HourState;
}

export interface HourlyOccupancy {
  bars: HourBar[];
  /** Подпись под заголовком, напр. "Сегодня · ср, 30 апр · обновлено 2 мин назад". */
  subtitle: string;
  peakHour: string;
  peakCount: number;
}

/* ---------- Живая заполняемость («В клубе сейчас») ---------- */

export interface OccupancyFace {
  initials: string;
  color: string;
}

export interface OccupancyCell {
  label: string;
  value: number;
  /** Ширина мини-полосы, 0..100 (%). */
  barPct: number;
  /** Прирост (для центральной ячейки «Сейчас»), напр. "↑ 20%". */
  delta?: string;
  /** Приглушённая полоса (обычное значение/пик) vs яркая (текущее). */
  muted?: boolean;
}

export interface OccupancyNow {
  current: number;
  capacity: number;
  faces: OccupancyFace[];
  moreCount: number;
  cells: OccupancyCell[];
  /** Заполнение метра, 0..100 (%). */
  fillPct: number;
  dayVisits: number;
}

/* ---------- Расписание тренировок (сегодня) ---------- */

export type SessionType = 'pt' | 'gr';
export type SessionState = 'done' | 'live' | 'planned' | 'group';

export interface ScheduleSession {
  id: string;
  time: string;
  duration: string;
  initials: string;
  color: string;
  type: SessionType;
  /** Кто ведёт (для групповых — с дисциплиной, напр. "Лиза Орлова · йога"). */
  who: string;
  /** Жирная часть строки «что», напр. "Карина Левчук" или "8/10". */
  whatBold: string;
  /** Остаток строки «что», напр. " · ноги + спина" или " человек · зал 2". */
  whatRest: string;
  state: SessionState;
  stateLabel: string;
}

export interface ScheduleToday {
  sessions: ScheduleSession[];
  /** Подпись текущего момента в разделителе, напр. "15:42 · сейчас". */
  nowLabel: string;
  total: number;
  done: number;
  live: number;
  planned: number;
}

/* ---------- Истекающие абонементы ---------- */

export type ExpiryUrgency = 'urgent' | 'soon' | 'normal';

export interface ExpiringMembership {
  id: string;
  initials: string;
  color: string;
  name: string;
  meta: string;
  whenTop: string;
  whenDate: string;
  urgency: ExpiryUrgency;
}

export interface ExpiringList {
  items: ExpiringMembership[];
  daysAhead: number;
  totalClients: number;
}

/* ---------- Выручка ---------- */

export type RevenuePeriod = '30' | '90' | 'year';

export interface RevenuePoint {
  /** Полная подпись для тултипа, напр. "12 апр". */
  label: string;
  /** Короткая подпись для оси, напр. "12". */
  short: string;
  value: number;
}

export interface RevenueBreakdownCell {
  label: string;
  value: number;
  color: string;
}

export interface RevenueSeries {
  period: RevenuePeriod;
  title: string;
  rangeLabel: string;
  /** Готовое к показу число выручки (headline). */
  total: number;
  delta: KpiDelta;
  deltaSub: string;
  points: RevenuePoint[];
  breakdown: RevenueBreakdownCell[];
  /** Каждую N-ю подпись показываем на оси X. */
  ticksEvery: number;
}

export interface RevenueData {
  defaultPeriod: RevenuePeriod;
  series: Record<RevenuePeriod, RevenueSeries>;
}

/* ---------- Топ тренеры ---------- */

export interface TopTrainer {
  id: string;
  initials: string;
  color: string;
  name: string;
  /** Ширина полосы, 0..100 (%). */
  barPct: number;
  meta: string;
  amountLabel: string;
  rankLabel: string;
}

/* ---------- Обращения клиентов ---------- */

export interface ClientMessage {
  id: string;
  initials: string;
  color: string;
  name: string;
  time: string;
  body: string;
  unread: boolean;
}

/* ---------- Лента активности ---------- */

export type ActivityType =
  | 'checkin'
  | 'payment'
  | 'training'
  | 'cancel'
  | 'alert'
  | 'signup'
  | 'expire';

export type ActivityCategory = 'checkin' | 'payment' | 'training' | 'alert';

export interface ActivityEvent {
  id: string;
  type: ActivityType;
  title: string;
  /** Текст подписи (лид). После него опционально показываем amount/danger. */
  subLead: string;
  /** Сумма-акцент, напр. "12 000 ₽". */
  amount?: string;
  /** Отрицательная сумма-предупреждение, напр. "−1 500 ₽". */
  danger?: string;
  /** Готовая подпись «сколько назад», напр. "4 мин". */
  timeLabel: string;
}

export interface ActivityFeedData {
  events: ActivityEvent[];
  subtitle: string;
  repliedToday: number;
}

/** Полная сводка дашборда (всё, что рендерит страница ниже шапки). */
export interface DashboardData {
  overview: DashboardOverview;
  hourly: HourlyOccupancy;
  occupancy: OccupancyNow;
  schedule: ScheduleToday;
  expiring: ExpiringList;
  revenue: RevenueData;
  topTrainers: TopTrainer[];
  messages: ClientMessage[];
  activity: ActivityFeedData;
}
