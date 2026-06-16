import type {
  ActivityFeedData,
  DashboardData,
  DashboardOverview,
  ExpiringList,
  HourlyOccupancy,
  OccupancyNow,
  RevenueData,
  RevenuePoint,
  RevenueSeries,
  ScheduleToday,
  TopTrainer,
  ClientMessage,
} from '@/features/dashboard/types';

/* Палитра инициалов — те же оттенки, что в референсе. */
const C = {
  sky: '#0ea5e9',
  violet: '#a855f7',
  amber: '#f59e0b',
  emerald: '#10b981',
  indigo: '#6366f1',
  red: '#dc2626',
} as const;

/** Сид-данные дашборда. Значения портированы из Dashboard.html. */
export const dashboardOverview: DashboardOverview = {
  dateLabel: 'Среда, 30 апреля',
  greetingName: 'Маша',
  trainingsToday: 28,
  expectedVisits: 112,
  defaultPeriod: 'week',
  kpis: [
    {
      id: 'members',
      label: 'Активных абонементов',
      icon: 'members',
      value: 847,
      delta: { label: '+34', direction: 'up' },
      footNote: 'за неделю',
    },
    {
      id: 'revenue',
      label: 'Выручка сегодня',
      icon: 'revenue',
      value: 184200,
      unit: '₽',
      delta: { label: '+12%', direction: 'up' },
      footNote: 'к прошлой Ср',
    },
    {
      id: 'trainings',
      label: 'Тренировок сегодня',
      icon: 'trainings',
      value: 28,
      chips: [
        { label: '12 завершено', tone: 'neutral' },
        { label: '2 идут', tone: 'accent' },
      ],
    },
    {
      id: 'visits',
      label: 'Визиты сегодня',
      icon: 'visits',
      value: 86,
      unit: '/ 112',
      delta: { label: '+8%', direction: 'up' },
      footNote: 'к прошлой Ср',
    },
  ],
};

/* ---------- Заполняемость по часам (7:00 → 23:00) ---------- */

const HOUR_HEIGHTS: { value: number; state: 'past' | 'now' | 'future' }[] = [
  { value: 30, state: 'past' },
  { value: 52, state: 'past' },
  { value: 64, state: 'past' },
  { value: 58, state: 'past' },
  { value: 38, state: 'past' },
  { value: 26, state: 'past' },
  { value: 32, state: 'past' },
  { value: 40, state: 'past' },
  { value: 46, state: 'past' },
  { value: 53, state: 'now' },
  { value: 62, state: 'future' },
  { value: 78, state: 'future' },
  { value: 88, state: 'future' },
  { value: 92, state: 'future' },
  { value: 74, state: 'future' },
  { value: 50, state: 'future' },
  { value: 22, state: 'future' },
];

export const hourlyOccupancy: HourlyOccupancy = {
  bars: HOUR_HEIGHTS.map((b, i) => ({ hour: 7 + i, value: b.value, state: b.state })),
  subtitle: 'Сегодня · ср, 30 апр · обновлено 2 мин назад',
  peakHour: '20:00',
  peakCount: 74,
};

/* ---------- Живая заполняемость ---------- */

export const occupancyNow: OccupancyNow = {
  current: 42,
  capacity: 80,
  faces: [
    { initials: 'МЛ', color: C.sky },
    { initials: 'ЛО', color: C.violet },
    { initials: 'КЛ', color: C.amber },
    { initials: 'АШ', color: C.emerald },
    { initials: 'НС', color: C.indigo },
  ],
  moreCount: 37,
  cells: [
    { label: 'Обычно сейчас', value: 35, barPct: 44, muted: true },
    { label: 'Сейчас', value: 42, barPct: 53, delta: '↑ 20%' },
    { label: 'Пик · 20:00', value: 74, barPct: 93, muted: true },
  ],
  fillPct: 53,
  dayVisits: 87,
};

/* ---------- Расписание тренировок ---------- */

