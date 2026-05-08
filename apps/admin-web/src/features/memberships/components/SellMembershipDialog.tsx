import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Input } from '@/shared/ui/input'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select'
import { ApiError, isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
import { todayMSK } from '@/shared/i18n/date'
import { formatMoney } from '@/shared/lib/money'
import { sellMembershipSchema, type SellMembershipFormInput } from '../model/schema'
import { useCreateMembership, useMembershipPlans } from '../api/hooks'

interface Props {
  open: boolean
  onClose: () => void
  clientId: string
}

interface SellFormProps {
  clientId: string
  onSuccess: () => void
  onCancel: () => void
}

function SellMembershipForm({ clientId, onSuccess, onCancel }: SellFormProps) {
  const plansQuery = useMembershipPlans({ active: true })
  const createMembership = useCreateMembership()
  const [rootError, setRootError] = useState<string | null>(null)

  const form = useForm<SellMembershipFormInput>({
    resolver: zodResolver(sellMembershipSchema),
    defaultValues: {
      planId: '',
      paidAt: todayMSK(),
      notes: '',
    },
  })

  const handleError = (err: unknown) => {
    const fields = err instanceof ApiError || isDomainError(err) ? err.fields : undefined
    if (fields) {
      for (const [k, v] of Object.entries(fields)) {
        const msg = Array.isArray(v) ? String(v[0] ?? '') : String(v)
        form.setError(k as keyof SellMembershipFormInput, { type: 'server', message: msg })
      }
      return
    }
    if (isDomainError(err) && err.code === 'mock_not_implemented') {
      setRootError(t('common.errors.demoMode'))
      return
    }
    setRootError(t('common.errors.network'))
  }

  const onSubmit = form.handleSubmit((values) => {
    setRootError(null)
    createMembership.mutate(
      {
        clientId,
        planId: values.planId as import('@/entities/membership').MembershipPlanId,
        paidAt: values.paidAt || undefined,
        notes: values.notes || undefined,
      },
      {
        onSuccess: () => {
          toast.success(t('memberships.toast.sold'))
          onSuccess()
        },
        onError: handleError,
      },
    )
  })

  const plans = plansQuery.data?.items ?? []

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="planId">{t('memberships.form.planSelect')}</Label>
        <Select
          value={form.watch('planId')}
          onValueChange={(v) => form.setValue('planId', v, { shouldValidate: true })}
        >
          <SelectTrigger id="planId">
            <SelectValue placeholder={t('memberships.form.planSelect')} />
          </SelectTrigger>
          <SelectContent>
            {plans.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name} — {formatMoney(p.priceKopecks)} / {p.durationDays}{' '}
                {t('membershipPlans.daysUnit')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {form.formState.errors.planId && (
          <p className="text-destructive text-sm">{form.formState.errors.planId.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="paidAt">{t('memberships.form.paidAt')}</Label>
        <Input id="paidAt" type="date" {...form.register('paidAt')} />
        {form.formState.errors.paidAt && (
          <p className="text-destructive text-sm">{form.formState.errors.paidAt.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="notes">{t('memberships.form.notes')}</Label>
        <Input id="notes" {...form.register('notes')} placeholder={t('memberships.form.notes')} />
        {form.formState.errors.notes && (
          <p className="text-destructive text-sm">{form.formState.errors.notes.message}</p>
        )}
      </div>

      {rootError && (
        <Alert variant="destructive">
          <AlertDescription>{rootError}</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-between pt-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t('membershipPlans.form.cancel')}
        </Button>
        <Button type="submit" disabled={createMembership.isPending}>
          {createMembership.isPending
            ? t('memberships.dialog.sellSubmitting')
            : t('memberships.dialog.sellSubmit')}
        </Button>
      </div>
    </form>
  )
}

export function SellMembershipDialog({ open, onClose, clientId }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t('memberships.dialog.sellTitle')}</DialogTitle>
          <DialogDescription className="sr-only">
            {t('memberships.dialogDescription.sell')}
          </DialogDescription>
        </DialogHeader>
        <SellMembershipForm clientId={clientId} onSuccess={onClose} onCancel={onClose} />
      </DialogContent>
    </Dialog>
  )
}
