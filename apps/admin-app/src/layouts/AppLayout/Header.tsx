import { Fragment } from 'react';
import { useMatches } from 'react-router-dom';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { Plus, QrCode } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';
import { GlobalSearch } from './GlobalSearch';
import { NAV_SECTIONS } from './nav-items';
import { useActiveClub } from './club-context';

/** Сегмент(ы) крошки после филиала. */
interface RouteHandle {
  breadcrumb?: string | string[];
}

/**
 * Хлебная крошка: сначала явный `handle.breadcrumb` (подстраницы вне меню,
 * напр. «Клиенты · Архив»), затем фолбэк по активному пункту меню (NAV_SECTIONS).
 */
function useBreadcrumb(): string[] {
  const matches = useMatches();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as RouteHandle | undefined;
    const crumb = handle?.breadcrumb;
    if (crumb) return Array.isArray(crumb) ? crumb : [crumb];
  }
  const pathname = matches[matches.length - 1]?.pathname ?? '';
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      if (item.to === pathname || (item.to !== '/' && pathname.startsWith(item.to))) {
        return [item.label];
      }
    }
  }
  return pathname === '/' ? ['Дашборд'] : [];
}

export function Header() {
  const crumbs = useBreadcrumb();
  const { active } = useActiveClub();
  const { open } = useModals();

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-border bg-bg px-4 md:px-8">
      <SidebarTrigger className="-ml-1 md:hidden" />
      <nav aria-label="breadcrumb" className="flex items-center gap-2 text-[13px] text-fg-muted">
        <span>{active.name}</span>
        {crumbs.map((crumb, i) => (
          <Fragment key={i}>
            <span className="text-fg-subtle">·</span>
            <span className={i === crumbs.length - 1 ? 'font-medium text-fg' : undefined}>
              {crumb}
            </span>
          </Fragment>
        ))}
      </nav>
      <div className="min-w-0 flex-1">
        <GlobalSearch />
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <ThemeToggle />
        <Button
          variant="outline"
          size="icon"
          aria-label="Чек-ин по QR"
          title="Чек-ин по QR"
          className="size-[38px] rounded-full"
          onClick={() => open('checkin')}
        >
          <QrCode className="size-[17px]" />
        </Button>
        <Button
          className="h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0"
          onClick={() => open('new-client')}
        >
          <Plus className="size-[15px]" strokeWidth={2.4} />
          <span className="max-sm:hidden">Новый клиент</span>
        </Button>
      </div>
    </header>
  );
}