export const scheduleToday: ScheduleToday = {
  nowLabel: '15:42 · сейчас',
  total: 28,
  done: 12,
  live: 2,
  planned: 14,
  sessions: [
    {
      id: 's1',
      time: '09:00',
      duration: '60 мин',
      initials: 'АС',
      color: C.amber,
      type: 'pt',
      who: 'Аня Соколова',
      whatBold: 'Карина Левчук',
      whatRest: ' · ноги + спина',
      state: 'done',
      stateLabel: 'Завершена',
    },
    {
      id: 's2',
      time: '10:30',
      duration: '75 мин',
      initials: 'ЛО',
      color: C.violet,
      type: 'gr',
      who: 'Лиза Орлова · йога',
      whatBold: '8/10',
      whatRest: ' человек · зал 2',
      state: 'done',
      stateLabel: 'Завершена',
    },
    {
      id: 's3',
      time: '13:00',
      duration: '60 мин',
      initials: 'МЛ',
      color: C.sky,
      type: 'pt',
      who: 'Марк Левин',
      whatBold: 'Иван Гранин',
      whatRest: ' · функционал',
      state: 'done',
      stateLabel: 'Завершена',
    },
    {
      id: 's4',
      time: '15:30',
      duration: '60 мин',
      initials: 'АС',
      color: C.amber,
      type: 'pt',
      who: 'Аня Соколова',
      whatBold: 'Маша Конева',
      whatRest: ' · грудь + руки',
      state: 'live',
      stateLabel: 'осталось 18 мин',
    },
    {
      id: 's5',
      time: '15:30',
      duration: '75 мин',
      initials: 'СБ',
      color: C.emerald,
      type: 'gr',
      who: 'Соня Бек · пилатес',
      whatBold: '6/8',
      whatRest: ' человек · зал 1',
      state: 'live',
      stateLabel: 'осталось 33 мин',
    },
    {
      id: 's6',
      time: '18:00',
      duration: '60 мин',
      initials: 'АС',
      color: C.amber,
      type: 'pt',
      who: 'Аня Соколова',
      whatBold: 'Олег Ивлев',
      whatRest: ' · силовая',
      state: 'planned',
      stateLabel: 'через 2 ч',
    },
    {
      id: 's7',
      time: '19:00',
      duration: '60 мин',
      initials: 'ИР',
      color: C.indigo,
      type: 'pt',
      who: 'Игорь Раш',
      whatBold: 'Никита Сюй',
      whatRest: ' · бодибилдинг',
      state: 'planned',
      stateLabel: 'через 3 ч',
    },
    {
      id: 's8',
      time: '20:00',
      duration: '75 мин',
      initials: 'ДК',
      color: C.red,
      type: 'gr',
      who: 'Денис Кравцов · бокс',
      whatBold: '10/12',
      whatRest: ' человек · ринг',
      state: 'group',
      stateLabel: 'через 4 ч',
    },
  ],
};

/* ---------- Истекающие абонементы ---------- */

export const expiringList: ExpiringList = {
  daysAhead: 14,
  totalClients: 18,
  items: [
    {
      id: 'e1',
      initials: 'ОИ',
      color: C.sky,
      name: 'Олег Ивлев',
      meta: 'Месячный · клиент 7 мес · 4 900 ₽',
      whenTop: 'через 2 дня',
      whenDate: '2 мая',
      urgency: 'urgent',
    },
    {
      id: 'e2',
      initials: 'КЛ',
      color: C.amber,
      name: 'Карина Левчук',
      meta: 'Полугодовой · клиент 2 года · 24 600 ₽',
      whenTop: 'через 3 дня',
      whenDate: '3 мая',
      urgency: 'urgent',
    },
    {
      id: 'e3',
      initials: 'ЮЗ',
      color: C.violet,
      name: 'Юлия Зайцева',
      meta: 'Месячный · клиент 11 мес · 4 900 ₽',
      whenTop: 'через 5 дней',
      whenDate: '5 мая',
      urgency: 'soon',
    },
    {
      id: 'e4',
      initials: 'АШ',
      color: C.emerald,
      name: 'Артур Шах',
      meta: 'Месячный · клиент 4 мес · 4 900 ₽',
      whenTop: 'через 9 дней',
      whenDate: '9 мая',
      urgency: 'soon',
    },
    {
      id: 'e5',
      initials: 'НС',
      color: C.indigo,
      name: 'Никита Сюй',
      meta: 'Годовой · клиент 1 год · 42 000 ₽',
      whenTop: 'через 11 дней',
      whenDate: '11 мая',
      urgency: 'normal',
    },
    {
      id: 'e6',
      initials: 'МК',
      color: C.red,
      name: 'Маша Конева',
      meta: 'Месячный · клиент 6 мес · 4 900 ₽',
      whenTop: 'через 13 дней',
      whenDate: '13 мая',
      urgency: 'normal',
    },
  ],
};

