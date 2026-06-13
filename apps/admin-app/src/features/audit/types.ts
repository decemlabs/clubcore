/**
 * Доменные типы экрана «Журнал действий» (Audit.html).
 * Лог событий, сгруппированный по дням; деталь — модалка с diff (было/стало).
 * Цвета аватаров — per-entity градиенты (из данных), не токены.
 */

export type AuditAction = 'create' | 'edit' | 'delete' | 'login';

export const ACTION_LABEL: Record<AuditAction, string> = {
  create: 'Создание',
  edit: 'Изменение',
  delete: 'Удаление',
  login: 'Вход',
};

export interface AuditActor {
  name: string;
  gradient: string;
  initials: string;
}

export interface AuditDiff {
  label: string;
  /** «—» — значение отсутствовало (создание). */
  old: string;
  new: string;
}

export interface AuditEvent {
  id: string;
  time: string;
  action: AuditAction;
  actor: AuditActor;
  /** Заголовок строки разбит на части: lead + <b>obj</b> + tail. */
  lead: string;
  obj: string;
  tail: string;
  /** Объект для меты модалки, напр. «Абонемент · Анна Петрова». */
  object: string;
  ip: string;
  diff: AuditDiff[];
}

export interface AuditGroup {
  /** Полная подпись дня, напр. «Сегодня · 30 апреля». */
  label: string;
  /** Дата для меты модалки, напр. «30 апреля». */
  date: string;
  events: AuditEvent[];
}

export interface AuditData {
  groups: AuditGroup[];
}
