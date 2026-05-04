import { Skeleton } from '@/shared/ui/skeleton'

/**
 * Loading-state skeleton for the clients DataGrid. ~8 fake rows with column widths
 * matching the real layout (ФИО / Телефон / Email / actions). Rendered by
 * <ClientsTable> when `query.isPending && !query.data`.
 */
export function ClientsTableSkeleton() {
  return (
    <div role="status" aria-label="Загрузка клиентов" className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/6" />
          <Skeleton className="ml-auto h-4 w-12" />
        </div>
      ))}
    </div>
  )
}
