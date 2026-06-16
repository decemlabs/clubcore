/**
 * Сид-данные экрана «Посещаемость». Портированы из Attendance.html.
 */
import type { HeatLevel, HeatRowData } from '@/components/charts/heatmap-utils';
import type { AttendanceData } from '@/features/attendance/types';

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

/** [день, выходной?, уровни 17 часов, индекс ячейки «сейчас»]. */
const MATRIX: [string, boolean, HeatLevel[], number?][] = [
  ['Пн', false, [3, 4, 3, 2, 2, 1, 1, 1, 2, 3, 4, 5, 'over', 6, 4, 2, 1]],
  ['Вт', false, [3, 4, 3, 2, 2, 2, 1, 2, 2, 3, 4, 5, 5, 5, 3, 2, 1]],
  ['Ср', false, [2, 3, 3, 2, 1, 1, 1, 1, 2, 3, 4, 5, 'over', 6, 4, 2, 1]],
  ['Чт', false, [3, 4, 3, 2, 2, 2, 1, 2, 3, 4, 5, 'over', 'over', 5, 3, 2, 0]],
  ['Пт', false, [3, 4, 2, 1, 1, 1, 1, 2, 2, 3, 4, 5, 5, 4, 2, 1, 'closed'], 10],
  ['Сб', true, ['closed', 'closed', 2, 4, 5, 'over', 'over', 5, 4, 3, 3, 3, 2, 2, 2, 1, 'closed']],
  ['Вс', true, ['closed', 'closed', 1, 3, 4, 5, 4, 3, 3, 2, 2, 2, 2, 1, 1, 0, 'closed']],
];

const heatRows: HeatRowData[] = MATRIX.map(([label, weekend, levels, nowIdx]) => ({
  label,
  weekend,
  cells: levels.map((level, i) => ({ level, now: i === nowIdx })),
}));

