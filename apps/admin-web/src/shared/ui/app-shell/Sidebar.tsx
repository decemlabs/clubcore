import { Link, useRouterState } from '@tanstack/react-router'
import {
  Sidebar as UiSidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/shared/ui/sidebar'
import { useSessionStore } from '@/shared/session/store'
import { routeRegistry } from '@/shared/session/registry'
import { can } from '@/shared/session/can'
import { t } from '@/shared/i18n'
import {
  LayoutDashboard,
  Users,
  CalendarDays,
  UserCog,
  Wallet,
  Settings,
  LogIn,
  Ticket,
  LayoutGrid,
  type LucideIcon,
} from 'lucide-react'

const ICONS: Record<string, LucideIcon> = {
  LayoutDashboard,
  Users,
  CalendarDays,
  UserCog,
  Wallet,
  Settings,
  LogIn, // NEW Phase 22 D-22-4
  Ticket, // NEW Phase 22 D-22-4
  LayoutGrid, // NEW Phase 22 D-22-4
}

export function AppSidebar() {
  const role = useSessionStore((s) => s.role)
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  const items = routeRegistry.filter((entry) => can(role, 'view', entry.resource))

  return (
    <UiSidebar collapsible="icon">
      <SidebarHeader>
        <div className="px-2 py-1.5">
          <span className="text-sm font-semibold">{t('shell.appName')}</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((entry) => {
                const Icon = ICONS[entry.icon] ?? LayoutDashboard
                const isActive =
                  entry.path === '/' ? pathname === '/' : pathname.startsWith(entry.path)
                const label = t(`shell.nav.${entry.navKey}` as const)
                return (
                  <SidebarMenuItem key={entry.navKey}>
                    <SidebarMenuButton asChild isActive={isActive} tooltip={label}>
                      <Link to={entry.path}>
                        <Icon className="size-4" />
                        <span>{label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </UiSidebar>
  )
}
