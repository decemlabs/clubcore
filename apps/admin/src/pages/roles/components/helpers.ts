import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Users,
  Calendar,
  CreditCard,
  UserCog,
  Wallet,
  MessageSquare,
  BarChart3,
  Activity,
  Settings,
} from '@/components/icons';

/** Иконка модуля по ключу (зеркалит иконки сайдбара). */
export const MODULE_ICON: Record<string, LucideIcon> = {
  dashboard: LayoutDashboard,
  clients: Users,
  schedule: Calendar,
  plans: CreditCard,
  trainers: UserCog,
  cashbox: Wallet,
  messages: MessageSquare,
  reports: BarChart3,
  attendance: Activity,
  settings: Settings,
};
