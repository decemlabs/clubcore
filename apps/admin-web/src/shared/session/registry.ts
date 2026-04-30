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

export type Action = 'view' | 'create' | 'edit' | 'delete' | 'refund'

export interface RouteEntry {
  path: string
  resource: Resource
  /** Russian sidebar label */
  label: string
  /** lucide-react icon name */
  icon: string
  /** i18n key under shell.nav */
  navKey: 'home' | 'clients' | 'schedule' | 'staff' | 'finance' | 'settings'
}

export const routeRegistry: readonly RouteEntry[] = [
  { path: '/', resource: 'dashboard', label: 'Главная', icon: 'LayoutDashboard', navKey: 'home' },
  { path: '/clients', resource: 'clients', label: 'Клиенты', icon: 'Users', navKey: 'clients' },
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
