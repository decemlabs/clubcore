import type { LucideIcon } from 'lucide-react'
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
} from 'lucide-react'
import { ROUTES } from '@/app/routes'

// UI-SPEC Surface 2: nav gating rule.
// Only Финансы and Отчёты are owner-only per the OWNER_ONLY matrix (can.ts).
// All other items are visible to all roles (reception included), so gating
// is encoded as an optional `ownerOnly` flag rather than overloading the
// `resource` field — keeping the nav contract clear and aligned with UI-SPEC.
// Deferred items (Сообщения, Уведомления, Филиалы) are removed entirely from
// NAV_SECTIONS; they are gone for ALL roles (FND-04 hide-for-future).

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  badge?: string | number
  /** 'accent' — изумрудный бейдж (напр. непрочитанные сообщения). По умолчанию нейтральный. */
  badgeTone?: 'accent'
  /**
   * When true, this item is rendered only for `owner` role.
   * Uses can(role, 'view', ownerResource) via AppSidebar to stay
   * consistent with the OWNER_ONLY matrix (single authority).
   */
  ownerOnly?: boolean
}

export interface NavSection {
  title: string
  items: NavItem[]
}

export const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Управление',
    items: [
      { label: 'Дашборд',    to: ROUTES.dashboard, icon: LayoutDashboard },
      { label: 'Клиенты',    to: ROUTES.clients,   icon: Users, badge: 847 },
      { label: 'Расписание', to: ROUTES.schedule,  icon: Calendar },
      { label: 'Абонементы', to: ROUTES.plans,     icon: CreditCard },
      { label: 'Тренеры',    to: ROUTES.trainers,  icon: UserCog, badge: 12 },
      { label: 'Касса',      to: ROUTES.cashbox,   icon: Wallet },
    ],
  },
  {
    title: 'Аналитика',
    items: [
      // ownerOnly=true: hidden for reception via can(role,'view','reports'|'finance')
      { label: 'Отчёты',       to: ROUTES.reports,    icon: BarChart3, ownerOnly: true },
      { label: 'Финансы',      to: ROUTES.finance,    icon: Banknote,  ownerOnly: true },
      { label: 'Посещаемость', to: ROUTES.attendance, icon: Activity },
      { label: 'Загруженность', to: ROUTES.load,      icon: Clock },
    ],
  },
  {
    title: 'Система',
    items: [
      // Филиалы removed — deferred (FND-04), hidden for all roles.
      { label: 'Настройки', to: ROUTES.settings, icon: Settings },
    ],
  },
]
