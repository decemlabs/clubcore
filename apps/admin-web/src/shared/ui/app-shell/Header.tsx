import { SidebarTrigger } from '@/shared/ui/sidebar'
import { Separator } from '@/shared/ui/separator'
import { RoleSwitcher } from './RoleSwitcher'
import { ThemeSwitcher } from './ThemeSwitcher'
import { NotificationsBell } from './NotificationsBell'
import { ProfileMenu } from './ProfileMenu'

export function Header() {
  return (
    <header className="bg-background sticky top-0 z-40 flex h-14 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="h-6" />
      <div className="ml-auto flex items-center gap-1">
        <RoleSwitcher />
        <ThemeSwitcher />
        <NotificationsBell />
        <ProfileMenu />
      </div>
    </header>
  )
}
