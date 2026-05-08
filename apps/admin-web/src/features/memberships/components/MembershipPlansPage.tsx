import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useReactTable, getCoreRowModel, type ColumnDef } from '@tanstack/react-table'
import { Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Route as MembershipPlansRoute } from '@/routes/_protected/membership-plans'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import {
  DataGrid,
  DataGridContainer,
  DataGridTable,
  DataGridPagination,
} from '@/shared/ui/data-grid'
import { Skeleton } from '@/shared/ui/skeleton'
import { t } from '@/shared/i18n'
import { formatMoney } from '@/shared/lib/money'
import { useMembershipPlans, useDeletePlan } from '../api/hooks'
import { MembershipPlanFormDialog } from './MembershipPlanFormDialog'
import type { MembershipPlan, MembershipPlanId } from '@/entities/membership'

function ActiveBadge({ active }: { active: boolean }) {
  if (active) return <Badge variant="default">{t('membershipPlans.status.active')}</Badge>
  return <Badge variant="secondary">{t('membershipPlans.status.archived')}</Badge>
}

export function MembershipPlansPage() {
  const search = MembershipPlansRoute.useSearch()
  const navigate = useNavigate({ from: MembershipPlansRoute.fullPath })
  const [formOpen, setFormOpen] = useState(false)
  const [editPlan, setEditPlan] = useState<MembershipPlan | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<MembershipPlanId | null>(null)

  const query = useMembershipPlans({ page: search.page, pageSize: search.pageSize })
  const deletePlan = useDeletePlan()

  const data = query.data

  const columns: ColumnDef<MembershipPlan>[] = [
    { accessorKey: 'name', header: t('membershipPlans.columns.name') },
    {
      accessorKey: 'durationDays',
      header: t('membershipPlans.columns.durationDays'),
      cell: ({ row }) => `${row.original.durationDays} ${t('membershipPlans.daysUnit')}`,
    },
    {
      accessorKey: 'priceKopecks',
      header: t('membershipPlans.columns.price'),
      cell: ({ row }) => formatMoney(row.original.priceKopecks),
    },
    {
      id: 'active',
      header: t('membershipPlans.columns.status'),
      cell: ({ row }) => <ActiveBadge active={row.original.active} />,
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const p = row.original
        return (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditPlan(p)
                setFormOpen(true)
              }}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive"
              onClick={() => setDeleteId(p.id as MembershipPlanId)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / data.pageSize) : 0,
    state: {
      pagination: {
        pageIndex: data ? data.page - 1 : 0,
        pageSize: data?.pageSize ?? search.pageSize,
      },
    },
    onPaginationChange: (updater) => {
      if (!data) return
      const next =
        typeof updater === 'function'
          ? updater({ pageIndex: data.page - 1, pageSize: data.pageSize })
          : updater
      void navigate({
        search: (prev) => ({
          ...prev,
          page: next.pageIndex + 1,
          pageSize: next.pageSize,
        }),
      })
    },
  })

  const handleDelete = () => {
    if (!deleteId) return
    deletePlan.mutate(deleteId, {
      onSuccess: () => {
        toast.success(t('membershipPlans.toast.deleted'))
        setDeleteId(null)
      },
      onError: () => {
        toast.error(t('common.errors.deleteTariff'))
        setDeleteId(null)
      },
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t('membershipPlans.heading')}</h1>
        <Button
          size="sm"
          onClick={() => {
            setEditPlan(undefined)
            setFormOpen(true)
          }}
        >
          {t('membershipPlans.actions.create')}
        </Button>
      </div>

      {query.isError && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          <h2 className="text-lg font-semibold">{t('membershipPlans.error.heading')}</h2>
          <Button onClick={() => void query.refetch()}>{t('membershipPlans.error.retry')}</Button>
        </div>
      )}

      {query.isLoading && (
        <div className="space-y-3 rounded-md border p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      )}

      {query.isSuccess && data && data.total === 0 && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          <h2 className="text-lg font-semibold">{t('membershipPlans.empty.heading')}</h2>
          <p className="text-muted-foreground text-sm">{t('membershipPlans.empty.body')}</p>
          <Button
            size="sm"
            onClick={() => {
              setEditPlan(undefined)
              setFormOpen(true)
            }}
          >
            {t('membershipPlans.actions.create')}
          </Button>
        </div>
      )}

      {query.isSuccess && data && data.total > 0 && (
        <DataGrid table={table} recordCount={data.total} tableLayout={{ headerSticky: true }}>
          <DataGridContainer>
            <DataGridTable />
          </DataGridContainer>
          <DataGridPagination sizes={[20, 50, 100]} />
        </DataGrid>
      )}

      <MembershipPlanFormDialog
        open={formOpen}
        onClose={() => {
          setFormOpen(false)
          setEditPlan(undefined)
        }}
        plan={editPlan}
      />

      <AlertDialog open={!!deleteId} onOpenChange={(o) => { if (!o) setDeleteId(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('membershipPlans.dialog.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('membershipPlans.dialog.deleteBody')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletePlan.isPending}>
              {t('membershipPlans.form.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={deletePlan.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}
            >
              {deletePlan.isPending ? '…' : t('membershipPlans.dialog.deleteConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
