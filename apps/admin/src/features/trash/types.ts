/**
 * Доменные типы экрана «Корзина» (Trash.html).
 * Мягко удалённые сущности с восстановлением и окончательным удалением.
 * Цвета аватаров — per-entity градиенты (из данных), не токены.
 */

export type TrashType = 'client' | 'trainer' | 'plan' | 'session';

export interface TrashItem {
  id: string;
  type: TrashType;
  name: string;
  /** Вторичная строка: телефон/категория · кто удалил. */
  sub: string;
  /** Градиент аватара (для client/trainer). */
  gradient?: string;
  initials?: string;
  /** Дата удаления, напр. «19 фев». */
  deletedAt: string;
  /** Дней до безвозвратного удаления. */
  daysLeft: number;
}

export interface TrashData {
  items: TrashItem[];
}
