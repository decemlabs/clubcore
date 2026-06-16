/**
 * Доменные типы экрана «Касса». Портированы из Cashbox.html (State A — открытая смена):
 * KPI смены, лента операций, тёмная карточка-«ящик» смены. Открытость смены — состояние.
 */

export type TxCategory = 'membership' | 'bar' | 'pt' | 'refund' | 'cashin';
export type TxMethod = 'card' | 'cash' | 'transfer' | 'refund';
export type TxFilter = 'all' | 'membership' | 'pt' | 'bar' | 'refund';

export interface Transaction {
  id: string;
  time: string;
  ago: string;
  category: TxCategory;
  title: string;
  client: string;
  note?: string;
  method: TxMethod;
  methodLabel: string;
  /** Хвост карты, напр. «•0421». */
  methodTail?: string;
  /** Сумма, ₽ (отрицательная — возврат). */
  amount: number;
  /** Приглушённая сумма (служебное внесение). */
  muted?: boolean;
  /** Номер чека/акта, напр. «чек №0047». */
  doc: string;
}

export interface TxFilterChip {
  filter: TxFilter;
  label: string;
  count: number;
}

/* ---------- KPI ---------- */
export type CashKpiIcon = 'revenue' | 'cash' | 'card' | 'refund';
export interface CashKpi {
  id: string;
  icon: CashKpiIcon;
  label: string;
  /** Готовое значение, напр. «184 200» (или «−4 800»). */
  value: string;
  unit?: string;
  valueDanger?: boolean;
  delta?: { label: string; direction: 'up' | 'down' | 'flat' };
  footNote?: string;
}

/* ---------- Смена (тёмная карточка) ---------- */
export interface PayMethodRow {
  method: TxMethod;
  label: string;
  sub: string;
  amount: number;
  pct: string;
  danger?: boolean;
}
export interface Shift {
  cashier: string;
  cashierInitials: string;
  openedAt: string;
  duration: string;
  drawerTotal: number;
  startCash: number;
  expectedCash: number;
  pay: PayMethodRow[];
}

export interface CashboxData {
  shift: Shift;
  kpis: CashKpi[];
  filters: TxFilterChip[];
  transactions: Transaction[];
  txTotal: number;
  txCount: number;
}
