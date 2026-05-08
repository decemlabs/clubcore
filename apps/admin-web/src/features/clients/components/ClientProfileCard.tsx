import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Pencil } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { t } from '@/shared/i18n'
import { ClientFormDialog } from './ClientFormDialog'
import type { Client } from '@/entities/client'

interface Props {
  client: Client
}

/**
 * Profile header card — renders client data ONLY.
 * MUST NOT import from @/features/memberships or @/features/visits
 * (ESLint Pattern α zone D-22-12 enforces this statically).
 */
export function ClientProfileCard({ client }: Props) {
  const [editOpen, setEditOpen] = useState(false)

  return (
    <>
      <div className="mb-2">
        <Link to="/clients" className="text-muted-foreground text-sm hover:underline">
          {t('clientProfile.backLink')}
        </Link>
      </div>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-xl font-semibold">{client.fullName}</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            aria-label="Редактировать клиента"
            title="Редактировать клиента"
            onClick={() => setEditOpen(true)}
          >
            <Pencil className="size-4" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-muted-foreground text-sm">{client.phone}</p>
          {client.email && (
            <p className="text-muted-foreground text-sm">{client.email}</p>
          )}
        </CardContent>
      </Card>

      <ClientFormDialog
        mode="edit"
        open={editOpen}
        onClose={() => setEditOpen(false)}
        client={client}
      />
    </>
  )
}
