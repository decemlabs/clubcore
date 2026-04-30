import { useUiPrefsStore, type Theme } from './uiPrefsStore'

export function useTheme(): {
  theme: Theme
  setTheme: (t: Theme) => void
  resolved: 'light' | 'dark'
} {
  const theme = useUiPrefsStore((s) => s.theme)
  const setTheme = useUiPrefsStore((s) => s.setTheme)
  const resolved =
    theme === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : theme
  return { theme, setTheme, resolved }
}
