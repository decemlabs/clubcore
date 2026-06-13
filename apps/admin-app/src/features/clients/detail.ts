/**
 * Типы детальной страницы клиента (Client.html как design-spec).
 * Отдельно от types.ts (список), чтобы не раздувать доменные типы таблицы.
 */
import type { ClientStatus } from './types';

/** Лёгкая разметка строки: либо plain-текст, либо сегменты с bold/muted. */
export interface RichSegment {
  text: string;
  bold?: boolean;
  muted?: boolean;
}
export type Rich = string | RichSegment[];

export interface DetailSubscription {
  name: string;
  amount: string;
  daysUsed: number;
  daysTotal: number;
  fillPct: number;
  /** Подпись справа под баром, напр. «через 3 дня». */
  expiresLabel: string;
  urgent: boolean;
  features: string[];
}

export interface DetailTrainerStat {
  value: string;
  label: string;
}

export interface DetailTrainer {
  initials: string;
  color: string;
  name: string;
  spec: string;
  stats: DetailTrainerStat[];
}

export interface ContactRow {
  k: string;
  v: string;
  /** Доп. приглушённый хвост (напр. «· ✓ SMS · ✓ Push»). */
  muted?: string;
}

export interface GoalBlock {
  label: string;
  body?: string;
  chips?: { label: string; warn?: boolean }[];
}

export interface StatCell {
  label: string;
  value: string;
  unit?: string;
  foot: string;
  /** Зелёный акцентный хвост после foot (напр. «+22%»). */
  footAccent?: string;
}

export type ActivityKind = 'checkin' | 'chat' | 'training' | 'note';
export type ActivityTone = 'accent' | 'warn' | 'note' | 'default';

export interface ActivityEvent {
  id: string;
  time: string;
  kind: ActivityKind;
  tone: ActivityTone;
  title: Rich;
  sub?: Rich;
  quote?: string;
  action?: { button: string; note: string };
}

export interface ActivityGroup {
  day: string;
  events: ActivityEvent[];
}

export type TrainingType = 'personal' | 'group';

export interface TrainingItem {
  id: string;
  day: string;
  month: string;
  trainerInitials: string;
  trainerColor: string;
  title: string;
  tag: string;
  type: TrainingType;
  meta: Rich;
  note: string;
  amount: string;
}

export interface TrainingsTabData {
  title: string;
  sub: string;
  items: TrainingItem[];
  moreLabel: string;
}

export type PaymentIcon = 'card' | 'trainer' | 'shop' | 'refund';

export interface PaymentSummaryCell {
  label: string;
  value: string;
  foot: string;
}

export interface PaymentItem {
  id: string;
  icon: PaymentIcon;
  title: string;
  meta: string;
  amount: string;
  refund?: boolean;
}

export interface PaymentsTabData {
  summary: PaymentSummaryCell[];
  title: string;
  sub: string;
  items: PaymentItem[];
  moreLabel: string;
}

export type ChatEntry =
  | { kind: 'day'; id: string; label: string }
  | {
      kind: 'msg';
      id: string;
      side: 'them' | 'me' | 'system';
      text: string;
      time?: string;
      unread?: boolean;
    };

export interface ChatTabData {
  lastActivity: string;
  entries: ChatEntry[];
  composePlaceholder: string;
}

export interface NoteItem {
  id: string;
  authorInitials: string;
  authorColor: string;
  author: string;
  authorTag?: string;
  date: string;
  body: Rich;
  tags?: { label: string; warn?: boolean }[];
}

export interface ClientDetail {
  id: string;
  initials: string;
  color: string;
  name: string;
  status: ClientStatus;
  statusLabel: string;
  phone: string;
  email: string;
  telegram: string;
  birthday: string;
  memberSinceLabel: string;
  tenure: string;
  subscription: DetailSubscription;
  trainer: DetailTrainer;
  contact: ContactRow[];
  goals: GoalBlock[];
  stats: StatCell[];
  counts: { trainings: number; payments: number; chat: number; notes: number };
  activity: { groups: ActivityGroup[]; moreLabel: string };
  trainings: TrainingsTabData;
  payments: PaymentsTabData;
  chat: ChatTabData;
  notes: { items: NoteItem[]; composePlaceholder: string };
}
