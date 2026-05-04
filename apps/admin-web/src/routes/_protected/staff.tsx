import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { t } from '@/shared/i18n'

export const Route = createFileRoute('/_protected/staff')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'staff')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  component: StaffPage,
})

function StaffPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('shell.nav.staff')}</h1>
      <p className="text-muted-foreground text-sm">Module placeholder.</p>
    </div>
  )
}
