/**
 * Доменные типы экрана «Уведомления и сообщения» (Notifications.html).
 * Хаб из 5 вкладок: центр уведомлений (лента), история, шаблоны, рассылка, доставка.
 * Цвета аватаров — per-entity градиенты (из данных), не токены.
 */

export type Channel = 'sms' | 'push' | 'email';
export const CHANNEL_LABEL: Record<Channel, string> = { sms: 'SMS', push: 'Push', email: 'Email' };

export type NotifTone = 'success' | 'warn' | 'danger' | 'info';
export type NotifCat = 'finance' | 'clients' | 'system';

export interface NotifItem {
  id: string;
  day: 'today' | 'earlier';
  cat: NotifCat;
  tone: NotifTone;
  unread: boolean;
  /** Заголовок: lead + <b>bold</b> + tail. */
  lead: string;
  bold: string;
  tail: string;
  body: string;
  time: string;
  icon: string;
}

export interface HistItem {
  id: string;
  name: string;
  sub: string;
  ch: Channel;
  aud: string;
  sent: string;
  pct: number;
}

export interface TplItem {
  id: string;
  name: string;
  trigger: string;
  ch: Channel;
  on: boolean;
  body: string;
}

export interface AudienceOpt {
  label: string;
  n: number;
}

export interface DeliveryStat {
  key: 'sent' | 'deliv' | 'read' | 'fail';
  label: string;
  value: number;
  pct: string;
}

export interface Recipient {
  id: string;
  initials: string;
  gradient: string;
  name: string;
  phone: string;
  status: 'read' | 'deliv' | 'fail';
  statusText: string;
}

export interface NotificationsData {
  notifications: NotifItem[];
  history: HistItem[];
  templates: TplItem[];
  audiences: AudienceOpt[];
  defaultMessage: string;
  delivery: { name: string; meta: string; stats: DeliveryStat[]; recipients: Recipient[] };
}
