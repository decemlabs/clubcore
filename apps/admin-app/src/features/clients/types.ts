/**
 * Доменные типы страницы «Клиенты».
 * Портированы из шаблона Clients.html как design-spec: статусы, абонемент с прогрессом,
 * срок действия, визиты, тренер. Значения-цвета аватаров приходят из данных (per-entity).
 */

/** Статус клиента — определяет пилюлю и левую полосу в карточке. */
export type ClientStatus = 'active' | 'expiring' | 'frozen' | 'lead' | 'expired';

/** Значение фильтра-вкладки (статусы + «все»). */
export type ClientFilter = 'all' | ClientStatus;

/** Тон заполнения прогресс-бара абонемента. */
export type PlanTone = 'normal' | 'warn' | 'danger' | 'muted';

/** Срочность истечения — красит верхнюю строку ячейки «Истекает». */
export type ExpiryUrgency = 'urgent' | 'soon' | 'normal';

/** Тип абонемента (для фильтра «Тип»). Выводится из названия плана. */
export type PlanType = 'monthly' | 'half' | 'year';

export interface ClientPlan {
  /** Полное название с суффиксом статуса, напр. «Годовой · пауза», «Месячный · истёк». */
  name: string;
  /** Приглушить название (заморозка / истёкший). */
  muted?: boolean;
  /** Тип для фильтрации. */
  type: PlanType;
  /** Заполнение прогресс-бара, %. */
  fillPct: number;
  tone: PlanTone;
  /** Подпись под баром, напр. «2 / 30 дней», «219 / 365 дней · до 18 мая». */
  daysLabel: string;
}

export interface ClientTrainer {
  initials: string;
  /** Цвет аватара (hex из данных). */
  color: string;
  name: string;
}

export interface ClientExpiry {
  /** Верхняя строка — дата, напр. «2 мая». */
  top: string;
  /** Нижняя строка, напр. «через 2 дня», «−18 дней». */
  sub: string;
  urgency: ExpiryUrgency;
  /** Ключ сортировки: дней до истечения (может быть отрицательным). */
  daysLeft: number;
}

export interface ClientVisits {
  /** Отображаемое число визитов за месяц («8», «0»). */
  value: string;
  /** Выделять жирным (есть активность) — иначе приглушённый ноль. */
  strong: boolean;
  /** Хвост-подпись, напр. «12 всего», «тестовая». */
  total?: string;
  /** Ключ сортировки. */
  month: number;
}

export interface ClientLastVisit {
  /** Верхняя строка: «Сегодня» / «Вчера» / «28 апр». */
  top: string;
  /** Подпись: «29 апр, 19:14» / «11:32». */
  sub: string;
  /** Ранг свежести (больше = новее) — ключ сортировки. */
  rank: number;
}

export interface Client {
  id: string;
  initials: string;
  /** Цвет аватара (hex из данных). */
  color: string;
  name: string;
  hasNote?: boolean;
  phone: string;
  /** Стаж/первый визит, напр. «7 мес», «впервые сегодня». */
  tenure: string;
  status: ClientStatus;
  /** Абонемент; null у лидов — тогда показываем planNote. */
  plan: ClientPlan | null;
  /** Заглушка вместо абонемента у лидов, напр. «— анкета не заполнена». */
  planNote?: string;
  /** Срок действия; null у лидов. */
  expiry: ClientExpiry | null;
  visits: ClientVisits;
  /** Закреплённый тренер; null если не назначен. */
  trainer: ClientTrainer | null;
  lastVisit: ClientLastVisit;
}

export type FilterTone = 'accent' | 'warn' | 'danger';

export interface ClientFilterTab {
  filter: ClientFilter;
  label: string;
  count: number;
  /** Тон счётчика; по умолчанию нейтральный. */
  tone?: FilterTone;
}

export interface ClientsSummary {
  branch: string;
  total: number;
  weeklyNew: number;
  expiringSoon: number;
  expiringDays: number;
}

/** Сортируемые колонки таблицы клиентов. */
export type ClientSortKey = 'name' | 'expires' | 'visits' | 'last';
export type SortDir = 'asc' | 'desc';
export interface ClientSort {
  key: ClientSortKey;
  dir: SortDir;
}

export interface ClientsPageData {
  summary: ClientsSummary;
  filters: ClientFilterTab[];
  clients: Client[];
  /** Сколько строк показано из общего числа (для пагинации). */
  shownCount: number;
  totalCount: number;
  totalPages: number;
  currentPage: number;
}
