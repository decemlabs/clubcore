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
import { API_MODE } from '@/shared/api/services'
import { useQueryClient } from '@tanstack/react-query'
import { authKeys } from '@/features/auth/api/keys'

const ROLES: Array<{ value: Role; label: string }> = [
  { value: 'owner', label: t('shell.roleSwitch.owner') },
  { value: 'reception', label: t('shell.roleSwitch.reception') },
]

export function RoleSwitcher() {
  // React Hooks must be called unconditionally (before any early returns).
  // Pitfall 7 belt-and-suspenders: when role changes in mock mode, invalidate
  // the cached me() so http-mode-aware components see fresh data.
  const qc = useQueryClient()
  const role = useSessionStore((s) => s.role)
  const setRole = useSessionStore((s) => s.setRole)

  if (API_MODE !== 'mock') return null // D-12: hidden in http-mode

  const current = ROLES.find((r) => r.value === role) ?? ROLES[0]!

  const handleSelect = (next: Role) => {
    setRole(next)
    void qc.invalidateQueries({ queryKey: authKeys.me })
  }

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
            onSelect={() => handleSelect(r.value)}
            className={role === r.value ? 'bg-accent' : ''}
          >
            {r.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