/* ---------- Выручка (сид-серии, генераторы портированы из референса) ---------- */

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

/** Детерминированный PRNG — кривая стабильна между загрузками. */
function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function genDaily(
  seed: number,
  n: number,
  base: number,
  trend: number,
  noise: number,
): RevenuePoint[] {
  const rnd = mulberry32(seed);
  const out: RevenuePoint[] = [];
  for (let i = 0; i < n; i++) {
    const day = (i + 2) % 7;
    const wkBoost = day === 0 || day === 6 ? 1.18 : day === 1 ? 0.88 : 1.0;
    const wave = Math.sin(i / 5) * 0.07;
    const v = (base + i * trend) * wkBoost * (1 + wave + (rnd() - 0.5) * noise);
    const d = i + 1;
    out.push({ value: Math.max(0, v), label: `${d} ${MONTHS[3]}`, short: String(d) });
  }
  return out;
}

function genWeekly(
  seed: number,
  n: number,
  base: number,
  trend: number,
  noise: number,
): RevenuePoint[] {
  const rnd = mulberry32(seed);
  const out: RevenuePoint[] = [];
  for (let i = 0; i < n; i++) {
    const v = (base + i * trend) * (1 + Math.sin(i / 4) * 0.08 + (rnd() - 0.5) * noise);
    out.push({ value: Math.max(0, v), label: `Нед. ${i + 1}`, short: `Н${i + 1}` });
  }
  return out;
}

function genMonthly(
  seed: number,
  n: number,
  base: number,
  trend: number,
  noise: number,
): RevenuePoint[] {
  const rnd = mulberry32(seed);
  const out: RevenuePoint[] = [];
  for (let i = 0; i < n; i++) {
    const seasonality = Math.sin(((i + 8) / 12) * Math.PI * 2) * 0.18;
    const v = (base + i * trend) * (1 + seasonality + (rnd() - 0.5) * noise);
    out.push({ value: Math.max(0, v), label: `${MONTHS[i]} ’25`, short: MONTHS[i] ?? '' });
  }
  return out;
}

function breakdown(abon: number, train: number, shop: number) {
  return [
    { label: 'Абонементы', value: abon, color: '#1c1917' },
    { label: 'Тренировки', value: train, color: '#2dd4a4' },
    { label: 'Магазин', value: shop, color: '#e9a23b' },
  ];
}

const revenue30: RevenueSeries = {
  period: '30',
  title: 'Выручка · 30 дней',
  rangeLabel: '1 апр — 30 апр',
  total: 3248600,
  delta: { label: '+18.4%', direction: 'up' },
  deltaSub: 'к март',
  points: genDaily(42, 30, 96000, 1100, 0.22),
  breakdown: breakdown(2248000, 812400, 188200),
  ticksEvery: 5,
};

const revenue90: RevenueSeries = {
  period: '90',
  title: 'Выручка · 90 дней',
  rangeLabel: '1 фев — 30 апр',
  total: 9478200,
  delta: { label: '+22.1%', direction: 'up' },
  deltaSub: 'к Q1',
  points: genWeekly(7, 13, 660000, 14000, 0.12),
  breakdown: breakdown(6412000, 2248700, 817500),
  ticksEvery: 2,
};

const revenueYear: RevenueSeries = {
  period: 'year',
  title: 'Выручка · год',
  rangeLabel: 'май 24 — апр 25',
  total: 38412000,
  delta: { label: '+34.7%', direction: 'up' },
  deltaSub: 'к 2024',
  points: genMonthly(99, 12, 2400000, 95000, 0.08),
  breakdown: breakdown(26880000, 8942000, 2590000),
  ticksEvery: 2,
};

export const revenueData: RevenueData = {
  defaultPeriod: '30',
  series: { '30': revenue30, '90': revenue90, year: revenueYear },
};

/* ---------- Топ тренеры ---------- */

