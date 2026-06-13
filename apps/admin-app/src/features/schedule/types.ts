/**
 * Доменные типы экрана «Расписание». Портированы из Schedule.html как design-spec:
 * недельный календарь (7 дней × часовая ось) с цветными блоками-сессиями по тренерам.
 * «Сейчас», сегодня и неделя — данные мока (не выводятся из реального времени).
 */

export type TrainerKey = 'as' | 'ml' | 'lo' | 'dk' | 'sb' | 'ir';
export type SessionKind = 'personal' | 'group';
export type SessionState = 'past' | 'live' | 'planned' | 'cancelled';
export type DayState = 'past' | 'today' | 'holiday' | 'default';
export type HallId = 1 | 2 | 3;

export interface ScheduleTrainer {
  key: TrainerKey;
  /** Цвет блока-события (hex, per-entity). */
  color: string;
  /** Краткое имя для легенды, напр. «Аня С.». */
  legend: string;
}

export interface ScheduleDay {
  /** Аббревиатура дня недели, напр. «Пн». */
  dow: string;
  /** Число/подпись дня, напр. «28», «1 мая». */
  num: string;
  /** Подпись под датой, напр. «завершено», «сегодня · 28 событий». */
  sub: string;
  state: DayState;
}

export interface SessionEvent {
  id: string;
  /** Индекс дня недели 0..6 (Пн..Вс). */
  day: number;
  /** Начало, «HH:MM». */
  start: string;
  /** Конец (для подписи), «HH:MM». */
  end: string;
  /** Длительность в минутах (задаёт высоту блока). */
  durationMin: number;
  trainer: TrainerKey;
  kind: SessionKind;
  state: SessionState;
  /** Жирный заголовок: имя клиента (персональная) или название класса (групповая). */
  who: string;
  /** Приглушённый хвост: дисциплина или вместимость «6/8». */
  focus?: string;
  /** Заметка курсивом, напр. «↻ перенос с 1 мая». */
  note?: string;
  hall: HallId;
}

/** Маркер текущего момента (мок). */
export interface NowMarker {
  day: number;
  label: string;
}

export interface ScheduleData {
  /** Диапазон недели, напр. «28 апр — 4 мая 2026». */
  rangeLabel: string;
  sessionsWeek: number;
  plannedToday: number;
  days: ScheduleDay[];
  trainers: ScheduleTrainer[];
  events: SessionEvent[];
  now: NowMarker;
}
