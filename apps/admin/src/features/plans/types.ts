/**
 * Доменные типы экрана «Абонементы и тарифы». Портированы из Plans.html как design-spec:
 * каталог тарифов (карточки-прайсы), продажи по тарифам (стек-бары), акции, доп. услуги.
 */

/* ---------- KPI ---------- */
export type PlanKpiIcon = 'subs' | 'mrr' | 'avg' | 'funnel';
export type PlanKpiValueKind = 'int' | 'percent';

export interface PlanKpi {
  id: string;
  icon: PlanKpiIcon;
  label: string;
  value: number;
  valueKind: PlanKpiValueKind;
  unit?: string;
  delta?: { label: string; direction: 'up' | 'down' | 'flat' };
  footNote?: string;
  chips?: { label: string; tone: 'neutral' | 'accent' | 'warn' }[];
}

/* ---------- Вкладки ---------- */
export type PlanTab = 'tariffs' | 'subs' | 'promos' | 'addons' | 'archive';
export interface PlanFilterTab {
  tab: PlanTab;
  label: string;
  count: number;
}

/* ---------- Тарифы ---------- */
export interface TariffFeature {
  text: string;
  included: boolean;
}
export interface TariffBadge {
  kind: 'hit' | 'deal';
  label: string;
}
export interface TariffStat {
  label: string;
  value: string;
  foot: string;
  /** Зелёный «вверх» футноут. */
  footUp?: boolean;
}
export interface Tariff {
  id: string;
  name: string;
  tag: string;
  badge?: TariffBadge;
  popular?: boolean;
  priceBig: string;
  per: string;
  days: string;
  sumLabel: string;
  features: TariffFeature[];
  stats: TariffStat[];
}

/* ---------- Продажи по тарифам ---------- */
export type SalesSegKey = 'annual' | 'half' | 'month';
export interface SalesMonth {
  label: string;
  count: number;
  revenueK: number;
  /** Доли сегментов (annual/half/month), сумма ≈ 1. */
  seg: Record<SalesSegKey, number>;
  current?: boolean;
}
export interface SalesLegendItem {
  key: SalesSegKey;
  label: string;
  value: number;
}
export interface SalesChart {
  months: SalesMonth[];
  legend: SalesLegendItem[];
  conversion: string;
}

/* ---------- Акции ---------- */
export type PromoIconKind = 'discount' | 'gift' | 'student' | 'percent';
export type PromoStatus = 'active' | 'paused';
export interface PromoStat {
  label: string;
  value: string;
}
export interface Promo {
  id: string;
  iconKind: PromoIconKind;
  title: string;
  /** Моно-чип кода, напр. «LETO2026». */
  codeChip?: string;
  status: PromoStatus;
  statusLabel: string;
  sub: string;
  stats: PromoStat[];
  actions: { label: string; primary?: boolean }[];
}

/* ---------- Доп. услуги ---------- */
export type AddonIconKind = 'sauna' | 'guest' | 'towel' | 'shaker' | 'freeze';
export interface Addon {
  id: string;
  iconKind: AddonIconKind;
  title: string;
  sub: string;
  price: string;
  unit: string;
  on: boolean;
}

/* ---------- Сводка страницы ---------- */
export interface PlansSummary {
  activeSubs: number;
  mrr: number;
  tariffCount: number;
}

export interface PlansPageData {
  summary: PlansSummary;
  kpis: PlanKpi[];
  tabs: PlanFilterTab[];
  tariffs: Tariff[];
  sales: SalesChart;
  promos: Promo[];
  addons: Addon[];
}
