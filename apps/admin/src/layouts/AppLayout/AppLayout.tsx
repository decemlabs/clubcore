import type { CSSProperties } from 'react';
import { Outlet } from 'react-router-dom';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { Header } from './Header';
import { ClubProvider } from './ClubProvider';
import { MobileDock } from './MobileDock';

export function AppLayout() {
  return (
    <ClubProvider>
      <SidebarProvider
        className="h-screen overflow-hidden"
        style={{ '--sidebar-width': '248px' } as CSSProperties}
      >
        <AppSidebar />
        <SidebarInset className="min-w-0 overflow-hidden">
          <Header />
          {/* Нижний паддинг на мобиле — под высоту MobileDock + safe-area. */}
          <div className="min-h-0 flex-1 overflow-y-auto max-lg:[padding-bottom:calc(80px+env(safe-area-inset-bottom))]">
            <Outlet />
          </div>
          <MobileDock />
        </SidebarInset>
      </SidebarProvider>
    </ClubProvider>
  );
}
