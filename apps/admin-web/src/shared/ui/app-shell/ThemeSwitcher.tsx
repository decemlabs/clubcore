import { useUiPrefsStore } from '@/shared/theme/uiPrefsStore'
import type { Theme } from '@/shared/theme/uiPrefsStore'
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
import { Moon, Sun, Monitor } from 'lucide-react'

const THEMES: Array<{ value: Theme; labelKey: 'shell.theme.light' | 'shell.theme.dark' | 'shell.theme.system'; icon: typeof Sun }> = [
  { value: 'light', labelKey: 'shell.theme.light', icon: Sun },
  { value: 'dark', labelKey: 'shell.theme.dark', icon: Moon },
  { value: 'system', labelKey: 'shell.theme.system', icon: Monitor },
]

export function ThemeSwitcher() {
  const theme = useUiPrefsStore((s) => s.theme)
  const setTheme = useUiPrefsStore((s) => s.setTheme)
  const current = THEMES.find((th) => th.value === theme) ?? THEMES[0]!
  const Icon = current.icon

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t('shell.theme.label')}>
          <Icon className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel>{t('shell.theme.label')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {THEMES.map((th) => {
          const ItemIcon = th.icon
          return (
            <DropdownMenuItem
              key={th.value}
              onSelect={() => setTheme(th.value)}
              className={theme === th.value ? 'bg-accent' : ''}
            >
              <ItemIcon className="mr-2 size-4" />
              {t(th.labelKey)}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
