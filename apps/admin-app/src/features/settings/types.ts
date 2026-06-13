/**
 * Доменные типы экрана «Настройки» (Settings.html). Длинная форма из 12 разделов;
 * списочные данные (команда, сессии, интеграции, счета, матрица уведомлений) — здесь.
 */

export interface NavLink {
  id: string;
  label: string;
  icon: string;
  pill?: string;
  external?: boolean;
  /** Маршрут перехода для external-ссылки (подстраница настроек). */
  to?: string;
  danger?: boolean;
}
export interface NavGroup {
  title: string;
  links: NavLink[];
}

export interface SessionRow {
  device: 'monitor' | 'phone';
  name: string;
  current?: boolean;
  meta: string;
}
export interface AuditRow {
  time: string;
  text: string;
  ip: string;
}

export type Role = 'owner' | 'admin' | 'trainer' | 'cashier';
export interface TeamMember {
  initials: string;
  color: string;
  name: string;
  note?: string;
  role: Role;
  roleLabel: string;
  branch: string;
  twofaOk: boolean;
  twofaLabel: string;
  last: string;
  lastSub: string;
}

export interface ChannelRow {
  trigger: string;
  sub: string;
  push: boolean;
  email: boolean;
  sms: boolean;
  tg: boolean;
  emailLocked?: boolean;
}

export interface IntegrationRow {
  logo: string;
  color: string;
  name: string;
  desc: string;
  meta: string;
  status: 'ok' | 'warn' | 'off';
  chip?: string;
  chipTone?: 'accent' | 'warn';
  action: string;
  muted?: boolean;
}

export interface InvoiceRow {
  num: string;
  desc: string;
  descSub: string;
  amount: string;
}
export interface UsageBar {
  label: string;
  used: string;
  limit: string;
  pct: number;
  tone: 'neutral' | 'warn';
}
export interface Swatch {
  color: string;
  title: string;
  active?: boolean;
}

export interface SettingsData {
  summary: {
    network: string;
    branches: string;
    clients: number;
    trainers: number;
    updated: string;
  };
  nav: NavGroup[];
  sessions: SessionRow[];
  audit: AuditRow[];
  team: TeamMember[];
  teamCount: number;
  channels: ChannelRow[];
  integrations: IntegrationRow[];
  swatches: Swatch[];
  planFeatures: string[];
  usage: UsageBar[];
  invoices: InvoiceRow[];
}
