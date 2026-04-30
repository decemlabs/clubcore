import type { ReactNode } from 'react'
import { SidebarInset, SidebarProvider } from '@/shared/ui/sidebar'
import { TooltipProvider } from '@/shared/ui/tooltip'
import { useUiPrefsStore } from '@/shared/theme/uiPrefsStore'
import { AppSidebar } from './Sidebar'
import { Header } from './Header'

export function AppShell({ children }: { children: ReactNode }) {
  const collapsed = useUiPrefsStore((s) => s.sidebarCollapsed)
  const setCollapsed = useUiPrefsStore((s) => s.setSidebarCollapsed)

  return (
    <TooltipProvider delayDuration={200}>
      <SidebarProvider open={!collapsed} onOpenChange={(open) => setCollapsed(!open)}>
        <AppSidebar />
        <SidebarInset>
          <Header />
          <main className="flex-1 p-4">{children}</main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
