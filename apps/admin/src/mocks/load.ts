/**
 * Сид-данные экрана «Загруженность». Портированы из Load.html: KPI, «Сейчас»
 * с зонами, heatmap день×час (7×17, % от вместимости 80).
 */
import type { HeatLevel, HeatRowData } from '@/components/charts/heatmap-utils';
import type { LoadData } from '@/features/load/types';

const HOURS = [
  '7',
  '8',
  '9',
  '10',
  '11',
  '12',
  '13',
  '14',
  '15',
  '16',
  '17',
  '18',
  '19',
  '20',
  '21',
  '22',
  '23',
];
const NOW_HOUR_IDX = 9; // 16:00

/** Матрица % загрузки по дням × часам. */
const MATRIX: [string, number[], boolean?][] = [
  ['Пн', [25, 55, 45, 30, 22, 28, 32, 40, 48, 52, 65, 82, 90, 86, 70, 42, 18]],
  ['Вт', [30, 60, 50, 32, 24, 30, 34, 42, 52, 60, 72, 86, 92, 92, 76, 46, 22]],
  ['Ср', [28, 58, 50, 33, 24, 28, 32, 40, 50, 53, 68, 84, 90, 88, 72, 44, 20], true],
  ['Чт', [30, 60, 50, 32, 24, 30, 34, 42, 52, 60, 72, 86, 92, 90, 74, 46, 22]],
  ['Пт', [26, 52, 44, 28, 22, 26, 30, 38, 46, 52, 64, 80, 85, 82, 68, 52, 32]],
  ['Сб', [12, 28, 45, 62, 72, 75, 68, 60, 52, 46, 42, 40, 36, 32, 28, 18, 8], false],
  ['Вс', [10, 22, 40, 58, 68, 70, 62, 54, 46, 40, 36, 34, 30, 26, 22, 14, 6]],
];

function mapLevel(p: number): HeatLevel {
  if (p < 12) return 0;
  if (p < 30) return 1;
  if (p < 50) return 2;
  if (p < 70) return 3;
  if (p < 90) return 5;
  return 6;
}

const heatRows: HeatRowData[] = MATRIX.map(([label, pcts, today]) => ({
  label,
  weekend: label === 'Сб' || label === 'Вс',
  cells: pcts.map((p, i) => ({
    level: mapLevel(p),
    now: today === true && i === NOW_HOUR_IDX,
    text: p >= 30 ? `${p}%` : '',
    title: `${label} ${HOURS[i]}:00 · ${p}% · ${Math.round(p * 0.8)} чел`,
  })),
}));

export const loadData: LoadData = {
  subtitleAvg: '64%',
  subtitlePeak: 'вт и чт 20:00',

  kpis: [
    {
      id: 'now',
      icon: 'now',
      label: 'Сейчас в клубе',
      value: '42',
      unit: '/ 80',
      meterPct: 52.5,
      meterTone: 'accent',
      delta: { label: '53%', tone: 'accent' },
      caption: 'заполнено',
    },
    {
      id: 'avg',
      icon: 'avg',
      label: 'Средняя за неделю',
      value: '64',
      unit: '%',
      meterPct: 64,
      meterTone: 'accent',
      delta: { label: '+6 п.п.', tone: 'accent', up: true },
      caption: 'к прошлой',
    },
    {
      id: 'peak',
      icon: 'peak',
      label: 'Пиковая загрузка',
      value: '92',
      unit: '%',
      meterPct: 92,
      meterTone: 'warn',
      delta: { label: 'вт · 20:00', tone: 'warn' },
      caption: '74 человека',
    },
    {
      id: 'free',
      icon: 'free',
      label: 'Свободно сейчас',
      value: '38',
      unit: ' мест',
      meterPct: 47.5,
      meterTone: 'neutral',
      delta: { label: 'тихо', tone: 'flat' },
      caption: 'пик через ~3 ч',
    },
  ],

  live: {
    time: '16:42',
    current: 42,
    capacity: 80,
    meterPct: 52.5,
    filledPct: '53%',
    dayVisits: 87,
    zones: [
      {
        name: 'Тренажёрный зал',
        metaStrong: '31',
        metaRest: ' / 60 чел · 5 свободных кардио',
        barPct: 51.6,
        tone: 'accent',
        pct: '52%',
      },
      {
        name: 'Студия групповых',
        metaStrong: '8',
        metaRest: ' / 12 чел · идёт йога',
        barPct: 66.6,
        tone: 'warn',
        pct: '67%',
        pctWarn: true,
      },
      {
        name: 'Сауна',
        metaStrong: '3',
        metaRest: ' / 8 чел',
        barPct: 37.5,
        tone: 'low',
        pct: '38%',
      },
      {
        name: 'Душевые / раздевалки',
        metaStrong: '',
        metaRest: 'средняя очередь — 0 мин',
        barPct: 28,
        tone: 'low',
        pct: '28%',
      },
    ],
  },

  heatmap: { hours: HOURS, rows: heatRows, freeSlots: 312, marketingWindow: 'будни 11–15' },
};
