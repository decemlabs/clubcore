/**
 * Типы детальной страницы тренера (Trainer.html как design-spec): профиль-герой,
 * KPI, вкладки Обзор / Выплаты / История. Отдельно от types.ts (ростер-список),
 * чтобы не раздувать доменные типы таблицы.
 */

/** Лёгкая разметка строки таймлайна: plain-текст либо сегменты с bold. */
export interface RichSeg {
  t: string;
  b?: boolean;
}
export type Rich = string | RichSeg[];

export type TrainerKpiIcon = 'clients' | 'trainings' | 'fill' | 'earnings';

export interface TrainerDetailKpi {
  id: string;
  icon: TrainerKpiIcon;
  label: string;
  /** Число (форматируется на месте) либо готовая строка. */
  value: number | string;
  unit?: string;
  delta?: { label: string; direction: 'up' | 'down' | 'flat' };
  footNote?: string;
  chips?: { label: string; tone: 'neutral' | 'accent' | 'warn' }[];
}

/** Строка «Расписание · сегодня». */
export interface TrainerSession {
  time: string;
  title: string;
  sub: string;
  /** Цвет вертикальной полоски слева. */
  bar: 'accent' | 'group' | 'done';
  tag: string;
  tagTone: 'now' | 'done' | 'default';
}

export interface RegularClient {
  initials: string;
  /** CSS-градиент аватара. */
  color: string;
  name: string;
  sub?: string;
  /** Финальная строка-«ещё N» — приглушённая, без подписи. */
  muted?: boolean;
}

export interface TermRow {
  k: string;
  v: string;
}

export interface PayoutLine {
  label: string;
  sub?: string;
  value: string;
  minus?: boolean;
}

export interface TrainerPayout {
  title: string;
  /** Опции селектора периода. */
  periods: string[];
  lines: PayoutLine[];
  totalLabel: string;
  totalValue: string;
  statusLabel: string;
  period: string;
  payoutDate: string;
  method: string;
  payButtonLabel: string;
  /** Тост и подпись кнопки после проведения выплаты. */
  paidToast: string;
  paidButtonLabel: string;
}

export interface PayoutHistoryRow {
  id: string;
  title: string;
  sub: string;
  amount: string;
}

export type TimelineKind = 'check' | 'client' | 'cancel' | 'payout' | 'rate' | 'join';

export interface TimelineItem {
  id: string;
  kind: TimelineKind;
  tone: 'accent' | 'warn' | 'default';
  title: Rich;
  time: string;
}

export interface TimelineGroup {
  day: string;
  items: TimelineItem[];
}

export interface TrainerDetail {
  id: string;
  initials: string;
  /** CSS-градиент аватара героя. */
  avatarGradient: string;
  name: string;
  /** Текст бейджа статуса героя, напр. «Активна». */
  statusLabel: string;
  rating: number;
  branch: string;
  memberSince: string;
  phone: string;
  specs: string[];

  kpis: TrainerDetailKpi[];

  schedule: TrainerSession[];
  scheduleDateLabel: string;
  regulars: RegularClient[];
  regularsCount: number;
  terms: TermRow[];

  payout: TrainerPayout;
  payoutHistory: PayoutHistoryRow[];

  timeline: TimelineGroup[];
}
