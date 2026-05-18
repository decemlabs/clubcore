export type Resource =
  | 'dashboard'
  | 'clients'
  | 'schedule'
  | 'staff'
  | 'finance'
  | 'reports'
  | 'payroll'
  | 'compensation'
  | 'templates'
  | 'settings'
  | 'owner-area'
  | 'memberships' // NEW Phase 15 INFRA-09
  | 'membership-plans' // NEW Phase 15 INFRA-09 — kebab-case mirror of Resource.MEMBERSHIP_PLANS.value
  | 'visits' // NEW Phase 15 INFRA-09
  | 'profile' // NEW Phase 22 FE-09 — own-account surface; both roles allowed (NOT in OWNER_ONLY)
  | 'trainers' // NEW Phase 30 INFRA-18 — mirror Resource.TRAINERS.value
  | 'payments' // NEW Phase 30 INFRA-18 — mirror Resource.PAYMENTS.value
  | 'pt-package-plans' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_PACKAGE_PLANS.value
  | 'pt-packages' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_PACKAGES.value
  | 'pt-sessions' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_SESSIONS.value
  | 'schedule-slots' // NEW Phase 37 INFRA-26 — kebab, mirror Resource.SCHEDULE_SLOTS.value
  | 'bookings' // NEW Phase 37 INFRA-26 — mirror Resource.BOOKINGS.value
  | 'users' // NEW Phase 41 INFRA-37 / D-41-23 — multi-user admin backend contract; no sidebar in v1.3 mock-reference

export type Action =
  | 'view'
  | 'create'
  | 'edit'
  | 'delete'
  | 'refund'
  | 'cancel' // NEW Phase 15 INFRA-09 — mirrors backend Action.CANCEL.value
  | 'check_in' // NEW Phase 15 INFRA-09 — underscore mirrors Action.CHECK_IN.value
  | 'list' // NEW Phase 37 INFRA-26 / D-37-03a — mirrors backend Action.LIST.value
  | 'update' // NEW Phase 41 INFRA-37 / D-41-22 — mirrors backend Action.UPDATE.value

export interface RouteEntry {
  path: string
  resource: Resource
  /** Russian sidebar label */
  label: string
  /** lucide-react icon name */
  icon: string
  /** i18n key under shell.nav */
  navKey:
    | 'home'
    | 'clients'
    | 'schedule'
    | 'staff'
    | 'finance'
    | 'settings'
    | 'visits' // NEW Phase 22
    | 'memberships' // NEW Phase 22
    | 'membershipPlans' // NEW Phase 22
}

export const routeRegistry: readonly RouteEntry[] = [
  { path: '/', resource: 'dashboard', label: 'Главная', icon: 'LayoutDashboard', navKey: 'home' },
  { path: '/visits', resource: 'visits', label: 'Отметки', icon: 'LogIn', navKey: 'visits' }, // NEW Phase 22 D-22-4 (position 2 — reception-first)
  { path: '/clients', resource: 'clients', label: 'Клиенты', icon: 'Users', navKey: 'clients' },
  {
    path: '/memberships',
    resource: 'memberships',
    label: 'Абонементы',
    icon: 'Ticket',
    navKey: 'memberships',
  }, // NEW Phase 22 D-22-4
  {
    path: '/membership-plans',
    resource: 'membership-plans',
    label: 'Тарифы',
    icon: 'LayoutGrid',
    navKey: 'membershipPlans',
  }, // NEW Phase 22 D-22-4 (owner-only — filtered by Sidebar can() check)
  {
    path: '/schedule',
    resource: 'schedule',
    label: 'Расписание',
    icon: 'CalendarDays',
    navKey: 'schedule',
  },
  { path: '/staff', resource: 'staff', label: 'Сотрудники', icon: 'UserCog', navKey: 'staff' },
  { path: '/finance', resource: 'finance', label: 'Финансы', icon: 'Wallet', navKey: 'finance' },
  {
    path: '/settings',
    resource: 'settings',
    label: 'Настройки',
    icon: 'Settings',
    navKey: 'settings',
  },
] as const
