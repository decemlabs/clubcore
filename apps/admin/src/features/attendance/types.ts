/**
 * Доменные типы экрана «Посещаемость» (Attendance.html) — аналитический дашборд:
 * heatmap день×час, кривая по часам, сегменты частоты, день недели, длительность,
 * когортное удержание, аномалии, список риска оттока.
 */
import type { HeatRowData } from '@/components/charts/heatmap-utils';

export type AttKpiIcon = 'visits' | 'active' | 'avg' | 'noshow';
export interface AttKpi {
  id: string;
  icon: AttKpiIcon;
  label: string;
  value: string;
  unit?: string;
  delta: { label: string; direction: 'up' | 'down' | 'flat' };
  foot: { pre: string; strong?: string; post?: string };
}

export interface HeatmapData {
  hours: string[];
  rows: HeatRowData[];
  windows: number;
  overload: number;
  quietest: string;
  now: string;
}

export interface PeakStat {
  label: string;
  value: string;
}
export interface PeakHeroData {
  when: string;
  whenSub: string;
  bodyPre: string;
  bodyAvg: string;
  bodyMid: string;
  bodyDays: string;
  bodyPost: string;
  stats: PeakStat[];
}

export interface CurvePoint {
  hour: string;
  today: number;
  weekday: number;
  weekend: number;
}
export interface HourCurveData {
  points: CurvePoint[];
  capacity: number;
  nowHour: string;
  nowValue: number;
  peakHour: string;
  peakValue: number;
}

export interface FreqSegment {
  color: string;
  name: string;
  sub: string;
  count: number;
  pct: string;
}
export interface FrequencyData {
  total: number;
  segments: FreqSegment[];
}

export interface DowBar {
  day: string;
  value: number;
  pct: number;
  note: string;
  peak?: boolean;
  now?: boolean;
  nowPct?: number;
}

export interface DurationBucket {
  label: string;
  pct: number;
  share: string;
  peak?: boolean;
}
export interface DurationData {
  donutPct: number;
  centerValue: string;
  median: string;
  notes: { pre: string; strong: string; post?: string }[];
  buckets: DurationBucket[];
}

export interface CohortRow {
  label: string;
  size: number;
  values: (number | null)[];
}
export interface CohortData {
  weeks: string[];
  rows: CohortRow[];
  footPre: string;
  footAvg: string;
  footMid: string;
  footGoal: string;
  footPost: string;
}

export type AnomalyTone = 'warn' | 'ok' | 'info';
export interface Anomaly {
  tone: AnomalyTone;
  title: string;
  body: string;
}

export type RiskScore = 'high' | 'med' | 'low';
export interface RiskClient {
  id: string;
  initials: string;
  color: string;
  name: string;
  meta: string;
  trend: string;
  score: RiskScore;
}

export interface AttendanceData {
  subtitle: { period: string; visits: string; avg: string; live: string };
  kpis: AttKpi[];
  heatmap: HeatmapData;
  peak: PeakHeroData;
  curve: HourCurveData;
  frequency: FrequencyData;
  dow: DowBar[];
  duration: DurationData;
  cohort: CohortData;
  anomalies: Anomaly[];
  risk: { count: number; total: number; rows: RiskClient[] };
}