export const attendanceData: AttendanceData = {
  subtitle: {
    period: '1 — 16 мая 2026',
    visits: '4 218',
    avg: '2.4 / нед',
    live: '42 в зале сейчас',
  },

  kpis: [
    {
      id: 'visits',
      icon: 'visits',
      label: 'Визитов в мае',
      value: '4 218',
      delta: { label: '+14%', direction: 'up' },
      foot: { pre: 'к апрелю · цель ', strong: '4 500' },
    },
    {
      id: 'active',
      icon: 'active',
      label: 'Активные клиенты',
      value: '621',
      unit: '/ 847',
      delta: { label: '73%', direction: 'up' },
      foot: { pre: 'хотя бы 1 визит за месяц' },
    },
    {
      id: 'avg',
      icon: 'avg',
      label: 'Среднее на клиента',
      value: '2.4',
      unit: '/ нед',
      delta: { label: '+0.3', direction: 'up' },
      foot: { pre: 'пик в марте — ', strong: '2.6' },
    },
    {
      id: 'noshow',
      icon: 'noshow',
      label: 'Неявки на ПТ',
      value: '4.8',
      unit: '%',
      delta: { label: '−1.2 п.п.', direction: 'up' },
      foot: { pre: '18 из 374 ПТ · ', strong: '21', post: ' отмена' },
    },
  ],

  heatmap: {
    hours: HOURS,
    rows: heatRows,
    windows: 119,
    overload: 14,
    quietest: 'Пн 13:00',
    now: 'Пт 17:00',
  },

  peak: {
    when: '19:00',
    whenSub: 'пн—чт',
    bodyPre: 'В среднем ',
    bodyAvg: '58 чел',
    bodyMid: ' в зале · превышает вместимость ',
    bodyDays: '4 дня',
    bodyPost: ' из 7 за неделю.',
    stats: [
      { label: 'Самое тихое', value: 'Пн 13:00 · 10 чел' },
      { label: 'Самый «жирный» день', value: 'Чт · 712 виз / нед' },
      { label: 'Утренний клуб', value: '7–9 ч · +18% к апр' },
      { label: 'Выходные', value: '11–13 ч · пик сб' },
    ],
  },

  curve: {
    points: [
      { hour: '7', today: 20, weekday: 22, weekend: 8 },
      { hour: '8', today: 30, weekday: 30, weekend: 14 },
      { hour: '9', today: 32, weekday: 34, weekend: 24 },
      { hour: '10', today: 28, weekday: 30, weekend: 30 },
      { hour: '11', today: 26, weekday: 28, weekend: 34 },
      { hour: '12', today: 30, weekday: 32, weekend: 32 },
      { hour: '13', today: 33, weekday: 30, weekend: 28 },
      { hour: '14', today: 31, weekday: 28, weekend: 24 },
      { hour: '15', today: 36, weekday: 32, weekend: 22 },
      { hour: '16', today: 40, weekday: 38, weekend: 20 },
      { hour: '17', today: 39, weekday: 44, weekend: 18 },
      { hour: '18', today: 52, weekday: 52, weekend: 16 },
      { hour: '19', today: 64, weekday: 58, weekend: 14 },
      { hour: '20', today: 56, weekday: 56, weekend: 12 },
      { hour: '21', today: 44, weekday: 48, weekend: 10 },
      { hour: '22', today: 28, weekday: 30, weekend: 8 },
      { hour: '23', today: 14, weekday: 16, weekend: 6 },
    ],
    capacity: 60,
    nowHour: '17',
    nowValue: 39,
    peakHour: '19',
    peakValue: 64,
  },

  frequency: {
    total: 847,
    segments: [
      {
        color: '#0f9b76',
        name: 'Фанаты · 4+ / нед',
        sub: 'в среднем 4.8 визита · 21 ПТ в мес',
        count: 142,
        pct: '17%',
      },
      {
        color: '#2dd4a4',
        name: 'Регулярные · 2–3 / нед',
        sub: 'среднее ядро зала · доход 60% выручки',
        count: 318,
        pct: '38%',
      },
      {
        color: '#a8a29e',
        name: 'Эпизодические · 1 / нед',
        sub: 'обычно групповая или партнёрский визит',
        count: 224,
        pct: '26%',
      },
      {
        color: '#e9a23b',
        name: 'Редкие · 1–3 за месяц',
        sub: 'под угрозой — обычно не продлевают',
        count: 89,
        pct: '11%',
      },
      {
        color: '#dc2626',
        name: 'Спящие · 0 за месяц',
        sub: 'абонемент активен, но не ходят',
        count: 74,
        pct: '9%',
      },
    ],
  },

  dow: [
    { day: 'Пн', value: 684, pct: 76, note: '3 нед' },
    { day: 'Вт', value: 658, pct: 73, note: '3 нед' },
    { day: 'Ср', value: 672, pct: 74, note: '3 нед' },
    { day: 'Чт', value: 712, pct: 100, note: 'топ', peak: true },
    { day: 'Пт', value: 498, pct: 58, note: 'сегодня', now: true, nowPct: 60 },
    { day: 'Сб', value: 524, pct: 62, note: 'выходной' },
    { day: 'Вс', value: 470, pct: 55, note: 'выходной' },
  ],

  duration: {
    donutPct: 62,
    centerValue: '68',
    median: '68',
    notes: [
      { pre: 'У клиентов с ПТ — ', strong: '82 мин', post: '.' },
      { pre: 'Без ПТ — ', strong: '54 мин', post: '.' },
      { pre: '«Кросс-вечер» Денис, чт 20:00 — ', strong: '110 мин', post: '.' },
    ],
    buckets: [
      { label: '<30', pct: 18, share: '10%' },
      { label: '30–45', pct: 32, share: '14%' },
      { label: '45–60', pct: 58, share: '18%' },
      { label: '60–75', pct: 100, share: '22%', peak: true },
      { label: '75–90', pct: 88, share: '17%', peak: true },
      { label: '90–105', pct: 60, share: '11%' },
      { label: '105–120', pct: 28, share: '6%' },
      { label: '120+', pct: 12, share: '2%' },
    ],
  },

  cohort: {
    weeks: ['1 нед', '2 нед', '3 нед', '4 нед', '6 нед', '8 нед', '12 нед', '24 нед'],
    rows: [
      { label: 'Сен 2024', size: 62, values: [94, 86, 74, 68, 58, 52, 44, 38] },
      { label: 'Окт 2024', size: 78, values: [96, 88, 82, 72, 64, 54, 46, 41] },
      { label: 'Янв 2025', size: 104, values: [92, 81, 68, 54, 47, 40, 34, 28] },
      { label: 'Фев 2025', size: 88, values: [95, 84, 78, 66, 58, 49, 42, null] },
      { label: 'Дек 2025', size: 142, values: [98, 90, 84, 76, 68, 62, null, null] },
      { label: 'Янв 2026', size: 96, values: [94, 82, 76, 64, 58, null, null, null] },
      { label: 'Фев 2026', size: 118, values: [96, 85, 78, 66, null, null, null, null] },
      { label: 'Апр 2026', size: 84, values: [98, 92, 82, null, null, null, null, null] },
    ],
    footPre: 'Среднее удержание на 4-й неделе: ',
    footAvg: '67%',
    footMid: ' · цель ',
    footGoal: '75%',
    footPost: '. Слабое место — 3–4 нед у клиентов без ПТ.',
  },

  anomalies: [
    {
      tone: 'warn',
      title: 'Перегруз в 19:00 · 4 раза за неделю',
      body: 'Зал был выше 60 чел в пн, ср, чт, пт. Стойки 3, 5, 7 простаивают >15 мин в очереди. Подумайте о вечернем доп. кросс-классе в студии.',
    },
    {
      tone: 'ok',
      title: 'Утренний клуб растёт +18%',
      body: 'Окно 7–9 утра прирастает 4 нед подряд. 38 регулярных «жаворонков» — кандидаты на годовую скидку в утренние слоты.',
    },
    {
      tone: 'info',
      title: '28 клиентов «затихли» 14+ дней',
      body: 'Из них 11 — постоянные клиенты >6 мес. Авто-сценарий пуша «как дела, давно не виделись» не отправлялся. Включить?',
    },
  ],

  risk: {
    count: 12,
    total: 28,
    rows: [
      {
        id: 'r1',
        initials: 'ОИ',
        color: '#0ea5e9',
        name: 'Олег Ивлев',
        meta: 'Месячный · клиент 7 мес · обычно 3.2/нед · последний визит 19 дней назад',
        trend: '−68%',
        score: 'high',
      },
      {
        id: 'r2',
        initials: 'КЛ',
        color: '#f59e0b',
        name: 'Карина Левчук',
        meta: 'Полугодовой · клиент 2 года · обычно 4.5/нед · последний визит 14 дней назад · абонемент истекает 3 мая',
        trend: '−74%',
        score: 'high',
      },
      {
        id: 'r3',
        initials: 'ЮЗ',
        color: '#a855f7',
        name: 'Юлия Зайцева',
        meta: 'Месячный · клиент 11 мес · обычно 2.8/нед · последний визит 11 дней назад · 2 отмены ПТ подряд',
        trend: '−52%',
        score: 'high',
      },
      {
        id: 'r4',
        initials: 'АШ',
        color: '#10b981',
        name: 'Артур Шах',
        meta: 'Месячный · клиент 4 мес · обычно 2.5/нед · последний визит 9 дней назад',
        trend: '−44%',
        score: 'med',
      },
      {
        id: 'r5',
        initials: 'НС',
        color: '#6366f1',
        name: 'Никита Сюй',
        meta: 'Годовой · клиент 1 год · обычно 3.0/нед · последний визит 8 дней назад · травма колена 22 апр',
        trend: '−38%',
        score: 'med',
      },
      {
        id: 'r6',
        initials: 'МК',
        color: '#dc2626',
        name: 'Маша Конева',
        meta: 'Месячный · клиент 6 мес · обычно 2.2/нед · последний визит 6 дней назад',
        trend: '−32%',
        score: 'med',
      },
    ],
  },
};
