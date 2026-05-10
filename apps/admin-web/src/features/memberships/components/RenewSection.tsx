import { useState } from 'react'
import { Button } from '@/shared/ui/button'
import { RoleGate } from '@/shared/session/RoleGate'
import { RenewConfirmDialog } from './RenewConfirmDialog'
import { t } from '@/shared/i18n'
import type { Membership } from '@/entities/membership'

interface Props {
  membership: Membership
}

export function RenewSection({ membership }: Props) {
  const [open, setOpen] = useState(false)

  // Renew is allowed for active/frozen/expired; backend rejects cancelled
  if (membership.status === 'cancelled') return null

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">{t('memberships.detail.section.renewal')}</h2>
      <RoleGate action="create" resource="memberships">
        <Button variant="default" size="sm" onClick={() => setOpen(true)}>
          {t('memberships.renew.button')}
        </Button>
      </RoleGate>
      <RenewConfirmDialog membership={membership} open={open} onClose={() => setOpen(false)} />
    </section>
  )
}
