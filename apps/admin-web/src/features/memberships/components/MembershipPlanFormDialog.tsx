import { useEffect } from 'react'
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
import { t } from '@/shared/i18n'
import { membershipPlanFormSchema, type MembershipPlanFormInput } from '../model/schema'
import { useCreatePlan, useUpdatePlan } from '../api/hooks'
import type { MembershipPlan, MembershipPlanId } from '@/entities/membership'

interface Props {
  open: boolean
  onClose: () => void
  /** If provided, the dialog is in edit mode */
  plan?: MembershipPlan
}

export function MembershipPlanFormDialog({ open, onClose, plan }: Props) {
  const isEdit = !!plan
  const createPlan = useCreatePlan()
  const updatePlan = useUpdatePlan()
  const isPending = createPlan.isPending || updatePlan.isPending

  const form = useForm<MembershipPlanFormInput>({
    resolver: zodResolver(membershipPlanFormSchema),
    defaultValues: {
      name: plan?.name ?? '',
      // Lossless: kopecks → roubles preserves sub-rouble precision (BLK-04).
      priceRoubles: plan ? plan.priceKopecks / 100 : 0,
      durationDays: plan?.durationDays ?? 30,
      active: plan?.active ?? true,
    },
  })

  // Reset form when plan changes (switching between create/edit)
  useEffect(() => {
    form.reset({
      name: plan?.name ?? '',
      priceRoubles: plan ? plan.priceKopecks / 100 : 0,
      durationDays: plan?.durationDays ?? 30,
      active: plan?.active ?? true,
    })
  }, [plan, form])

  const handleClose = () => {
    form.reset()
    onClose()
  }

  const onSubmit = form.handleSubmit((values) => {
    // Round explicitly so an existing fractional rouble value (e.g. 2500.50)
    // round-trips back to the original kopecks (BLK-04). FE allows decimals
    // in the input; backend money is integer minor units.
    const priceKopecks = Math.round(values.priceRoubles * 100)

    if (isEdit && plan) {
      updatePlan.mutate(
        {
          id: plan.id as MembershipPlanId,
          input: {
            name: values.name,
            priceKopecks,
            active: values.active,
          },
        },
        {
          onSuccess: () => {
            toast.success(t('membershipPlans.toast.updated'))
            handleClose()
          },
          onError: () => {
            toast.error(t('common.errors.saveTariff'))
          },
        },
      )
    } else {
      createPlan.mutate(
        {
          name: values.name,
          durationDays: values.durationDays,
          priceKopecks,
          active: values.active,
        },
        {
          onSuccess: () => {
            toast.success(t('membershipPlans.toast.created'))
            handleClose()
          },
          onError: () => {
            toast.error(t('common.errors.createTariff'))
          },
        },
      )
    }
  })

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEdit
            ? t('membershipPlans.dialog.editTitle')
            : t('membershipPlans.dialog.createTitle')}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {isEdit
              ? t('memberships.dialogDescription.edit')
              : t('memberships.dialogDescription.create')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="name">{t('membershipPlans.form.name')}</Label>
            <Input id="name" {...form.register('name')} />
            {form.formState.errors.name && (
              <p className="text-destructive text-sm">{form.formState.errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="durationDays">{t('membershipPlans.form.durationDays')}</Label>
            <Input
              id="durationDays"
              type="number"
              min={1}
              disabled={isEdit}
              {...form.register('durationDays', { valueAsNumber: true })}
            />
            {isEdit && (
              <p className="text-muted-foreground text-xs">
                {t('membershipPlans.form.durationImmutable')}
              </p>
            )}
            {form.formState.errors.durationDays && (
              <p className="text-destructive text-sm">
                {form.formState.errors.durationDays.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="priceRoubles">{t('membershipPlans.form.priceRoubles')}</Label>
            <Input
              id="priceRoubles"
              type="number"
              min={0}
              step={0.01}
              {...form.register('priceRoubles', { valueAsNumber: true })}
            />
            {form.formState.errors.priceRoubles && (
              <p className="text-destructive text-sm">
                {form.formState.errors.priceRoubles.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              id="active"
              type="checkbox"
              className="h-4 w-4 rounded border"
              {...form.register('active')}
              defaultChecked={plan?.active ?? true}
            />
            <Label htmlFor="active" className="cursor-pointer">
              {t('membershipPlans.form.active')}
            </Label>
          </div>

          {(createPlan.isError || updatePlan.isError) && (
            <Alert variant="destructive">
              <AlertDescription>
                {isEdit ? t('common.errors.saveTariff') : t('common.errors.createTariff')}
              </AlertDescription>
            </Alert>
          )}

          <div className="flex justify-between pt-2">
            <Button type="button" variant="ghost" onClick={handleClose} disabled={isPending}>
              {t('membershipPlans.form.cancel')}
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending
                ? t('membershipPlans.form.submitting')
                : isEdit
                  ? t('membershipPlans.form.saveEdit')
                  : t('membershipPlans.form.saveCreate')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
