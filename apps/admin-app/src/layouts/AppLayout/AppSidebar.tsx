import { ChevronRight } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/cn'
import { APP_NAME } from '@/lib/constants'
import { getInitials } from '@/lib/format'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
import { ClubSelector } from './ClubSelector'
import { NAV_SECTIONS } from './nav-items'

// Активный пункт — высококонтрастная «пилюля» (тёмная в светлой теме, светлая в тёмной),
// перебивает дефолтные data-[active=true] классы shadcn через tailwind-merge.
const NAV_ITEM =
  'h-9 gap-[11px] rounded-[10px] px-3 text-[13.5px] font-medium text-fg-muted [&>svg]:size-[17px] ' +
  'hover:bg-surface hover:text-fg ' +
  'data-[active=true]:bg-ink data-[active=true]:font-medium data-[active=true]:text-surface ' +
  'data-[active=true]:hover:bg-ink data-[active=true]:hover:text-surface'

export function AppSidebar() {
  const { pathname } = useLocation()
  const session = useSession()

  // Default to least-privilege ('reception') while role is unknown (session.isPending).
  // This prevents owner-only items from flashing before the role resolves (T-100-14).
  const role = session.data?.role ?? 'reception'

  const isActive = (to: string) =>
    to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`)

  // UI-SPEC Surface 2: gate ONLY ownerOnly items via can().
  // All other remaining items are visible to all roles (absent = deferred items
  // were removed from NAV_SECTIONS in Task 2 — they are gone for everyone).
  // ownerResource is the explicit resource to check — no URL-string heuristics (WR-02).
  const visibleSections = NAV_SECTIONS
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) =>
          !item.ownerOnly ||
          can(role, 'view', item.ownerResource ?? 'finance'),
      ),
    }))
    .filter((section) => section.items.length > 0)

  return (
    <Sidebar>
      <SidebarHeader className="gap-3.5 px-3.5 pb-3.5 pt-[18px]">
        <div className="flex items-center gap-2.5 px-1">
          <div className="grid size-[30px] shrink-0 place-items-center rounded-[9px] bg-ink text-[15px] font-extrabold tracking-[-0.5px] text-primary">
            {APP_NAME.charAt(0)}
          </div>
          <span className="text-[15px] font-bold tracking-[-0.3px] text-fg">{APP_NAME}</span>
          {/* Role pill — hidden while session is pending (T-100-14 — no owner-item flash). */}
          {session.data ? (
            <span
              className={cn(
                'ml-auto rounded-full px-[7px] py-0.5 text-[10px] font-bold tracking-[0.4px]',
                session.data.role === 'owner'
                  ? 'bg-primary-soft text-primary-deep'
                  : 'bg-surface-3 text-fg-subtle',
              )}
            >
              {session.data.role === 'owner' ? 'Владелец' : 'Ресепшн'}
            </span>
          ) : null}
        </div>
        <ClubSelector />
      </SidebarHeader>

      <SidebarContent className="gap-0 px-3.5">
        {visibleSections.map((section) => (
          <SidebarGroup key={section.title} className="p-0">
            <SidebarGroupLabel className="h-auto px-3 pb-1.5 pt-3.5 text-[10.5px] font-bold uppercase tracking-[0.06em] text-fg-subtle">
              {section.title}
            </SidebarGroupLabel>
            <SidebarMenu className="gap-1">
              {section.items.map((item) => {
                const Icon = item.icon
                const active = isActive(item.to)
                return (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      tooltip={item.label}
                      className={NAV_ITEM}
                    >
                      <Link to={item.to}>
                        <Icon />
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.badge !== undefined ? (
                          <span
                            className={cn(
                              'rounded-full px-[7px] py-px text-[11px] font-bold tabular-nums',
                              active
                                ? 'bg-primary text-[#06120c]'
                                : item.badgeTone === 'accent'
                                  ? 'bg-primary-soft text-primary-deep'
                                  : 'bg-surface-3 text-fg-muted',
                            )}
                          >
                            {item.badge}
                          </span>
                        ) : null}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="px-3.5 pb-[18px]">
        {session.isPending ? (
          /* Loading skeleton — avatar placeholder + name + role lines (UI-SPEC Surface 2) */
          <div className="flex items-center gap-2.5 rounded-[12px] border-[0.5px] border-border bg-surface p-2">
            <div className="size-8 rounded-full bg-surface-3 shrink-0" />
            <div className="flex flex-col gap-1.5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-2.5 w-16" />
            </div>
          </div>
        ) : session.data ? (
          /* Real user card — fullName + localized role label */
          <div className="flex items-center gap-2.5 rounded-[12px] border-[0.5px] border-border bg-surface p-2">
            <div className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#f59e0b] to-[#f97316] text-[12px] font-bold text-white">
              {getInitials(session.data.fullName)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-semibold text-fg">
                {session.data.fullName}
              </div>
              <div className="truncate text-[11.5px] text-fg-subtle">
                {session.data.role === 'owner' ? 'Владелец' : 'Ресепшн'}
              </div>
            </div>
            <button
              type="button"
              aria-label="Профиль"
              className="text-fg-subtle transition-colors hover:text-fg"
            >
              <ChevronRight className="size-3.5" />
            </button>
          </div>
        ) : null}
      </SidebarFooter>
    </Sidebar>
  )
}
