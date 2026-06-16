/**
 * Доменные типы экрана «Отчёты» (Reports.html) — аналитический дашборд:
 * KPI, выручка по дням (area+сравнение), структура выручки (donut), топ-списки.
 */
import type { TrendPoint } from '@/components/charts/AreaTrendChart';

export type ReportKpiIcon = 'revenue' | 'newClients' | 'retention' | 'avgCheck';
export interface ReportKpi {
  id: string;
  icon: ReportKpiIcon;
  label: string;
  value: string;
  unit?: string;
  delta: { label: string; direction: 'up' | 'down' | 'flat' };
  footNote: string;
}

export interface RevenueData {
  bigValue: string;
  deltaLabel: string;
  vsLabel: string;
  points: TrendPoint[];
  ticks: string[];
  yMax: number;
  legend: { aprTotal: string; marTotal: string; bestDay: string; bestVal: string };
}

export interface MixSegment {
  label: string;
  pct: string;
  amount: string;
  value: number;
  color: string;
}
export interface MixData {
  center: { top: string; sub: string; label: string };
  segments: MixSegment[];
  growingLabel: string;
  growingDelta: string;
  cashPct: string;
}

export type BarTone = 'dark' | 'accent' | 'grey';
export interface RankRow {
  id: string;
  rank?: number;
  avatar?: { initials: string; color: string };
  name: string;
  sub: string;
  barPct: number;
  barTone: BarTone;
  amount: string;
  share: string;
}
export interface ListFootSide {
  pre: string;
  strong: string;
  post?: string;
}
export interface RankedListData {
  title: string;
  sub: string;
  linkLabel: string;
  linkTo: string;
  rows: RankRow[];
  footLeft: ListFootSide;
  footRight: ListFootSide;
}

export interface ReportsData {
  periodLabel: string;
  periodDelta: string;
  dateRange: string;
  kpis: ReportKpi[];
  revenue: RevenueData;
  mix: MixData;
  topPlans: RankedListData;
  topTrainers: RankedListData;
}
