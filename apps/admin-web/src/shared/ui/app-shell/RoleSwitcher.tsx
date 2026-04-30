import { useSessionStore } from '@/shared/session/store'
import type { Role } from '@/shared/session/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'
import { Button } from '@/shared/ui/button'
import { t } from '@/shared/i18n'
import { UserCog } from 'lucide-react'

const ROLES: Array<{ value: Role; label: string }> = [
  { value: 'owner', label: t('shell.roleSwitch.owner') },
  { value: 'reception', label: t('shell.roleSwitch.reception') },
]

export function RoleSwitcher() {
  const role = useSessionStore((s) => s.role)
  const setRole = useSessionStore((s) => s.setRole)
  const current = ROLES.find((r) => r.value === role) ?? ROLES[0]!

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <UserCog className="size-4" />
          <span className="hidden sm:inline">{current.label}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>{t('shell.roleSwitch.label')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {ROLES.map((r) => (
          <DropdownMenuItem
            key={r.value}
            onSelect={() => setRole(r.value)}
            className={role === r.value ? 'bg-accent' : ''}
          >
            {r.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
