// Plan 05 placeholder; Plan 06 replaces fully with validateSearch + loader + ClientsPage
import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { t } from '@/shared/i18n'

export const Route = createFileRoute('/_protected/clients')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'clients')) {
      throw redirect({ to: '/', search: { forbidden: location.href } })
    }
  },
  component: ClientsPlaceholder,
})

function ClientsPlaceholder() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('shell.nav.clients')}</h1>
      <p className="text-muted-foreground text-sm">Module placeholder.</p>
    </div>
  )
}
