/**
 * Доменные типы раздела «Филиалы» (Branches.html + Branch-Settings.html).
 * Один тип `Branch` обслуживает и карточку списка, и детальную форму настроек.
 * Цвета марок/аватаров — per-entity градиенты (из данных), не токены.
 */

export type BranchStatus = 'active' | 'soon' | 'paused';

export interface WorkingDay {
  /** Пн … Вс. */
  day: string;
  open: string;
  close: string;
  closed: boolean;
}

export type ZoneKind = 'group' | 'personal' | 'cardio';
export interface Zone {
  id: string;
  name: string;
  sub: string;
  /** Подпись вместимости, напр. «до 16 чел». */
  capacity: string;
  kind: ZoneKind;
}

export interface BranchPayments {
  trainerCommissionPct: number;
  acquiring: string;
  acceptCash: boolean;
  payByLink: boolean;
  installments: boolean;
}

export interface BranchNotifications {
  workoutReminder: boolean;
  membershipExpiry: boolean;
  promos: boolean;
}

export interface BranchManager {
  name: string;
  initials: string;
  /** CSS-градиент аватара (per-entity). */
  gradient: string;
}

export interface Branch {
  id: string;
  /** Код филиала, напр. «BR-TVER». */
  code: string;
  name: string;
  /** Буква-марка. */
  mark: string;
  /** CSS-градиент марки (per-entity). */
  gradient: string;
  status: BranchStatus;
  city: string;
  metro: string;
  /** Улица/дом (без префикса метро). */
  addr: string;
  phone: string;
  timezone: string;
  /** null — управляющий не назначен (филиал «скоро»). */
  manager: BranchManager | null;

  clients: number;
  trainers: number;
  /** Заполняемость, %. */
  occ: number;
  /** Выручка за месяц, ₽. */
  mrr: number;
  /** Подпись для филиала «скоро», напр. «Открытие 1 июня». */
  opening?: string;

  /* ---- детальная форма настроек ---- */
  hours: WorkingDay[];
  zones: Zone[];
  payments: BranchPayments;
  notifications: BranchNotifications;
}

export interface BranchesSummary {
  branchesActive: number;
  branchesUpcoming: number;
  clientsTotal: number;
  trainersTotal: number;
  revenueApril: number;
}

export interface BranchesData {
  summary: BranchesSummary;
  branches: Branch[];
}
