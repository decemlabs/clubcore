import { useEffect, useState } from 'react'
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
import { isDomainError } from '@/shared/api/errors'
import {
  createTrainerSchema,
  updateTrainerSchema,
  type CreateTrainerInput,
  type UpdateTrainerInput,
} from '../model/schema'
import { useCreateTrainer, useUpdateTrainer } from '../api/hooks'
import type { Trainer } from '@/entities/trainer'

interface Props {
  open: boolean
  onClose: () => void
  trainer?: Trainer
}

export function TrainerFormDialog({ open, onClose, trainer }: Props) {
  const isEdit = !!trainer
  const createTrainer = useCreateTrainer()
  const updateTrainer = useUpdateTrainer()
  const isPending = createTrainer.isPending || updateTrainer.isPending
  const [inlineError, setInlineError] = useState<string | null>(null)

  const form = useForm<CreateTrainerInput | UpdateTrainerInput>({
    resolver: zodResolver(isEdit ? updateTrainerSchema : createTrainerSchema),
    defaultValues: {
      fullName: trainer?.fullName ?? '',
      phone: trainer?.phone ?? undefined,
      ...(isEdit ? { isActive: trainer?.isActive ?? true } : {}),
    },
  })

  useEffect(() => {
    setInlineError(null)
    form.reset({
      fullName: trainer?.fullName ?? '',
      phone: trainer?.phone ?? undefined,
      ...(isEdit ? { isActive: trainer?.isActive ?? true } : {}),
    })
  }, [trainer, form, isEdit])

  const handleClose = () => {
    form.reset()
    setInlineError(null)
    onClose()
  }

  const onSubmit = form.handleSubmit(async (values) => {
    setInlineError(null)
    try {
      if (isEdit && trainer) {
        const editValues = values as UpdateTrainerInput
        const prevIsActive = trainer.isActive
        await updateTrainer.mutateAsync({ id: trainer.id, input: editValues })
        const toastKey =
          editValues.isActive !== prevIsActive
            ? editValues.isActive
              ? 'trainers.toast.reactivated'
              : 'trainers.toast.deactivated'
            : 'trainers.toast.updated'
        toast.success(t(toastKey))
        handleClose()
      } else {
        await createTrainer.mutateAsync(values as CreateTrainerInput)
        toast.success(t('trainers.toast.created'))
        handleClose()
      }
    } catch (err) {
      if (
        isDomainError(err) &&
        err.code === 'validation_failed' &&
        (err.fields as Record<string, unknown> | undefined)?.['phone']
      ) {
        setInlineError(t('trainers.errors.phoneDuplicate'))
      } else {
        toast.error(t('common.errors.network'))
      }
    }
  })

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t('trainers.form.editHeading') : t('trainers.form.createHeading')}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {isEdit ? t('trainers.form.editHeading') : t('trainers.form.createHeading')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="fullName">{t('trainers.form.fields.fullName')}</Label>
            <Input id="fullName" {...form.register('fullName')} />
            {form.formState.errors['fullName'] && (
              <p className="text-destructive text-sm">
                {form.formState.errors['fullName']?.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="phone">{t('trainers.form.fields.phone')}</Label>
            <Input
              id="phone"
              placeholder="+7XXXXXXXXXX"
              {...form.register('phone')}
            />
            {form.formState.errors['phone'] && (
              <p className="text-destructive text-sm">
                {form.formState.errors['phone']?.message}
              </p>
            )}
          </div>

          {isEdit && (
            <div className="flex items-center gap-2">
              <input
                id="isActive"
                type="checkbox"
                className="h-4 w-4 rounded border"
                {...form.register('isActive' as keyof (CreateTrainerInput | UpdateTrainerInput))}
              />
              <Label htmlFor="isActive" className="cursor-pointer">
                {t('trainers.form.fields.isActive')}
              </Label>
            </div>
          )}

          {inlineError && (
            <Alert variant="destructive">
              <AlertDescription>{inlineError}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-between pt-2">
            <Button type="button" variant="outline" onClick={handleClose} disabled={isPending}>
              {t('trainers.form.cancel')}
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending
                ? t('trainers.form.submitting')
                : isEdit
                  ? t('trainers.form.saveEdit')
                  : t('trainers.form.saveCreate')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
