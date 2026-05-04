import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { t } from '@/shared/i18n'

export const Route = createFileRoute('/_protected/schedule')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'schedule')) {
      throw redirect({ to: '/', search: { forbidden: location.href } })
    }
  },
  component: SchedulePage,
})

function SchedulePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('shell.nav.schedule')}</h1>
      <p className="text-muted-foreground text-sm">Module placeholder.</p>
    </div>
  )
}