export const topTrainers: TopTrainer[] = [
  {
    id: 't1',
    initials: 'ДК',
    color: C.red,
    name: 'Денис Кравцов',
    barPct: 100,
    meta: '52 сессии · бокс, ММА',
    amountLabel: '145.6К ₽',
    rankLabel: '1 место',
  },
  {
    id: 't2',
    initials: 'АС',
    color: C.amber,
    name: 'Аня Соколова',
    barPct: 79,
    meta: '64 сессии · силовые, функционал',
    amountLabel: '140.8К ₽',
    rankLabel: '2 место',
  },
  {
    id: 't3',
    initials: 'МЛ',
    color: C.sky,
    name: 'Марк Левин',
    barPct: 65,
    meta: '41 сессия · кроссфит',
    amountLabel: '98.4К ₽',
    rankLabel: '3 место',
  },
  {
    id: 't4',
    initials: 'ЛО',
    color: C.violet,
    name: 'Лиза Орлова',
    barPct: 62,
    meta: '48 сессий · йога, стретчинг',
    amountLabel: '96.0К ₽',
    rankLabel: '4 место',
  },
  {
    id: 't5',
    initials: 'ИР',
    color: C.indigo,
    name: 'Игорь Раш',
    barPct: 55,
    meta: '36 сессий · бодибилдинг',
    amountLabel: '90.0К ₽',
    rankLabel: '5 место',
  },
];

/* ---------- Обращения клиентов ---------- */

export const clientMessages: ClientMessage[] = [
  {
    id: 'm1',
    initials: 'КЛ',
    color: C.amber,
    name: 'Карина Левчук',
    time: '4 мин',
    body: 'Маша, можно перенести тренировку с Аней с четверга на пятницу 18:00?',
    unread: true,
  },
  {
    id: 'm2',
    initials: 'ИГ',
    color: C.sky,
    name: 'Иван Гранин',
    time: '12 мин',
    body: 'Уезжаю в командировку. Нужна заморозка абонемента с 5 по 18 мая.',
    unread: true,
  },
  {
    id: 'm3',
    initials: 'ЮЗ',
    color: C.violet,
    name: 'Юлия Зайцева',
    time: '38 мин',
    body: 'Подскажите, сколько стоит гостевой визит для подруги в субботу?',
    unread: true,
  },
  {
    id: 'm4',
    initials: 'МК',
    color: C.emerald,
    name: 'Маша Конева',
    time: '1 ч',
    body: 'Спасибо за вчерашнее. Тренер супер, очень довольна!',
    unread: true,
  },
  {
    id: 'm5',
    initials: 'АШ',
    color: C.red,
    name: 'Артур Шах',
    time: '3 ч',
    body: 'Скоро заканчивается абонемент. Когда удобно подъехать продлить?',
    unread: false,
  },
];

/* ---------- Лента активности ---------- */

export const activityFeed: ActivityFeedData = {
  subtitle: 'Лента событий в реальном времени · все филиалы',
  repliedToday: 12,
  events: [
    {
      id: 'a1',
      type: 'checkin',
      title: 'Никита Сюй пришёл на тренировку',
      subLead: 'Зал · QR',
      timeLabel: 'сейчас',
    },
    {
      id: 'a2',
      type: 'payment',
      title: 'Алина Каплан · оплата',
      subLead: 'Продление · ',
      amount: '5 400 ₽',
      timeLabel: '1 мин',
    },
    {
      id: 'a3',
      type: 'training',
      title: 'Аня Соколова завершила сессию',
      subLead: 'С Иван Гранин · 60 мин',
      timeLabel: '4 мин',
    },
    {
      id: 'a4',
      type: 'signup',
      title: 'Полина Бах оформила абонемент',
      subLead: 'Годовой · ',
      amount: '42 000 ₽',
      timeLabel: '9 мин',
    },
    {
      id: 'a5',
      type: 'cancel',
      title: 'Олег Ивлев отменил тренировку',
      subLead: 'С Марк Левин · ',
      danger: '−1 500 ₽',
      timeLabel: '14 мин',
    },
    {
      id: 'a6',
      type: 'checkin',
      title: 'Мария Конева пришла на тренировку',
      subLead: 'Студия · QR',
      timeLabel: '21 мин',
    },
    {
      id: 'a7',
      type: 'alert',
      title: 'Низкий остаток в кулере',
      subLead: 'Зал — 2 бут.',
      timeLabel: '32 мин',
    },
    {
      id: 'a8',
      type: 'expire',
      title: 'Тимур Ким · абонемент истекает',
      subLead: 'Осталось 2 дн · напомнить?',
      timeLabel: '48 мин',
    },
  ],
};

/** Полная сводка дашборда — резолвится одним хуком. */
export const dashboardData: DashboardData = {
  overview: dashboardOverview,
  hourly: hourlyOccupancy,
  occupancy: occupancyNow,
  schedule: scheduleToday,
  expiring: expiringList,
  revenue: revenueData,
  topTrainers,
  messages: clientMessages,
  activity: activityFeed,
};
