/**
 * Доменные типы экрана «Финансы» (Finance.html).
 * KPI-полоса + 3 вкладки таблиц (реестр / неудачные / выплаты) + модалки.
 * Без графиков. Цвета аватаров — per-entity градиенты (из данных), не токены.
 */

export type RegStatus = 'ok' | 'refund' | 'pending';

export interface RegRow {
  id: string;
  date: string;
  time: string;
  initials: string;
  gradient: string;
  name: string;
  desc: string;
  method: string;
  amount: number;
  status: RegStatus;
}

export interface FailRow {
  id: string;
  date: string;
  time: string;
  initials: string;
  gradient: string;
  name: string;
  phone: string;
  reason: string;
  amount: number;
}

export type PayStatus = 'pending' | 'paid';

export interface PayRow {
  id: string;
  initials: string;
  gradient: string;
  name: string;
  spec: string;
  accrued: number;
  payout: number;
  status: PayStatus;
}

export interface FinanceData {
  kpi: { turnover: number; success: number; failed: number; payout: number };
  reg: RegRow[];
  regCount: number;
  fail: FailRow[];
  failCount: number;
  pay: PayRow[];
  payoutTotal: number;
  payoutTrainers: number;
}
