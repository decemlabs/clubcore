/**
 * Доменные типы экрана «Загруженность» (Load.html) — occupancy-дашборд:
 * KPI с прогресс-метрами, тёмная карточка «Сейчас» с зонами, heatmap день×час.
 */
import type { HeatRowData } from '@/components/charts/heatmap-utils';

export type LoadKpiIcon = 'now' | 'avg' | 'peak' | 'free';
export type MeterTone = 'accent' | 'warn' | 'neutral';
export type DeltaTone = 'accent' | 'warn' | 'flat';

export interface LoadKpi {
  id: string;
  icon: LoadKpiIcon;
  label: string;
  value: string;
  unit?: string;
  meterPct: number;
  meterTone: MeterTone;
  delta: { label: string; tone: DeltaTone; up?: boolean };
  caption: string;
}

export type ZoneTone = 'accent' | 'warn' | 'low';
export interface ZoneRow {
  name: string;
  /** Мета (жирная часть — отдельным полем для рендера). */
  metaStrong: string;
  metaRest: string;
  barPct: number;
  tone: ZoneTone;
  pct: string;
  pctWarn?: boolean;
}

export interface LiveData {
  time: string;
  current: number;
  capacity: number;
  meterPct: number;
  filledPct: string;
  dayVisits: number;
  zones: ZoneRow[];
}

export interface LoadHeatmapData {
  hours: string[];
  rows: HeatRowData[];
  freeSlots: number;
  marketingWindow: string;
}

export interface LoadData {
  subtitleAvg: string;
  subtitlePeak: string;
  kpis: LoadKpi[];
  live: LiveData;
  heatmap: LoadHeatmapData;
}
