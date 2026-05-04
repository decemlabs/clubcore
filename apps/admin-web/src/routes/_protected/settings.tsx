import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { t } from '@/shared/i18n'

export const Route = createFileRoute('/_protected/settings')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'settings')) {
      throw redirect({ to: '/', search: { forbidden: location.href } })
    }
  },
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('shell.nav.settings')}</h1>
      <p className="text-muted-foreground text-sm">Module placeholder.</p>
    </div>
  )
}
