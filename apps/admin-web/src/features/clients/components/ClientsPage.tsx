import { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import { Route as ClientsRoute } from '@/routes/_protected/clients'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { useClientsList } from '../api/hooks'
import { useDebounceValue } from '@/shared/lib/hooks/useDebounceValue'
import { ClientsTable } from './ClientsTable'
import { ClientFormDialog } from './ClientFormDialog'
import { ClientDeleteDialog } from './ClientDeleteDialog'
import type { Client } from '@/entities/client'

export function ClientsPage() {
  const search = ClientsRoute.useSearch()
  const navigate = useNavigate({ from: ClientsRoute.fullPath })
  const [searchInput, setSearchInput] = useState(search.q ?? '')
  const debounced = useDebounceValue(searchInput, 300)

  // Sync debounced value back to URL (resets page to 1 when q changes)
  useEffect(() => {
    if (debounced === (search.q ?? '')) return
    void navigate({
      search: (prev) => ({
        ...prev,
        q: debounced || undefined,
        page: 1,
      }),
    })
  }, [debounced, search.q, navigate])

  const query = useClientsList(search)
  const [editing, setEditing] = useState<Client | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Client | null>(null)

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Клиенты</h1>
      <div className="flex items-center gap-4">
        <Input
          placeholder="Поиск по имени или телефону..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-md flex-1"
          aria-label="Поиск клиентов"
        />
        <Button onClick={() => setCreating(true)}>
          <Plus className="mr-2 size-4" />
          Новый клиент
        </Button>
      </div>
      <ClientsTable
        query={query}
        search={search}
        onEdit={(c) => setEditing(c)}
        onDelete={(c) => setDeleting(c)}
        onRetry={() => void query.refetch()}
        onCreateFromEmpty={() => setCreating(true)}
      />
      {creating && (
        <ClientFormDialog
          mode="create"
          open={creating}
          onClose={() => setCreating(false)}
        />
      )}
      {editing && (
        <ClientFormDialog
          mode="edit"
          client={editing}
          open={!!editing}
          onClose={() => setEditing(null)}
        />
      )}
      {deleting && (
        <ClientDeleteDialog
          client={deleting}
          open={!!deleting}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
