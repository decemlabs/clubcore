/**
 * Доменные типы экрана «Роли и права доступа» (Roles.html).
 * Мастер-деталь: список ролей слева, матрица прав по модулям справа.
 * Цвета аватаров — per-entity градиенты (из данных), не токены.
 */

/** Уровень доступа: 0 — нет, 1 — просмотр, 2 — управление. */
export type PermLevel = 0 | 1 | 2;

export interface RoleModule {
  id: string;
  name: string;
  sub: string;
  /** Ключ иконки модуля (см. ICON в page). */
  icon: string;
}

/** Цветовой класс иконки роли. */
export type RoleIcoClass = 'owner' | 'admin' | 'purple' | 'amber';

export interface RoleAvatar {
  initials: string;
  /** CSS-градиент; отсутствует у chip «+N». */
  gradient?: string;
}

export interface Role {
  id: string;
  name: string;
  /** Системная роль — read-only. */
  sys: boolean;
  locked: boolean;
  icoClass: RoleIcoClass;
  /** Ключ иконки роли (shield/gear/building/store/user/file). */
  icon: string;
  desc: string;
  /** Кол-во сотрудников с ролью. */
  count: number;
  avas: RoleAvatar[];
  /** Права по модулям — порядок совпадает с modules. */
  perms: PermLevel[];
}

export interface RolesData {
  modules: RoleModule[];
  roles: Role[];
}
