import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Users,
  Calendar,
  CreditCard,
  UserCog,
  Wallet,
  BarChart3,
  Activity,
  Clock,
  Banknote,
  Settings,
} from 'lucide-react';
import type { Resource } from '@/shared/session/can';
import { ROUTES } from '@/app/routes';

// UI-SPEC Surface 2: nav gating rule.
// ownerOnly items are gated via can(role, 'view', ownerResource).
// ownerResource must be set explicitly on every ownerOnly item so the sidebar
// filter does not have to guess from the URL path (WR-02).
// Deferred items (Сообщения, Уведомления, Филиалы) are removed entirely from
// NAV_SECTIONS; they are gone for ALL roles (FND-04 hide-for-future).

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  badge?: string | number;
  /** 'accent' — изумрудный бейдж (напр. непрочитанные сообщения). По умолчанию нейтральный. */
  badgeTone?: 'accent';
  /**
   * When true, this item is rendered only for `owner` role.
   * Must be paired with `ownerResource` — the resource passed to can(role,'view',ownerResource).
   */
  ownerOnly?: boolean;
  /**
   * Resource to gate when ownerOnly=true. Required when ownerOnly is set.
   * Explicit resource avoids URL-string heuristics in AppSidebar (WR-02).
   */
  ownerResource?: Resource;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Управление',
    items: [
      { label: 'Дашборд', to: ROUTES.dashboard, icon: LayoutDashboard },
      { label: 'Клиенты', to: ROUTES.clients, icon: Users, badge: 847 },
      { label: 'Расписание', to: ROUTES.schedule, icon: Calendar },
      { label: 'Абонементы', to: ROUTES.plans, icon: CreditCard },
      { label: 'Тренеры', to: ROUTES.trainers, icon: UserCog, badge: 12 },
      { label: 'Касса', to: ROUTES.cashbox, icon: Wallet },
    ],
  },
  {
    title: 'Аналитика',
    items: [
      // ownerOnly=true: hidden for reception via can(role,'view', ownerResource)
      {
        label: 'Отчёты',
        to: ROUTES.reports,
        icon: BarChart3,
        ownerOnly: true,
        ownerResource: 'reports',
      },
      {
        label: 'Финансы',
        to: ROUTES.finance,
        icon: Banknote,
        ownerOnly: true,
        ownerResource: 'finance',
      },
      { label: 'Посещаемость', to: ROUTES.attendance, icon: Activity },
      { label: 'Загруженность', to: ROUTES.load, icon: Clock },
    ],
  },
  {
    title: 'Система',
    items: [
      // Филиалы removed — deferred (FND-04), hidden for all roles.
      // ownerOnly=true: can('reception','view','settings') === false per OWNER_ONLY (WR-03).
      {
        label: 'Настройки',
        to: ROUTES.settings,
        icon: Settings,
        ownerOnly: true,
        ownerResource: 'settings',
      },
    ],
  },
];
