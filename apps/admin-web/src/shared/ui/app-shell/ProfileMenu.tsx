import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { LogOut, User } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/shared/ui/avatar'
import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'
import { t } from '@/shared/i18n'
import { useCurrentRole } from '@/shared/session'
import { services } from '@/shared/api/services'
import { queryClient } from '@/app/queryClient'

export function ProfileMenu() {
  const role = useCurrentRole()
  const navigate = useNavigate()
  const initials = role === 'owner' ? 'ВЛ' : 'РЦ'
  const label = role === 'owner' ? t('shell.roleSwitch.owner') : t('shell.roleSwitch.reception')

  const logout = useMutation({
    mutationFn: () => services.auth.logout(),
    onSuccess: () => {
      queryClient.clear()
      void navigate({ to: '/login', replace: true })
    },
    onError: () => {
      // Even on failure, clear local cache + navigate so the operator can retry login.
      queryClient.clear()
      void navigate({ to: '/login', replace: true })
    },
  })

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label={t('shell.profile.label')}>
          <Avatar className="size-8">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{label}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault()
            void navigate({ to: '/profile' })
          }}
        >
          <User className="mr-2 size-4" />
          {t('profile.menuLink')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault()
            logout.mutate()
          }}
          disabled={logout.isPending}
        >
          <LogOut className="mr-2 size-4" />
          {t('shell.profile.logout')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
