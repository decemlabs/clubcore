import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Users,
  Calendar,
  CreditCard,
  UserCog,
  Wallet,
  MessageSquare,
  Bell,
  BarChart3,
  Activity,
  Clock,
  Banknote,
  Building2,
  Settings,
} from 'lucide-react';
import { ROUTES } from '@/app/routes';

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  badge?: string | number;
  /** 'accent' — изумрудный бейдж (напр. непрочитанные сообщения). По умолчанию нейтральный. */
  badgeTone?: 'accent';
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
      {
        label: 'Сообщения',
        to: ROUTES.messages,
        icon: MessageSquare,
        badge: 4,
        badgeTone: 'accent',
      },
      { label: 'Уведомления', to: ROUTES.notifications, icon: Bell, badge: 5, badgeTone: 'accent' },
    ],
  },
  {
    title: 'Аналитика',
    items: [
      { label: 'Отчёты', to: ROUTES.reports, icon: BarChart3 },
      { label: 'Финансы', to: ROUTES.finance, icon: Banknote },
      { label: 'Посещаемость', to: ROUTES.attendance, icon: Activity },
      { label: 'Загруженность', to: ROUTES.load, icon: Clock },
    ],
  },
  {
    title: 'Система',
    items: [
      { label: 'Филиалы', to: ROUTES.branches, icon: Building2, badge: 3 },
      { label: 'Настройки', to: ROUTES.settings, icon: Settings },
    ],
  },
];
